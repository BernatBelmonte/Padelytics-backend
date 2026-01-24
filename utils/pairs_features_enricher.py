import json
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MATCHES_FILE,
    DYNAMIC_PAIRS_FILE,
    DYNAMIC_PAIRS_FEATURED_FILE
)

class PairsFeaturesEnricher:
    def __init__(self):
        self.pairs_data = []    
        self.matches_data = []  
        self.match_lookup = {}
        self.history_tracker = {}     
        self.partnership_tracker = {} 

    def start(self):
        print("🚀 Pairs Enricher ")
        print("==================")
        
        if not self._load_data():
            return

        self._index_matches()
        self._enrich_data()
        self._save_data()

    def _load_data(self):
        try:
            with open(DYNAMIC_PAIRS_FILE, 'r', encoding='utf-8') as f:
                self.pairs_data = json.load(f)
            self.pairs_data.sort(key=lambda x: x.get('timestamp', ''))

            if os.path.exists(MATCHES_FILE):
                 with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
                    self.matches_data = json.load(f)
            else:
                self.matches_data = []

            print(f"📚 Loaded: {len(self.pairs_data)} rankings & {len(self.matches_data)} matches.")
            return True
        except Exception as e:
            print(f"❌ Error loading files: {e}")
            return False

    def _index_matches(self):
        print("⚙️  Indexing matches...")
        for m in self.matches_data:
            slug_t1 = m.get('team1_slug')
            slug_t2 = m.get('team2_slug')
            date_str = m.get('date')
            if not date_str: continue

            match_obj = {
                'date': date_str,
                'tournament_id': m.get('tournament_id'),
                'winner_id': str(m.get('winner_team')), 
                'round_name': m.get('round_name'),
                'team1_score': m.get('team1_score'),
                'team2_score': m.get('team2_score')
            }

            if slug_t1:
                if slug_t1 not in self.match_lookup: self.match_lookup[slug_t1] = []
                self.match_lookup[slug_t1].append({**match_obj, 'my_role': '1'})

            if slug_t2:
                if slug_t2 not in self.match_lookup: self.match_lookup[slug_t2] = []
                self.match_lookup[slug_t2].append({**match_obj, 'my_role': '2'})

    @staticmethod
    def _get_round_weight(round_name):
        if not round_name: return 1
        r = str(round_name).lower().strip()
        
        if 'final' in r or r.endswith(' f') or r == 'f': 
            return 6 
        if 'semi' in r or 'sf' in r: 
            return 5
        if 'quarter' in r or 'qf' in r: 
            return 4
        if '16' in r: 
            return 3
        if '32' in r: 
            return 2
        return 1 # Early Rounds

    def _enrich_data(self):
        print("🧪 Calculating Features...")
        
        for group in self.pairs_data:
            timestamp = group.get('timestamp')
            pairs_list = group.get('pairs', [])
            if not pairs_list: continue

            try:
                ts_date = datetime.strptime(str(timestamp).split(' ')[0], "%Y-%m-%d").date()
                ts_year = ts_date.year
            except: continue

            try:
                leader_points = max(float(str(p.get('total_points', 0)).replace(',', '')) for p in pairs_list)
            except: leader_points = 0

            for pair in pairs_list:
                slug = pair.get('pair_slug')
                if not slug: continue

                # Context
                try: curr_points = float(str(pair.get('total_points', 0)).replace(',', ''))
                except: curr_points = 0
                curr_rank = pair.get('rank')

                pair['points_behind_leader'] = leader_points - curr_points
                pair['is_number_one'] = (curr_rank == 1)

                # History
                if slug in self.history_tracker:
                    prev = self.history_tracker[slug]
                    pair['rank_change'] = (prev['rank'] - curr_rank) if (prev['rank'] and curr_rank) else 0
                    pair['points_change'] = curr_points - prev['points']
                    pair['is_new_pair'] = False
                else:
                    pair['rank_change'] = 0
                    pair['points_change'] = 0
                    pair['is_new_pair'] = True
                
                self.history_tracker[slug] = {'rank': curr_rank, 'points': curr_points}

                # Chemistry
                if slug not in self.partnership_tracker:
                    self.partnership_tracker[slug] = {'start_date': ts_date, 'count': 0}
                chem = self.partnership_tracker[slug]
                pair['partnership_time_days'] = (ts_date - chem['start_date']).days
                pair['tournaments_played_together'] = chem['count']
                chem['count'] += 1

                # Init Metrics
                pair['form_guide'] = "N/A"
                pair['streak_numeric'] = 0
                pair['matches_last_14_days'] = 0
                pair['days_since_last_match'] = None
                pair['average_round_value'] = 0
                pair['finals_conversion_rate'] = 0

                # Stats Season
                pair['season_matches_played'] = 0
                pair['season_win_pct'] = 0
                pair['stats_confidence'] = 0.0
                pair['dominance_ratio'] = 0
                pair['straight_sets_win_rate'] = 0
                pair['avg_games_conceded_per_set'] = 0
                pair['tie_break_win_pct'] = 0
                pair['closing_efficiency'] = 0 
                pair['comeback_rate'] = 0

                if slug in self.match_lookup:
                    all_matches = self.match_lookup[slug]
                    past_matches = []
                    season_matches = []

                    for m in all_matches:
                        try:
                            m_date = datetime.strptime(m['date'], "%Y-%m-%d").date()
                            if m_date < ts_date:
                                past_matches.append(m)
                                if m_date.year == ts_year:
                                    season_matches.append(m)
                        except: pass
                    
                    past_matches.sort(key=lambda x: x['date'], reverse=True)

                    if past_matches:
                        # Form Guide
                        form = []
                        for m in past_matches[:5]:
                            is_win = (str(m['winner_id']) == str(m['my_role']))
                            form.append("W" if is_win else "L")
                        pair['form_guide'] = "-".join(form)

                        # Rust
                        last_match_date = datetime.strptime(past_matches[0]['date'], "%Y-%m-%d").date()
                        pair['days_since_last_match'] = (ts_date - last_match_date).days

                        # Streak
                        current_streak = 0
                        for m in past_matches:
                            is_win = (str(m['winner_id']) == str(m['my_role']))
                            if is_win: current_streak += 1
                            else: break 
                        pair['streak_numeric'] = current_streak

                        # Fatigue
                        date_14_days_ago = ts_date - timedelta(days=14)
                        matches_14d = sum(1 for m in past_matches 
                                          if datetime.strptime(m['date'], "%Y-%m-%d").date() >= date_14_days_ago)
                        pair['matches_last_14_days'] = matches_14d

                        tournament_results = {} # {t_id: max_round_value}
                        
                        for m in past_matches:
                            t_id = m['tournament_id']
                            r_val = self._get_round_weight(m['round_name'])
                            
                            if t_id not in tournament_results:
                                tournament_results[t_id] = r_val
                            else:
                                if r_val > tournament_results[t_id]:
                                    tournament_results[t_id] = r_val

                        last_5_tournament_values = []
                        seen_tournaments = set()
                        
                        for m in past_matches:
                            t_id = m['tournament_id']
                            if t_id not in seen_tournaments:
                                val = tournament_results[t_id]
                                last_5_tournament_values.append(val)
                                seen_tournaments.add(t_id)
                                
                                if len(last_5_tournament_values) == 5:
                                    break
                        
                        if last_5_tournament_values:
                            pair['average_round_value'] = round(sum(last_5_tournament_values) / len(last_5_tournament_values), 1)

                        # Finals Conversion Rate   
                        f_played = 0
                        f_won = 0
                        for m in past_matches:
                            if self._get_round_weight(m['round_name']) == 6:
                                f_played += 1
                                if str(m['winner_id']) == str(m['my_role']):
                                    f_won += 1
                        
                        if f_played > 0:
                            pair['finals_conversion_rate'] = (f_won / f_played)

                    # Season Stats
                    total_wins = 0
                    total_games_won = 0
                    total_games_lost = 0
                    total_straight_set_wins = 0
                    total_sets_played = 0
                    tb_played = 0
                    tb_won = 0
                    won_set1_count = 0
                    closed_match_count = 0
                    lost_set1_count = 0
                    comeback_count = 0

                    for m in season_matches:
                        is_win = (str(m['winner_id']) == str(m['my_role']))
                        if is_win: total_wins += 1

                        my_score = m['team1_score'] if m['my_role'] == '1' else m['team2_score']
                        opp_score = m['team2_score'] if m['my_role'] == '1' else m['team1_score']
                        
                        match_games_w = 0
                        match_games_l = 0
                        match_sets_w = 0
                        match_sets_l = 0
                        first_set_processed = False
                        
                        if my_score and opp_score:
                            for i in range(1, 6):
                                try:
                                    s_me = int(my_score.get(f'set{i}') or 0)
                                    s_op = int(opp_score.get(f'set{i}') or 0)
                                    if s_me == 0 and s_op == 0: continue
                                    
                                    if not first_set_processed:
                                        if s_me > s_op:
                                            won_set1_count += 1
                                            if is_win: closed_match_count += 1
                                        elif s_op > s_me:
                                            lost_set1_count += 1
                                            if is_win: comeback_count += 1
                                        first_set_processed = True

                                    match_games_w += s_me
                                    match_games_l += s_op
                                    
                                    if s_me > s_op: match_sets_w += 1
                                    elif s_op > s_me: match_sets_l += 1
                                    
                                    if (s_me == 7 and s_op == 6) or (s_me == 6 and s_op == 7):
                                        tb_played += 1
                                        if s_me == 7: tb_won += 1
                                except: pass
                        
                        total_games_won += match_games_w
                        total_games_lost += match_games_l
                        total_sets_played += (match_sets_w + match_sets_l)

                        if is_win and match_sets_l == 0 and match_sets_w == 2:
                            total_straight_set_wins += 1

                    match_count = len(season_matches)
                    pair['season_matches_played'] = match_count
                    
                    if match_count > 0:
                        pair['stats_confidence'] = round(match_count / (match_count + 10), 2)
                        pair['season_win_pct'] = round((total_wins / match_count * 100), 2)

                    if (total_games_won + total_games_lost) > 0:
                        pair['dominance_ratio'] = round((total_games_won / (total_games_won + total_games_lost)), 3)

                    if total_wins > 0:
                        pair['straight_sets_win_rate'] = round((total_straight_set_wins / total_wins * 100), 2)

                    if total_sets_played > 0:
                        pair['avg_games_conceded_per_set'] = round((total_games_lost / total_sets_played), 2)
                    
                    if tb_played > 0:
                        pair['tie_break_win_pct'] = round((tb_won / tb_played * 100), 2)
                    
                    if won_set1_count > 0:
                        pair['closing_efficiency'] = round((closed_match_count / won_set1_count * 100), 2)
                    
                    if lost_set1_count > 0:
                        pair['comeback_rate'] = (comeback_count / lost_set1_count)

    def _save_data(self):
        try:
            with open(DYNAMIC_PAIRS_FEATURED_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.pairs_data, f, indent=4, ensure_ascii=False)
            print(f"💾 Saved Enriched Data: {DYNAMIC_PAIRS_FEATURED_FILE}")
        except Exception as e:
            print(f"❌ Error saving: {e}")

if __name__ == "__main__":
    enricher = PairsFeaturesEnricher()
    enricher.start()