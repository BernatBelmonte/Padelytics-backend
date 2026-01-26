import time
import json
import os
import sys
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Importar configuración
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PREMIER_PADEL_TOURNAMENTS_URL, YEARS_TO_SCRAPE

class PremierTournamentsScraper:
    def __init__(self, existing_data_ref):
        self.existing_ids = [t['tournaments_id'] for t in existing_data_ref]
        self.scraped_data = []
        
        # Configurar Selenium
        opts = Options()
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--headless") # Headless para producción/servidor
        self.driver = webdriver.Chrome(options=opts)
        self.wait = WebDriverWait(self.driver, 10)

    def run(self):
        print("   📥 Scraping Premier tournaments...")
        print("    ==================================")
        self.driver.get(PREMIER_PADEL_TOURNAMENTS_URL)
        time.sleep(5)

        try:
            for year in YEARS_TO_SCRAPE:
                self._process_year(year)
        except Exception as e:
            print(f"❌ Critical Selenium Error: {e}")
        finally:
            self.driver.quit()
        
        return self.scraped_data

    def _process_year(self, year):
        print(f"\n    📅 Scanning Premier Year: {year}")
        if not self._select_year(year): return

        # Meses a escanear
        MONTHS = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]

        # Rebobinar a Enero
        try:
            left_arrow = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//img[contains(@src, 'larrow')]]")
            ))
            for _ in range(12):
                left_arrow.click()
                time.sleep(0.2)
            del self.driver.requests
        except: pass # Quizás ya estábamos al principio

        # Avanzar meses
        try:
            right_arrow = self.driver.find_element(By.XPATH, "//button[.//img[contains(@src, 'rarrow')]]")
            for i, month in enumerate(MONTHS):
                print(f"        👉 [{i+1}/12] {month}...", end="")
                self._catch_api_response()
                if i < 11:
                    del self.driver.requests
                    right_arrow.click()
                    time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ Nav error: {e}")

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
        print(f"   ⚠️ Could not select {year}")
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
                                if t['tournaments_id'] in self.existing_ids:
                                    print(t['full_name'], t['tournaments_id'])
                                    continue
                                self.scraped_data.append(t)
                                new_count += 1
                            print(f" ✅ Got {new_count} new.")
                            return
                    except: pass
        print(" .")