import json
import time
import os
import re
from unidecode import unidecode
import sys
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PREMIER_PADEL_RESULTS_URL,
    PREMIER_PADEL_MATCH_STATS_URL,
    RAW_DATA_DIR,
    RAW_PREMIER_PADEL_MATCHES_FILE,
    RAW_PREMIER_PADEL_TOURNAMENTS_FILE
)

class PremierMatchesInterceptor:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless") # Keep visible to debug

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.existing_matches = []
        self.existing_matche_ids = set()
        self.all_matches = [] 
        self.draw_contestants = {}
        self.draw_matches = []

    def start(self):
        print("🏓 Premier Padel Matches Scraper")
        print("==================================")
        print(f"🚀 Starting Interceptor at: {PREMIER_PADEL_RESULTS_URL}")

        self._load_existing_matches() # Load existing matches to avoid already scraped ones
        tournament_slugs = self._load_tournaments_slugs()
        try:
            for slug in tournament_slugs:
                self._process_tournament_slug(slug)
            self.all_matches.extend(self.existing_matches)
            self._save_to_json()
        except Exception as e:
            print(f"❌ Critical Error: {e}")
        finally:
            self.driver.quit()

    def _load_existing_matches(self):
        if os.path.exists(RAW_PREMIER_PADEL_MATCHES_FILE):
            with open(RAW_PREMIER_PADEL_MATCHES_FILE, "r", encoding="utf-8") as f:
                matches = json.load(f)
                for match in matches:
                    self.existing_matche_ids.add(match['match_score']['tournaments_match_id'])
                self.existing_matches = matches
            print(f"🔄 Loaded {len(matches)} existing matches.")
        else:
            print("ℹ️ No existing matches data found.")
            return []

    def _load_tournaments_slugs(self):
        if os.path.exists(RAW_PREMIER_PADEL_TOURNAMENTS_FILE):
            with open(RAW_PREMIER_PADEL_TOURNAMENTS_FILE, "r", encoding="utf-8") as f:
                tournaments = json.load(f)
            slugs = [t['slug'] for t in tournaments if t['is_result_available'] == 'Yes']
            print(f"🔄 Loaded {len(slugs)} tournament slugs.")
            return slugs
        else:
            print("ℹ️ No existing tournaments data found.")
            return []

    def _process_tournament_slug(self, slug):
        print(f"\n📅 TOURNAMENT SLUG: {slug}")

        self.draw_contestants = {}
        self.draw_matches = []
        try:
            draw_url = f"{PREMIER_PADEL_RESULTS_URL}{slug}/draws" 
            print(f"   🕷️ Fetching Draw Data from: {draw_url}")
            
            del self.driver.requests # Clear logs
            self.driver.get(draw_url)
            time.sleep(4) # Wait for API load
            
            draw_data = self._catch_api_response_draw()
            if draw_data:
                self.draw_contestants = draw_data.get('contestants', {})
                teams_in_draw = draw_data.get('contestants', {})
                matches_in_draw = draw_data.get('matches', [])
                for match_in_draw in matches_in_draw:
                    if match_in_draw['sides'][0].get('contestantId') != 'bye' and match_in_draw['sides'][1].get('contestantId') != 'bye':
                        try:
                            match = {
                                "team_1": {
                                    "p1": self._normalize(teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][0]['title']),
                                    "p1_raw": teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][0]['title'],
                                    "p2": self._normalize(teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][1]['title']),
                                    "p2_raw": teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][1]['title'],
                                },
                                "team_2": {
                                    "p1": self._normalize(teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][0]['title']),
                                    "p1_raw": teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][0]['title'],
                                    "p2": self._normalize(teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][1]['title']),
                                    "p2_raw": teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][1]['title'],
                                }
                                }
                            self.draw_matches.append(match)
                        except Exception as e:
                            print(f"Could not process match in draw: {e}")
                print(f"      ✅ Draw Main Data Captured ({len(self.draw_contestants)} contestants)")
            else:
                print("      ⚠️ Draw API not found or empty.")

        except Exception as e:
            print(f"   ❌ Error fetching Draw: {e}")

        try:
            # Look for "Qualification" or "Qualifiers" button
            quali_btn = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Qualification') or contains(text(), 'Qualifiers') or contains(text(), 'Qualify')]")
            
            clickable_btn = None
            for btn in quali_btn:
                if btn.tag_name in ['div', 'span', 'button', 'a', 'p']:
                    clickable_btn = btn
                    break
            
            if clickable_btn:
                del self.driver.requests # Clear logs
                self.driver.execute_script("arguments[0].click();", clickable_btn)
                time.sleep(3) # Wait for Quali Draw API
                
                quali_data = self._catch_api_response_draw()
                if quali_data:
                    self.draw_contestants = quali_data.get('contestants', {})
                    teams_in_draw = quali_data.get('contestants', {})
                    matches_in_draw = quali_data.get('matches', [])
                    for match_in_draw in matches_in_draw:
                        if match_in_draw['sides'][0].get('contestantId') != 'bye' and match_in_draw['sides'][1].get('contestantId') != 'bye':
                            try:
                                match = {
                                    "team_1": {
                                        "p1": self._normalize(teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][0]['title']),
                                        "p1_raw": teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][0]['title'],
                                        "p2": self._normalize(teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][1]['title']),
                                        "p2_raw": teams_in_draw[match_in_draw['sides'][0]['contestantId']]['players'][1]['title'],
                                    },
                                    "team_2": {
                                        "p1": self._normalize(teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][0]['title']),
                                        "p1_raw": teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][0]['title'],
                                        "p2": self._normalize(teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][1]['title']),
                                        "p2_raw": teams_in_draw[match_in_draw['sides'][1]['contestantId']]['players'][1]['title'],
                                    }
                                    }
                                self.draw_matches.append(match)
                            except Exception as e:
                                print(f"Could not process match in draw: {e}")
                    print(f"      ✅ Draw Qualy Data Captured ({len(self.draw_contestants)} contestants)")
                else:
                    print("      ⚠️ Draw API not found or empty.")
            else:
                print("      ℹ️ No Qualification tab found.")
        
        except Exception as e:
            print(f"      ⚠️ Quali tab interaction failed: {e}")

        print(f"      ✅ Total Contestants: {len(self.draw_contestants)} | Total Draw Matches: {len(self.draw_matches)}")

        
        try:
            url = f"{PREMIER_PADEL_RESULTS_URL}{slug}/results"
            print(url)
            self.driver.get(url)
            time.sleep(3) 
        except Exception as e:
            print(f"   ❌ Could not load tournament page {slug}: {e}")
            return

        try:
            container = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".new-results-list")
            ))
            
            try:
                self.wait.until(
                    lambda driver: len(container.find_elements(By.TAG_NAME, "a")) > 0
                )
            except:
                print("      ⚠️ Schedule list is empty.")
                return

            day_buttons = container.find_elements(By.TAG_NAME, "a")
            
            print(f"      Found {len(day_buttons)} days to scan.")
            match_ids = []

            for index in range(len(day_buttons)):

                current_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".new-results-list a")
                if index >= len(current_buttons): break
                
                button = current_buttons[index]
                
                text_parts = [span.text for span in button.find_elements(By.TAG_NAME, "span")]
                day_text = " ".join(text_parts).strip()
                
                if not day_text: continue

                print(f"      👉 Clicking Day {index + 1}: {day_text}...", end="")

                # Scroll into view
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});", button)
                time.sleep(0.5)
                del self.driver.requests # Clear logs
                
                try:
                    button.click()
                except:
                    self.driver.execute_script("arguments[0].click();", button)
                time.sleep(1) 

                aux = self._catch_api_response_tournament_matches()
                match_ids.extend(aux)
                print(" Done.")
            for match_id in match_ids:
                del self.driver.requests
                match_stats = self._get_match_stats(match_id)
                if match_stats:
                    enriched_match = self._merge_names_with_draw(match_stats)
                    if enriched_match['match_score']['tournaments_match_id'] in self.existing_matche_ids:
                        print(f"        🔄 Match ID {match_id} already exists. Skipping.")
                        continue
                    self.all_matches.append(enriched_match)

        except Exception as e:
            print(f"   ❌ Error navigating days: {e}")
    
    def _catch_api_response_draw(self):
        start_time = time.time()
        while time.time() - start_time < 5:
            for request in reversed(self.driver.requests):
                if request.response and ("gettournamentsmatchdraw" in request.url):
                    try:
                        body = request.response.body
                        data = json.loads(body.decode('utf-8'))
                        if data.get('status') == 1:
                            return data.get('data')
                    except:
                        pass
            time.sleep(0.2)
        return None

    def _get_match_stats(self, match_id):
        print(f"        - Fetching stats for Match ID: {match_id}")
        try:
            url = f"{PREMIER_PADEL_MATCH_STATS_URL}{match_id}"
            self.driver.get(url)
            time.sleep(2) 
        except Exception as e:
            print(f"   ❌ Could not load matchstats page {match_id}: {e}")
            return
        return self._catch_api_response_match_stats()

    def _catch_api_response_tournament_matches(self):
        found = False
        start_time = time.time()
        check_repeated = []
        tournament_match_ids = []
        
        while time.time() - start_time < 5:
            for request in reversed(self.driver.requests):
                if request.response and "gettournamentsmatchlistnew" in request.url:
                    try:
                        body = request.response.body
                        data = json.loads(body.decode('utf-8'))
                        if data['status'] == 1:
                            found = True
                            matches = []
                            matches.extend(data['data']['main_draw'])
                            matches.extend(data['data']['qualify_draw'])
                            for match in matches:
                                id = match['matchId']
                                if id not in check_repeated:                   
                                    match_id = match['tournaments_match_id']
                                    tournament_match_ids.append(match_id)
                                    check_repeated.append(id)  
                    except:
                        pass
            if found: break
            time.sleep(0.2)
        return tournament_match_ids

    def _catch_api_response_match_stats(self):
        found = False
        start_time = time.time()

        while time.time() - start_time < 5:
            for request in reversed(self.driver.requests):
                if request.response and "gettournamentsmatchdetail" in request.url:
                    try:
                        body = request.response.body
                        data = json.loads(body.decode('utf-8'))
                        
                        if data.get('status') == 1:
                            return data['data']
                        
                    except:
                        pass
            if found: break
            time.sleep(0.2)
        
        if not found:
            print(" ⚠️ No API call (empty month?)")

    @staticmethod
    def _normalize(text):
        clean = unidecode(str(text)).lower().replace(',', '')
        return set(clean.split())
    
    @staticmethod
    def _format_slug(name):
        if not name: 
            return ""
        # Normalize characters (e.g. ñ -> n, á -> a)
        text = unidecode(name).lower()
        # Replace non-alphanumeric characters with hyphens
        text = re.sub(r'[^a-z0-9]+', '-', text)
        # Strip leading/trailing hyphens
        return text.strip('-')
    
    @staticmethod
    def _check_players(short_players, long_players):
        return (
            (short_players['p1'].issubset(long_players['p1']) and short_players['p2'].issubset(long_players['p2'])) or \
            (short_players['p1'].issubset(long_players['p2']) and short_players['p2'].issubset(long_players['p1']))
        )

    def _merge_names_with_draw(self, match_stats):
        if not self.draw_matches:
            return match_stats

        match_score = match_stats.get('match_score', {})
        
        short_team1_p1 = self._normalize(match_score.get('team1_player_name'))
        short_team1_p2 = self._normalize(match_score.get('team1_partner_name'))
        short_team2_p1 = self._normalize(match_score.get('team2_player_name'))
        short_team2_p2 = self._normalize(match_score.get('team2_partner_player_name'))
        
        short_teams = {
            "team_1": {
                "p1": short_team1_p1,
                "p2": short_team1_p2,
            },
            "team_2": {
                "p1": short_team2_p1,
                "p2": short_team2_p2,
            }
        }
        
        for long_teams in self.draw_matches:
            # Direct Match (T1==T1 and T2==T2)
            if self._check_players(short_teams['team_1'], long_teams['team_1']) and \
               self._check_players(short_teams['team_2'], long_teams['team_2']):
                
                match_stats['match_score']['team_1_p1_full_name'] = self._format_slug(long_teams['team_1']['p1_raw'])
                match_stats['match_score']['team_1_p2_full_name'] = self._format_slug(long_teams['team_1']['p2_raw'])
                match_stats['match_score']['team_2_p1_full_name'] = self._format_slug(long_teams['team_2']['p1_raw'])
                match_stats['match_score']['team_2_p2_full_name'] = self._format_slug(long_teams['team_2']['p2_raw']) 
                print("        ✅ Full Names Matched from Draw (Direct).")
                return match_stats

            # Cross Match (T1==T2 and T2==T1)
            elif self._check_players(short_teams['team_1'], long_teams['team_2']) and \
                 self._check_players(short_teams['team_2'], long_teams['team_1']):
                
                match_stats['match_score']['team_1_p1_full_name'] = self._format_slug(long_teams['team_2']['p1_raw'])
                match_stats['match_score']['team_1_p2_full_name'] = self._format_slug(long_teams['team_2']['p2_raw'])
                match_stats['match_score']['team_2_p1_full_name'] = self._format_slug(long_teams['team_1']['p1_raw'])
                match_stats['match_score']['team_2_p2_full_name'] = self._format_slug(long_teams['team_1']['p2_raw'])
                print("        🔀 Full Names Matched from Draw (Swapped).")
                return match_stats

        # No match found
        match_stats['match_score']['team_1_p1_full_name'] = None
        match_stats['match_score']['team_1_p2_full_name'] = None   
        match_stats['match_score']['team_2_p1_full_name'] = None
        match_stats['match_score']['team_2_p2_full_name'] = None
        return match_stats

    def _save_to_json(self):
        if not os.path.exists(RAW_DATA_DIR):
            os.makedirs(RAW_DATA_DIR)   
        with open(RAW_PREMIER_PADEL_MATCHES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.all_matches, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.all_matches)} matches.")
    
if __name__ == "__main__":
    bot = PremierMatchesInterceptor()
    bot.start()