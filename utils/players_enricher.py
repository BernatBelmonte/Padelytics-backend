import requests
import json
import os
import sys
import time
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    STATIC_PLAYERS_FILE,
    USER_AGENT, 
    FIP_PLAYER_URL
)

class PlayersEnricher:
    def __init__(self):
        self.headers = {"User-Agent": USER_AGENT}
        self.players_data = []

    def start(self):
        print("🕵️‍♀️ FIP Players Enricher")
        print("========================")

        if not self._load_data():
            return

        self._enrich_players()
        self._save_data()

    def _load_data(self):
        if os.path.exists(STATIC_PLAYERS_FILE):
            try:
                with open(STATIC_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    self.players_data = json.load(f)
                print(f"📚 Loaded {len(self.players_data)} players to enrich.")
                return True
            except Exception as e:
                print(f"❌ Error loading file: {e}")
                return False
        else:
            print(f"⚠️ File not found: {STATIC_PLAYERS_FILE}")
            return False

    def _enrich_players(self):
        total = len(self.players_data)
        
        for index, player in enumerate(self.players_data):
            # If already enriched, skip
            if player.get('birth_date') or player.get('height'):
                print(f"[{index+1}/{total}] ⏭️ Skipping: {player['name']} (already enriched)")
                continue
            fip_url = f"{FIP_PLAYER_URL}{player['slug']}/"
    
            print(f"[{index+1}/{total}] 🔎 Scraping: {player['name']} ({fip_url})...", end=" ")
            try:
                details = self._scrape_player_profile(fip_url)
                if details:
                    player.update(details)
                    print("✅ Found!")
                else:
                    print("⚠️ Profile not found.")

            except Exception as e:
                print(f"❌ Error: {e}")

            time.sleep(1)

    def _scrape_player_profile(self, url):
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 404:
                return None
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            data = {}

            # Country
            country_tag = soup.select_one('.slider__country.player__country')
            data['country'] = country_tag.get_text(strip=True) if country_tag.get_text(strip=True) != '--' else None # type: ignore
            
            # Height
            height_tag = soup.select_one('.additionalInfo__height .additionalInfo__data')
            data['height'] = height_tag.get_text(strip=True) if height_tag.get_text(strip=True) != '--' else None # type: ignore
            
            # Position (Hand/Side)
            pos_tag = soup.select_one('.additionalInfo__hand .content')
            data['position'] = pos_tag.get_text(strip=True) if pos_tag.get_text(strip=True) != '--' else None # type: ignore
            
            # Birth Date
            birth_tag = soup.select_one('.additionalInfo__birth .additionalInfo__data')
            data['birth_date'] = birth_tag.get_text(strip=True) if birth_tag.get_text(strip=True) != '--' else None # type: ignore

            return data
        
        except Exception:
            return None

    def _save_data(self):
        try:
            with open(STATIC_PLAYERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.players_data, f, indent=4, ensure_ascii=False)
            print(f"💾 Saved updates to {STATIC_PLAYERS_FILE}")
        except Exception as e:
            print(f"❌ Error saving data: {e}")

if __name__ == "__main__":
    enricher = PlayersEnricher()
    enricher.start()