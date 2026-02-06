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


# --- CONFIGURATION ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    PREMIER_PADEL_RESULTS_URL,
    PREMIER_PADEL_MATCH_STATS_URL,
    
)  

class PremierMatchesScraper:
    """Scraper for Premier Padel matches data."""

    def __init__(self, existing_matches, tournaments):
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless") # Keep visible to debug
    
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.existing_matches = existing_matches
        self.existing_match_ids = [m['tournaments_match_id'] for m in existing_matches]
        self.tournament_slugs = [t['slug'] for t in tournaments]
        self.all_matches = [] 
        self.cleaned_matches = []
        self.draw_contestants = {}
        self.qualy_contestants = {}
        self.draw_matches = []

    def run(self):
        """Main method to start scraping matches."""
        print("🏓 Premier Padel Matches Scraper")
        print("==================================")
        tournaments_id_scraped = []
        try:
            for slug in self.tournament_slugs:
                success = self._process_tournament_slug(slug)
                if success:
                    tournaments_id_scraped.append(slug)
                    
            self.all_matches.extend(self.existing_matches)
        except Exception as e:
            print(f"❌ Critical Error: {e}")
        finally:
            self.driver.quit()
        self._process_all_matches()
        return self.cleaned_matches, tournaments_id_scraped

    def _process_tournament_slug(self, slug):
        print(f"\n📅 TOURNAMENT SLUG: {slug}")
        enriched_count = 0
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
                    self.qualy_contestants = quali_data.get('contestants', {})
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
                    print(f"      ✅ Draw Qualy Data Captured ({len(self.qualy_contestants)} contestants)")
                else:
                    print("      ⚠️ Draw API not found or empty.")
            else:
                print("      ℹ️ No Qualification tab found.")
        
        except Exception as e:
            print(f"      ⚠️ Quali tab interaction failed: {e}")

        print(f"      ✅ Total Contestants: {len(self.draw_contestants) + len(self.qualy_contestants)} | Total Draw Matches: {len(self.draw_matches)}")

        
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
                    if enriched_match['match_score']['tournaments_match_id'] in self.existing_match_ids:
                        print(f"        🔄 Match ID {match_id} already exists. Skipping.")
                        continue
                    enriched_count += 1
                    self.all_matches.append(enriched_match)

        except Exception as e:
            print(f"   ❌ Error navigating days: {e}")

        return True if enriched_count > 0 else False
    
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

    def _process_all_matches(self):
        print("⚙️ Processing matches...")
        for raw_match in self.all_matches:
            cleaned_match = self._clean_single_match(raw_match)
            if cleaned_match:
                self.cleaned_matches.append(cleaned_match)

    def _clean_single_match(self, raw_match):
        try:
            # Extract Basic Match Info
            raw_match_score = raw_match.get("match_score", {})
            if raw_match_score.get("is_bye") == "Yes" or (not raw_match_score.get("team_1_p1_full_name") or not raw_match_score.get("team_2_p1_full_name") or not raw_match_score.get("team_1_p2_full_name") or not raw_match_score.get("team_2_p2_full_name")):
                return None  # Skip bye matches
            team1_slug = '/'.join(sorted([raw_match_score.get("team_1_p1_full_name"), raw_match_score.get("team_1_p2_full_name")]))
            team2_slug = '/'.join(sorted([raw_match_score.get("team_2_p1_full_name"), raw_match_score.get("team_2_p2_full_name")]))
            cleaned_match = {
                "tournaments_match_id": raw_match_score.get("tournaments_match_id"),
                "tournament_id": raw_match_score.get("tournaments_id"),
                "tournament_name": raw_match_score.get("tournament_name"),
                "date": raw_match_score.get("date"),
                "start_time": raw_match_score.get("start_time"),
                "matchId": raw_match_score.get("matchId"),
                "team1_slug": team1_slug,
                "team1_player1": raw_match_score.get("team1_player_name"),
                "team1_player1_slug": raw_match_score.get("team_1_p1_full_name"),
                "team1_player2": raw_match_score.get("team1_partner_name"),
                "team1_player2_slug": raw_match_score.get("team_1_p2_full_name"),
                "team2_slug": team2_slug,
                "team2_player1": raw_match_score.get("team2_player_name"),
                "team2_player1_slug": raw_match_score.get("team_2_p1_full_name"),
                "team2_player2": raw_match_score.get("team2_partner_player_name"),
                "team2_player2_slug": raw_match_score.get("team_2_p2_full_name"),
                "is_bye": raw_match_score.get("is_bye"),
                "round": raw_match_score.get("round"),
                "round_name": raw_match_score.get("round_name"),
                "winner_team": raw_match_score.get("winner_id"),
                "team1_score": raw_match_score.get("team1_score"),
                "team2_score": raw_match_score.get("team2_score"),
            }

            # Match stats are inside match_state, so first check if it exists
            match_state = raw_match.get("match_state")

            if not match_state:
                cleaned_match["match_stats"] = None
            else:
                stats_output = {}
                # Although 7 sets are displayed in the data, only a maximum of 3 sets are played in Padel
                set_prefix_map = {
                    "set 1": "firstset",
                    "set 2": "secondset",
                    "set 3": "thirdset"
                }

                stat_type_map = {
                    "First Serve Points Won": "first_serve_points",
                    "Second Serve Points Won": "second_serve_points"
                }

                # Initialize accumulators
                match_totals = {
                    "team1": {"first_serve_won": 0, "first_serve_played": 0, "second_serve_won": 0, "second_serve_played": 0},
                    "team2": {"first_serve_won": 0, "first_serve_played": 0, "second_serve_won": 0, "second_serve_played": 0}
                }

                for part_stats in match_state:
                    set_title = part_stats.get("title")
                    prefix = set_prefix_map.get(set_title)

                    if not prefix:
                        continue 

                    # Service Stats
                    for service in part_stats.get("service", []):
                        stat_title = service.get("title")
                        base_stat_name = stat_type_map.get(stat_title)

                        if base_stat_name:
                            for team_key, team_num in [("team_1", "team1"), ("team_2", "team2")]:
                                data = service.get(team_key, {})
                                won = data.get("won", 0)
                                played = data.get("played", 0)
                                percentage = data.get("percentage", 0)

                                stats_output[f"{prefix}_{team_num}_{base_stat_name}_won"] = won
                                stats_output[f"{prefix}_{team_num}_{base_stat_name}_played"] = played
                                stats_output[f"{prefix}_{team_num}_{base_stat_name}_percentage"] = percentage

                                match_totals[team_num][f"{base_stat_name.split('_')[0]}_serve_won"] += int(won or 0)
                                match_totals[team_num][f"{base_stat_name.split('_')[0]}_serve_played"] += int(played or 0)

                    # Longest Streak
                    total_points_list = part_stats.get("total_points", [])
                    if len(total_points_list) > 3:
                        stats_output[f"{prefix}_team1_longest_point_streak"] = int(total_points_list[3].get("team_1", {}).get("title"))
                        stats_output[f"{prefix}_team2_longest_point_streak"] = int(total_points_list[3].get("team_2", {}).get("title"))

                for team in ["team1", "team2"]:
                    for serve_type in ["first", "second"]:
                        won = match_totals[team][f"{serve_type}_serve_won"]
                        played = match_totals[team][f"{serve_type}_serve_played"]
                        pct = (won / played * 100) if played > 0 else 0
                        
                        stats_output[f"match_{team}_{serve_type}_serve_points_won"] = won
                        stats_output[f"match_{team}_{serve_type}_serve_points_played"] = played
                        stats_output[f"match_{team}_{serve_type}_serve_points_percentage"] = round(pct, 2)

                cleaned_match["match_stats"] = stats_output
            
            return self._prepare_match(cleaned_match)
            
        except Exception as e:
            print(f"⚠️ Error cleaning match ID {raw_match.get('matchId', 'Unknown')}: {e}")
            return None
    @staticmethod
    def _prepare_match(match):
        stats_columns = [
            "firstset_team1_first_serve_points_won",
            "firstset_team1_first_serve_points_played",
            "firstset_team1_first_serve_points_percentage",
            "firstset_team2_first_serve_points_won",
            "firstset_team2_first_serve_points_played",
            "firstset_team2_first_serve_points_percentage",
            "firstset_team1_second_serve_points_won",
            "firstset_team1_second_serve_points_played",
            "firstset_team1_second_serve_points_percentage",
            "firstset_team2_second_serve_points_won",
            "firstset_team2_second_serve_points_played",
            "firstset_team2_second_serve_points_percentage",
            "firstset_team1_longest_point_streak",
            "firstset_team2_longest_point_streak",
            "secondset_team1_first_serve_points_won",
            "secondset_team1_first_serve_points_played",
            "secondset_team1_first_serve_points_percentage",
            "secondset_team2_first_serve_points_won",
            "secondset_team2_first_serve_points_played",
            "secondset_team2_first_serve_points_percentage",
            "secondset_team1_second_serve_points_won",
            "secondset_team1_second_serve_points_played",
            "secondset_team1_second_serve_points_percentage",
            "secondset_team2_second_serve_points_won",
            "secondset_team2_second_serve_points_played",
            "secondset_team2_second_serve_points_percentage",
            "secondset_team1_longest_point_streak",
            "secondset_team2_longest_point_streak",
            "match_team1_first_serve_points_won",
            "match_team1_first_serve_points_played",
            "match_team1_first_serve_points_percentage",
            "match_team1_second_serve_points_won",
            "match_team1_second_serve_points_played",
            "match_team1_second_serve_points_percentage",
            "match_team2_first_serve_points_won",
            "match_team2_first_serve_points_played",
            "match_team2_first_serve_points_percentage",
            "match_team2_second_serve_points_won",
            "match_team2_second_serve_points_played",
            "match_team2_second_serve_points_percentage"
        ]
        match['winner_team'] = int(match['winner_team']) if match['winner_team'] is not None else None
        if 'team1_score' in match:
            match['team1_set1'] = match['team1_score'].get('set1')
            match['team1_set2'] = match['team1_score'].get('set2')
            match['team1_set3'] = match['team1_score'].get('set3')
            del match['team1_score']
        if 'team2_score' in match:
            match['team2_set1'] = match['team2_score'].get('set1')
            match['team2_set2'] = match['team2_score'].get('set2')
            match['team2_set3'] = match['team2_score'].get('set3')
            del match['team2_score']
        if match['match_stats'] is not None:
            match.update(match.pop("match_stats"))
        elif match['match_stats'] is None:
            for col in stats_columns:
                match[col] = None
        columns_to_delete = ['tournament_name', 'start_time', 'matchId', 'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2', 'round', 'is_bye', 'match_stats']
        for col in columns_to_delete:
            if col in match:
                del match[col]
        return match
            
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
