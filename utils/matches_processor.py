import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CLEAN_DATA_DIR,
    MATCHES_FILE,
    RAW_PREMIER_PADEL_MATCHES_FILE
)

class MatchesProcessor:
    def __init__(self):
        self.raw_matches = []
        self.cleaned_matches = []

    def start(self):
        print("🎾 Match Data Processor")
        print("=======================")
        
        self._load_raw_matches()
        if self.raw_matches:
            self._process_all_matches()
            self._save_to_json()
        else:
            print("⚠️ Skipping processing as no raw data was found.")

    def _load_raw_matches(self):
        if os.path.exists(RAW_PREMIER_PADEL_MATCHES_FILE):
            try:
                with open(RAW_PREMIER_PADEL_MATCHES_FILE, "r", encoding="utf-8") as f:
                    self.raw_matches = json.load(f)
                print(f"🔄 Loaded {len(self.raw_matches)} raw matches.")
            except Exception as e:
                print(f"❌ Error loading raw file: {e}")
                self.raw_matches = []
        else:
            print("ℹ️ No existing matches data found.")
            self.raw_matches = []

    def _process_all_matches(self):
        print("⚙️ Processing matches...")
        self.cleaned_matches = []
        for raw_match in self.raw_matches:
            cleaned_match = self._clean_single_match(raw_match)
            if cleaned_match:
                self.cleaned_matches.append(cleaned_match)

    def _clean_single_match(self, raw_match):
        try:
            # Extract Basic Match Info
            raw_match_score = raw_match.get("match_score", {})
            if raw_match_score.get("is_bye") == "Yes" or (not raw_match_score.get("team_1_p1_full_name") or not raw_match_score.get("team_2_p1_full_name") or not raw_match_score.get("team_1_p2_full_name") or not raw_match_score.get("team_2_p2_full_name")):
                return None  # Skip bye matches
            team1_slug = '-'.join(sorted([raw_match_score.get("team_1_p1_full_name"), raw_match_score.get("team_1_p2_full_name")]))
            team2_slug = '-'.join(sorted([raw_match_score.get("team_2_p1_full_name"), raw_match_score.get("team_2_p2_full_name")]))
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

            # Natch stats are inside match_state, so first check if it exists
            match_state = raw_match.get("match_state")

            if not match_state:
                cleaned_match["match_stats"] = None
                return cleaned_match
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
                    stats_output[f"{prefix}_team1_longest_point_streak"] = total_points_list[3].get("team_1", {}).get("title")
                    stats_output[f"{prefix}_team2_longest_point_streak"] = total_points_list[3].get("team_2", {}).get("title")

            for team in ["team1", "team2"]:
                for serve_type in ["first", "second"]:
                    won = match_totals[team][f"{serve_type}_serve_won"]
                    played = match_totals[team][f"{serve_type}_serve_played"]
                    pct = (won / played * 100) if played > 0 else 0
                    
                    stats_output[f"match_{team}_{serve_type}_serve_points_won"] = won
                    stats_output[f"match_{team}_{serve_type}_serve_points_played"] = played
                    stats_output[f"match_{team}_{serve_type}_serve_points_percentage"] = round(pct, 2)

            cleaned_match["match_stats"] = stats_output
            return cleaned_match
            
        except Exception as e:
            print(f"⚠️ Error cleaning match ID {raw_match.get('matchId', 'Unknown')}: {e}")
            return None

    def _save_to_json(self):
        if not os.path.exists(CLEAN_DATA_DIR):
            os.makedirs(CLEAN_DATA_DIR)
        try:
            with open(MATCHES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cleaned_matches, f, indent=4, ensure_ascii=False)
            print(f"💾 Saved {len(self.cleaned_matches)} cleaned matches to {MATCHES_FILE}.")
        except Exception as e:
            print(f"❌ Error saving cleaned file: {e}")

if __name__ == "__main__":
    processor = MatchesProcessor()
    processor.start()