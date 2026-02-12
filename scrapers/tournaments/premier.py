import time
import json
import os
import sys
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PREMIER_PADEL_TOURNAMENTS_URL,
    YEARS_TO_SCRAPE
)

class PremierTournamentsScraper:
    """
    Docstring for PremierTournamentsScraper
    Class to scrape tournament data from the Premier Padel website using Selenium.
    Methods:
        - __init__: Initializes the scraper with existing tournament IDs.
        - run: Main method to start scraping process.
        - _process_year: Processes tournaments for a specific year.
        - _select_year: Selects the desired year in the website's dropdown.
        - _catch_api_response: Captures and processes the API response containing tournament data.
    """
    def __init__(self, existing_ids):
        self.existing_ids = existing_ids
        self.scraped_data = []
        
        # Selenium setup
        opts = Options()
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--no-sandbox")
        # opts.add_argument("--headless")
        self.driver = webdriver.Chrome(options=opts)
        self.wait = WebDriverWait(self.driver, 10)

    def run(self, last_date):
        print("📥 Scraping Premier tournaments...")
        print("==================================")
        self.driver.get(PREMIER_PADEL_TOURNAMENTS_URL)
        time.sleep(5)
        years_to_scrape = [year for year in YEARS_TO_SCRAPE if not last_date or year >= last_date.year]
        months_to_scrape_first_year = len([month for month in range(1, 13) if not last_date or month >= last_date.month])
        try:
            first = True
            for year in years_to_scrape:
                self._process_year(year, first, months_to_scrape_first_year)
                first = False
        except Exception as e:
            print(f"    ❌ Selenium Error: {e}")
        finally:
            self.driver.quit()
        return self.scraped_data

    def _process_year(self, year, first, months_to_scrape_first_year):
        print(f"    📅 Scanning Premier Year: {year}")
        if not self._select_year(year): return

        # Rewind to January
        try:
            left_arrow = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//img[contains(@src, 'larrow')]]")
            ))
            for _ in range(12):
                del self.driver.requests
                left_arrow.click()
                time.sleep(0.2)
        except: pass # Maybe we were already at the beginning

        # Advance months
        try:
            right_arrow = self.driver.find_element(By.XPATH, "//button[.//img[contains(@src, 'rarrow')]]")
            for i in range(12 - months_to_scrape_first_year) if first else range(12):
                print(f"        👉 [{i+1}/12]...", end="")
                self._catch_api_response()
                if i < 11:
                    del self.driver.requests
                    right_arrow.click()
                    time.sleep(0.5)
        except Exception as e:
            print(f"    ❌ Nav error: {e}")

    def _select_year(self, year):
        try:
            container = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".tournaments-month-select-box")
            ))
            dropdown = container.find_element(By.CSS_SELECTOR, ".react-dropdown-select")
            dropdown.click()
            time.sleep(0.5)
            opts = self.driver.find_elements(By.XPATH, f"//span[contains(@class, 'react-dropdown-select-item') and text()='{year}']")
            if opts:
                opts[-1].click()
                time.sleep(2)
                return True
        except: pass
        print(f"    ⚠️ Could not select {year}")
        return False

    def _catch_api_response(self):
        start = time.time()
        while time.time() - start < 4:
            for req in reversed(self.driver.requests):
                if req.response and "getfanapptournaments" in req.url:
                    try:
                        body = json.loads(req.response.body.decode('utf-8'))
                        if body.get('status') == 1:
                            items = body.get('data', [])
                            new_count = 0
                            for t in items:
                                if t['tournaments_id'] not in [x['tournaments_id'] for x in self.scraped_data]:
                                    self.scraped_data.append(t)
                                    new_count += 1
                                else:
                                    continue
                                
                            print(f"    ✅ Got {new_count} new.")
                            return
                    except: pass