import json
import time
import os
import sys
import re
from unidecode import unidecode
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    RAW_DATA_DIR,
    RAW_PREMIER_PADEL_PLAYERS_FILE,
    RAW_PREMIER_PADEL_TOURNAMENTS_FILE,
    PREMIER_PADEL_RESULTS_URL,
    STATIC_PLAYERS_FILE
)  

class PremierPlayersInterceptor:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--headless") # Keep visible to debug
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.all_entries = []
        self.existing_slugs = set()
        self.existing_players = []

    def start(self):
        print("🎾 Premier Padel Player Scraper")
        print("===============================")

        self._load_players_data() # Get existing players data
        self._load_players_slugs() # Get existing players slugs new file cause its a processed file
        tournament_slugs = self._load_tournaments_slugs()

        
        try:
            print(f"🚀 Starting Interceptor...")
            for slug in tournament_slugs:
                self._process_tournament_slug(slug)
            self.all_entries.extend(self.existing_players)  # Add existing players to the final list
            self._save_to_json()

        except Exception as e:
            print(f"❌ Critical Error: {e}")
        finally:
            self.driver.quit()

    def _load_players_slugs(self):
        if os.path.exists(STATIC_PLAYERS_FILE):
            with open(STATIC_PLAYERS_FILE, "r", encoding="utf-8") as f:
                players = json.load(f)
            for player in players:
                self.existing_slugs.add(player['slug'])
            print(f"🔄 Loaded {len(players)} existing player slugs.")
        else:
            print("ℹ️ No existing players slugs found.")

    def _load_players_data(self):
        if os.path.exists(RAW_PREMIER_PADEL_PLAYERS_FILE):
            with open(RAW_PREMIER_PADEL_PLAYERS_FILE, "r", encoding="utf-8") as f:
                players = json.load(f)
                self.existing_players = players
        else:
            print("ℹ️ No existing players data found.")

    @staticmethod
    def _clean_player_name(name):
        if not name: 
            return ""
        # Normalize characters (e.g. ñ -> n, á -> a)
        text = unidecode(name).lower()
        # Replace non-alphanumeric characters with hyphens
        text = re.sub(r'[^a-z0-9]+', '-', text)
        # Strip leading/trailing hyphens
        return text.strip('-')

    def _load_tournaments_slugs(self):
        if os.path.exists(RAW_PREMIER_PADEL_TOURNAMENTS_FILE):
            with open(RAW_PREMIER_PADEL_TOURNAMENTS_FILE, "r", encoding="utf-8") as f:
                tournaments = json.load(f)
            # We want all tournaments
            slugs = [t['slug'] for t in tournaments]
            print(f"🔄 Loaded {len(slugs)} tournament slugs.")
            return slugs
        else:
            print("ℹ️ No existing tournaments data found.")
            return []

    def _process_tournament_slug(self, slug):
        print(f"\n📅 TOURNAMENT: {slug}")
        del self.driver.requests
        # Navigate to the Player List Page
        try:
            url = f"{PREMIER_PADEL_RESULTS_URL}{slug}/playerlist"
            self.driver.get(url)
            time.sleep(3)
            
        except Exception as e:
            print(f"   ❌ Navigation Failed: {e}")
            return
        
        entries_found = self._catch_api_response_players()
        if entries_found:
            self.all_entries.extend(entries_found)


    def _catch_api_response_players(self):
        start_time = time.time()
    
        while time.time() - start_time < 5:
            for request in reversed(self.driver.requests):
                if request.response and "gettournamentsplayer" in request.url:
                    try:
                        body = request.response.body
                        data = json.loads(body.decode('utf-8'))
                        
                        if data.get('status') == 1:
                            raw_data = data.get('data', [])
                            main_players = raw_data.get('player_md', [])
                            qualy_players = raw_data.get('player_mq', [])
                            all_players = main_players + qualy_players
                            non_existing_players = []
                            for player in all_players:
                                player_slug = self._clean_player_name(player.get('player_name', None))
                                if player_slug and player_slug not in self.existing_slugs:
                                    non_existing_players.append(player)
                            print(f"   ✅ Captured {len(non_existing_players)} new players (Packet size: {len(all_players)})")
                            return non_existing_players
                    except Exception:
                        pass
        print("   ⚠️ No API call (empty tournament?)")         
        return []

    def _save_to_json(self):
        if not os.path.exists(RAW_DATA_DIR):
            os.makedirs(RAW_DATA_DIR)
        with open(RAW_PREMIER_PADEL_PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.all_entries, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.all_entries)- len(self.existing_players)} total player entries to {RAW_PREMIER_PADEL_PLAYERS_FILE}")

if __name__ == "__main__":
    bot = PremierPlayersInterceptor()
    bot.start()