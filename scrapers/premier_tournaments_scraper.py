import json
import time
import os
import sys
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PREMIER_PADEL_TOURNAMENTS_URL,
    RAW_DATA_DIR, RAW_PREMIER_PADEL_TOURNAMENTS_FILE,
    YEARS_TO_SCRAPE
)

class PremierTournamentInterceptor:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--headless") # Keep visible to debug

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.all_tournaments = [] 

    def start(self):
        print("🏓 Premier Padel Tournament Scraper")
        print("===================================")
        print("Loading existing data...")
        self._load_existing_data()
        print(f"🚀 Starting Interceptor at: {PREMIER_PADEL_TOURNAMENTS_URL}")
        self.driver.get(PREMIER_PADEL_TOURNAMENTS_URL)
        time.sleep(5) 

        try:
            for year in YEARS_TO_SCRAPE:
                self._process_year(year)
            
            self._save_to_json()

        except Exception as e:
            print(f"❌ Critical Error: {e}")
        finally:
            self.driver.quit()

    def _process_year(self, year):
        print(f"\n📅 YEAR: {year}")
        
        # Select Year from Dropdown
        if not self._select_year(year):
            return

        # Define months to tag the data correctly
        MONTH_NAMES = [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ]

        # Rewind to January
        print("   ⏪ Rewinding to start...")
        try:
            # Look for Left Arrow (button with larrow.svg)
            left_arrow = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//img[contains(@src, 'larrow')]]")
            ))
            
            # Spam click left to ensure we are at the beginning
            for _ in range(12):
                left_arrow.click()
                time.sleep(0.5)
            
            # Clear requests so we start fresh for the actual scan
            del self.driver.requests
            time.sleep(1) 
            
        except Exception as e:
            print(f"   ⚠️ Rewind failed (maybe already at start?): {e}")

        print("   ⏩ Scanning Months...")
        
        try:
            # Look for Right Arrow (button with rarrow.svg)
            right_arrow = self.driver.find_element(By.XPATH, "//button[.//img[contains(@src, 'rarrow')]]")

            for i, month_name in enumerate(MONTH_NAMES):
                print(f"   👉 [{i+1}/12] Scanning: {month_name}...", end="")
                self._catch_api_response()

                if i < 11:
                    try:
                        del self.driver.requests 
                        right_arrow.click()
                        time.sleep(0.5) # Wait for animation & API trigger
                    except Exception as e:
                        print(f" (Arrow Error: {e})", end="")

        except Exception as e:
            print(f"   ❌ Error traversing: {e}")

    def _select_year(self, year):
        try:
            container = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".tournaments-month-select-box")
            ))
            
            dropdown = container.find_element(By.CSS_SELECTOR, ".react-dropdown-select")
            dropdown.click()
            time.sleep(0.5)
            
            options = self.driver.find_elements(By.XPATH, f"//span[contains(@class, 'react-dropdown-select-item') and text()='{year}']")
            
            if options:
                # Click the last one found (usually the visible one if there are dupes)
                options[-1].click()
                print(f"   ✅ Year {year} selected.")
                time.sleep(2) # Wait for page reload
                return True
            else:
                print(f"   ⚠️ Option '{year}' not found in dropdown.")
                return False

        except Exception as e:
            print(f"   ❌ Could not select year {year}: {e}")
            return False

    def _catch_api_response(self):
        # Wait up to 5 seconds for the request
        start_time = time.time()
        
        while time.time() - start_time < 5:
            for request in reversed(self.driver.requests):
                if request.response and "getfanapptournaments" in request.url:
                    try:
                        body = request.response.body
                        data = json.loads(body.decode('utf-8'))
                        
                        if data.get('status') == 1:
                            
                            items = data.get('data', [])
                            new_count = 0
                            for t in items:
                                if not any(existing['tournaments_id'] == t.get('tournaments_id') for existing in self.all_tournaments):
                                    self.all_tournaments.append(t)
                                    new_count += 1
                            
                            print(f" ✅ Captured {new_count} new (Packet size: {len(items)})")
                            return 
                    except:
                        pass
        print(" ⚠️ No API call (empty month?)")

    def _load_existing_data(self):
        if os.path.exists(RAW_PREMIER_PADEL_TOURNAMENTS_FILE):
            with open(RAW_PREMIER_PADEL_TOURNAMENTS_FILE, "r", encoding="utf-8") as f:
                self.all_tournaments = json.load(f)
            print(f"🔄 Loaded {len(self.all_tournaments)} existing tournaments.")
        else:
            self.all_tournaments = []
            print("ℹ️ No existing tournaments data found.")

    def _save_to_json(self):
        if not os.path.exists(RAW_DATA_DIR):
            os.makedirs(RAW_DATA_DIR) 
        with open(RAW_PREMIER_PADEL_TOURNAMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.all_tournaments, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.all_tournaments)} tournaments.")

if __name__ == "__main__":
    bot = PremierTournamentInterceptor()
    bot.start()