import sys
import os
import time
import json
from datetime import datetime

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from typing import List, Dict, Set, Optional

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PREMIER_PADEL_TOURNAMENTS_URL,
    YEARS_TO_SCRAPE
)

class PremierTournamentsScraper:
    """
    A scraper designed to extract tournament data from the Premier Padel website.
    
    This class uses SeleniumWire to intercept background API requests triggered 
    by UI navigation (month/year selection), allowing for clean data extraction 
    without manual HTML parsing.
    """
    def __init__(self, finished_tournaments: Set[str]):
        """
        Initializes the scraper with Selenium configuration and an exclusion set.

        Args:
            finished_tournaments: A set of tournament slugs that have already been
                processed and should be ignored during scraping.
        """
        self.finished_tournaments: Set[str] = finished_tournaments
        self.scraped_data: List[Dict] = []
        
        # Selenium setup
        opts = Options()
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--headless")
        self.driver = webdriver.Chrome(options=opts)
        self.wait = WebDriverWait(self.driver, 10)

    def run(self, last_date: Optional[datetime]) -> List[Dict]:
        """
        Starts the scraping process across specified years.

        Args:
            last_date: The date of the last finished tournament. Only years 
                from this date forward will be processed.

        Returns:
            scraped_data: A list of dictionaries containing the raw tournament data objects
            captured from the API.
        """
        print("📥 Scraping Premier tournaments...")
        self.driver.get(PREMIER_PADEL_TOURNAMENTS_URL)
        time.sleep(5)
        years_to_scrape = [year for year in YEARS_TO_SCRAPE if not last_date or year >= last_date.year]
        try:
            for year in years_to_scrape:
                self._process_year(year)
        except Exception as e:
            print(f"    Selenium Error: {e}")
        finally:
            self.driver.quit()
        print(f"--------------------------------")
        return self.scraped_data

    def _process_year(self, year: int) -> None:
        """
        Navigates the calendar for a specific year and iterates through all 12 months.

        Args:
            year: The calendar year to scan.
        """
        print(f"    Scanning Premier Calendar for: {year}")
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

        print(f"        [01/12] -> ", end="", flush=True)
        self._catch_api_response() # Catch initial month response

        # Advance months
        try:
            right_arrow = self.driver.find_element(By.XPATH, "//button[.//img[contains(@src, 'rarrow')]]")
            for i in range(1, 12):
                if i < 9:
                    print(f"        [0{i+1}/12] -> ", end="", flush=True)
                else:
                    print(f"        [{i+1}/12] -> ", end="", flush=True)
                del self.driver.requests
                
                right_arrow.click()
                
                self._catch_api_response()
                
                time.sleep(1)
        except Exception as e:
            print(f"    Nav error: {e}")

    def _select_year(self, year: int) -> bool:
        """
        Interacts with the dropdown UI to change the active year.

        Args:
            year: The year value to select in the dropdown.

        Returns:
            bool: True if selection was successful, False otherwise.
        """
        try:
            container = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".tournaments-month-select-box")
            ))
            dropdown = container.find_element(By.CSS_SELECTOR, ".react-dropdown-select")
            dropdown.click()
            time.sleep(0.8)
            opts = self.driver.find_elements(By.XPATH, f"//span[contains(@class, 'react-dropdown-select-item') and text()='{year}']")
            if opts:
                opts[-1].click()
                time.sleep(2)
                return True
        except: pass
        print(f"    Could not select {year}")
        return False

    def _catch_api_response(self) -> None:
        """
        Intercepts network requests to find the specific API call for tournament data.
        
        This method polls the intercepted requests for up to 6 seconds until a 
        matching URL with a valid JSON body is found. It then appends new, 
        non-duplicate tournaments to the internal storage.
        """
        start = time.time()
        while time.time() - start < 6:
            target_requests = [r for r in self.driver.requests if "getfanapptournaments" in r.url]
            if target_requests:
                req = target_requests[-1]
                if req.response:
                    try:
                        body = json.loads(req.response.body.decode('utf-8'))
                        if body.get('status') == 1:
                            items = body.get('data', [])
                            catched = 0
                            for t in items:
                                if t['slug'] not in [x['slug'] for x in self.scraped_data] and \
                                    t['slug'] not in self.finished_tournaments:
                                    self.scraped_data.append(t)
                                    catched += 1
                            print(f"    Found {catched} tournaments.")
                            return
                        else:
                            print(f"    API returned error status: {body.get('status')}")
                    except Exception as e:
                        print(f"    Failed to parse API response: {e}")
            time.sleep(0.5)
        print("Timed out waiting for API.")