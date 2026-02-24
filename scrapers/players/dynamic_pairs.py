import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from supabase import create_client, Client

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL,
    SUPABASE_KEY
)

class DynamicPairsProcessor:
    """
    The DynamicPairsProcessor class is responsible for processing player pair data to calculate 
    advanced KPIs and prepare the data for storage in the database. It identifies player pairs 
    based on their slugs, fetches their match history, calculates various performance metrics, 
    and prepares a final payload that includes both the calculated KPIs and historical comparisons.
    ALERT: stats are calculated based on matches from 1 year back until the snapshot date, this is to 
    ensure that the KPIs reflect the current form and performance of the pairs, rather than being skewed 
    by older matches that may not be indicative of their current level.
    
    """
    def __init__(self):
        """
        Initializes the DynamicPairsProcessor with a Supabase client for database interactions and a predefined set of round weights for KPI calculations.
        """
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.round_weights = {
            'Men F': 10, 'Men SF': 8, 'Men QF': 6,
            'Men R16': 4, 'Men R32': 2, 'Men R64': 1,
            'Men Q3':0.75, 'Men Q2':0.50, 'Men Q1':0.25    
        }

    def run(self, scraped_players: List[Dict], snapshot_date_str: str) -> List[Optional[Dict]]:
        """
        The main method to process dynamic player pair data. It identifies pairs, fetches their match history,
        calculates advanced KPIs, and prepares the final payload for database storage.
        Args:
            scraped_players: A list of dictionaries containing scraped player data, including their slugs and points.
            snapshot_date_str: A string representing the snapshot date for which the KPIs are being calculated, in the format "YYYY-MM-DD".
        Returns:
            A list of dictionaries containing the processed pair data with calculated KPIs and historical comparisons, ready
        """
        print(f"Calculating Dynamic Pairs Stats for {snapshot_date_str}...")
        pairs_data = self._identify_pairs(scraped_players)
        if not pairs_data:
            return []

        leader_points = max(p['points'] for p in pairs_data.values())
        
        # Sort pairs by points descending to assign rankings
        sorted_pairs = sorted(pairs_data.items(), key=lambda x: x[1]['points'], reverse=True)
        pair_rankings = {pair_slug: rank + 1 for rank, (pair_slug, _) in enumerate(sorted_pairs)}
        
        final_payload = []
        for pair_slug, base_info in pairs_data.items():
            print(f"    📈 Processing {pair_slug}...")

            matches = self._fetch_pair_matches(pair_slug, snapshot_date_str)
            print(f"        Found {len(matches)} matches for {pair_slug} from 1 year back until {snapshot_date_str}.")
            prev_snapshot = self._fetch_previous_pair_stat(pair_slug, snapshot_date_str)
            kpis = self._calculate_advanced_kpis(pair_slug, matches, snapshot_date_str)
            
            current_ranking = pair_rankings[pair_slug]
            
            record = {
                "pair_slug": pair_slug,
                "player1_slug": pair_slug.split("--")[0],
                "player2_slug": pair_slug.split("--")[1],
                "snapshot_date": snapshot_date_str,
                "points": base_info['points'],
                "points_behind_leader": leader_points - base_info['points'],
                "is_number_one": base_info['is_no1'],
                "ranking": current_ranking,
                **kpis
            }

            if prev_snapshot:
                record["points_change"] = int(base_info['points'] - prev_snapshot.get('points', 0)) # type: ignore
                record["is_new_pair"] = False
                prev_ranking = prev_snapshot.get('ranking')
                if prev_ranking is not None:
                    record["ranking_change"] = prev_ranking - current_ranking  # Positive means improved
                else:
                    record["ranking_change"] = None
            else:
                record["points_change"] = None
                record["is_new_pair"] = True
                record["ranking_change"] = None

            final_payload.append(record)

        return final_payload

    def _identify_pairs(self, players: List[Dict]) -> Dict[str, Dict]:
        """
        Identifies player pairs based on their slugs and calculates their combined points
        Args:
            players: A list of dictionaries containing player data
        Returns:
            A dictionary where the keys are pair slugs (formatted as "player1--player2") and the values are dictionaries containing the combined points and number one status of the pair.
        """
        pairs = {}
        processed_slugs = set()

        for p in players:
            slug = p['slug']
            partner = p['paired_with_slug']
            if not partner or slug in processed_slugs: continue

            # Canonical slug (Alphabetical)
            pair_slug = "--".join(sorted([slug, partner]))
            if partner not in [pl['slug'] for pl in players]: continue  # Skip if partner data is missing
            partner_data = next((x for x in players if x['slug'] == partner), None)
            total_pts = p.get('points', 0) + (partner_data.get('points', 0) if partner_data else 0)
            
            pairs[pair_slug] = {
                "points": total_pts,
                "is_no1": p['ranking_position'] == 1 or (partner_data and partner_data.get('ranking_position') == 1),
            }
            processed_slugs.update([slug, partner])
        return pairs


    def _fetch_pair_matches(self, pair_slug: str, date_str: str) -> List[Dict]:
        """
        Fetches the match history for a given player pair from back util a year up until a specified date.
            pair_slug: A string representing the slug of the player pair (formatted as "player1--player2") for which to fetch match history.
            date_str: A string representing the cutoff date (in "YYYY-MM-DD" format) for fetching matches, ensuring that only matches before this date are included in the results.
        Returns:
            A list of dictionaries containing the match data for the specified player pair, including details such as match date, tournament, round, and scores.
        """
        all_matches = []
        limit = 1000
        offset = 0

        while True:
            # Fetch matches from 1 year back from the snapshot date
            one_year_ago = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=365)
            one_year_ago_str = one_year_ago.strftime("%Y-%m-%d")

            res = self.supabase.table("matches").select("*")\
            .or_(f"team1_slug.eq.{pair_slug},team2_slug.eq.{pair_slug}")\
            .lt("date", date_str)\
            .gte("date", one_year_ago_str)\
            .order("date", desc=False).execute()
            
            data = res.data
            all_matches.extend(data)
            
            if len(data) < limit:
                break
            offset += limit

        return all_matches

    def _fetch_previous_pair_stat(self, pair_slug: str, date_str: str) -> Optional[Dict]:
        """
        Fetches the most recent previous statistics for a given player pair before a specified date. 
        Args:
            pair_slug: A string representing the slug of the player pair (formatted as "player1--player2") for which to fetch previous statistics.
            date_str: A string representing the cutoff date (in "YYYY-MM-DD" format) for fetching previous statistics, ensuring that only records with a snapshot date before this date are considered.
        Returns:
            A dictionary containing the most recent previous statistics for the specified player pair, or None if no such record exists in the database.
        """
        res = self.supabase.table("dynamic_pairs").select("*")\
            .eq("pair_slug", pair_slug)\
            .lt("snapshot_date", date_str)\
            .order("snapshot_date", desc=True).limit(1).execute()
        return res.data[0] if res.data else None # type: ignore

    def _calculate_advanced_kpis(self, pair_slug: str, matches: List[Dict], snapshot_date_str: str) -> Dict:
        """
        Calculates a comprehensive set of advanced KPIs for a given player pair based on their match history from 1 year back until the snapshot date. 
        The KPIs include performance metrics such as win percentage, dominance ratio, form guide, and more, 
        providing a detailed analysis of the pair's performance over time.
        Args:
            pair_slug: A string representing the slug of the player pair (formatted as "player1--player2") for which to calculate KPIs.
            matches: A list of dictionaries containing the match history for the player pair, including details such as match date, tournament, round, and scores.
            snapshot_date_str: A string representing the snapshot date for which the KPIs are being calculated, in the format "YYYY-MM-DD".
        Returns:
            A dictionary containing the calculated KPIs for the specified player pair, including metrics such as form guide, win percentage, dominance ratio, and confidence level of the statistics based on match volume and tournament variety.
        """
        
        stats = {
            "form_guide": "", "streak_numeric": 0, "matches_last_14_days": 0,
            "matches_played": len(matches), "win_pct": 0,
            "dominance_ratio": 0, "straight_sets_win_rate": 0,
            "avg_games_conceded_per_set": 0, "tie_break_win_pct": 0,
            "closing_efficiency": 0, "comeback_rate": 0, "average_round_value": 0,
            "partnership_time_days": 0, "tournaments_played_together": 0,
            "days_since_last_match": 0, 'finals_conversion_rate': 0, "stats_confidence": 0  # default confidence level
        }

        MATCH_THRESHOLD = 30 # Threshold for number of matches to consider stats fully reliable
        TOURNEY_THRESHOLD = 5 # Threshold for number of unique tournaments to consider stats fully reliable

        if not matches: return stats

        wins, sets_won, sets_lost, games_won, games_lost = 0, 0, 0, 0, 0
        tb_won, tb_played = 0, 0
        straight_sets_wins = 0
        closing_attempts, closing_wins = 0, 0
        comeback_attempts, comeback_wins = 0, 0
        finals_played, finals_won = 0, 0
        total_round_weight = 0
        streak_val = 0
        first_match_won = None
        
        snap_date = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
        form = []

        match_dates = []
        unique_tournaments = set()
        tournament_max_weights = {}

        # Sort matches by date first
        sorted_matches = sorted(matches, key=lambda x: x['date'])
        stint_start = sorted_matches[0]['date'].split(' ')[0]
        stint_start = datetime.strptime(stint_start, "%Y-%m-%d") # Initialize stint start to the date of the first match in the sorted list

        # Define what counts as a "breakup" (e.g., 6 months of no matches)
        GAP_THRESHOLD = 180 

        for i, m in enumerate(sorted_matches):
            is_team1 = m['team1_slug'] == pair_slug
            # Whether the pair won the match
            won_match = (is_team1 and m['winner_team'] == 1) or (not is_team1 and m['winner_team'] == 2)

            current_match = m['date'].split(' ')[0] # Ensure date is in "YYYY-MM-DD" format
            previous_match = sorted_matches[i-1]['date'].split(' ')[0] if i > 0 else current_match
            current_match = datetime.strptime(current_match, "%Y-%m-%d")
            previous_match = datetime.strptime(previous_match, "%Y-%m-%d")
            if (current_match - previous_match).days > GAP_THRESHOLD:
                stint_start = current_match # Reset start date to the reunion

            if i == 0:
                first_match_won = won_match
                streak_val = 1
            elif won_match == first_match_won:
                streak_val += 1

            if i + 1 == streak_val:
                stats["streak_numeric"] = streak_val if first_match_won else -streak_val

            if won_match: wins += 1
            if len(sorted_matches) - i <= 10: form.append("W" if won_match else "L")
            
            if m['round_name'] == 'Men F':
                finals_played += 1
                if won_match: finals_won += 1
            # 14 day form metric
            match_date = datetime.strptime(m['date'], "%Y-%m-%d")
            match_dates.append(match_date)
            t_id = m.get('tournament_id')
            if t_id: unique_tournaments.add(t_id)
            
            current_round_weight = self.round_weights.get(m['round_name'], 0)
        
            if t_id not in tournament_max_weights or current_round_weight > tournament_max_weights[t_id]:
                tournament_max_weights[t_id] = current_round_weight

            if (snap_date - match_date).days <= 14: 
                stats["matches_last_14_days"] += 1

            # Sets and games calculation
            m_sets_won, m_sets_lost = 0, 0
            first_set_won = None
            for s in range(1, 4):
                s1 = m.get(f"team1_set{s}")
                s2 = m.get(f"team2_set{s}")
                if s1 is None or s2 is None: continue
                
                my_score = s1 if is_team1 else s2
                opp_score = s2 if is_team1 else s1
                
                games_won += my_score
                games_lost += opp_score
                
                if my_score > opp_score: 
                    m_sets_won += 1
                    if s == 1: 
                        closing_attempts += 1 # Win or lose the first set is what creates the closing/comeback opportunities
                        first_set_won = True
                else: 
                    m_sets_lost += 1
                    if s == 1: 
                        comeback_attempts += 1 # If you lose the first set, you have to mount a comeback to win the match
                        first_set_won = False
                
                # Tie breaks
                if my_score >= 6 and opp_score >= 6:
                    tb_played += 1
                    if my_score > opp_score: tb_won += 1

            sets_won += m_sets_won
            sets_lost += m_sets_lost
            
            if won_match and m_sets_lost == 0 and m_sets_won > 0: straight_sets_wins += 1
            if won_match and first_set_won is True:
                closing_wins += 1
            if won_match and first_set_won is False:
                comeback_wins += 1
                
            total_round_weight += self.round_weights.get(m['round_name'], 0.25)

        num_tournaments = len(tournament_max_weights)
        num_matches = len(matches)
        if num_tournaments > 0:
            total_top_weights = sum(tournament_max_weights.values())
            stats["average_round_value"] = round(total_top_weights / num_tournaments, 2)

        if match_dates:
            today = datetime.now()
            latest_match = max(sorted_matches, key=lambda x: x['date'])['date']
            latest_match = datetime.strptime(latest_match.split(' ')[0], "%Y-%m-%d")
            
            stats["partnership_time_days"] = (today - stint_start).days
            stats["days_since_last_match"] = (today - latest_match).days
            stats["tournaments_played_together"] = len(unique_tournaments)
            
        # Final KPI calculations
        stats["form_guide"] = "-".join(form)
        stats["win_pct"] = round((wins / len(matches)) * 100, 2) if matches else None
        stats["dominance_ratio"] = round(games_won / games_lost, 2) if games_lost > 0 else None
        stats["straight_sets_win_rate"] = round((straight_sets_wins / len(matches)) * 100, 2) if matches else None
        stats["avg_games_conceded_per_set"] = round(games_lost / (sets_won + sets_lost), 2) if (sets_won + sets_lost) > 0 else None
        stats["tie_break_win_pct"] = round((tb_won / tb_played) * 100, 2) if tb_played > 0 else None
        stats["closing_efficiency"] = round((closing_wins / closing_attempts) * 100, 2) if closing_attempts > 0 else None
        stats["comeback_rate"] = round((comeback_wins / comeback_attempts) * 100, 2) if comeback_attempts > 0 else None
        stats["finals_conversion_rate"] = round((finals_won / finals_played) * 100, 2) if finals_played > 0 else None

        # Confidence heuristic based on match volume and tournament variety
        # this helps to contextualize the reliability of the calculated KPIs,
        # especially for newer pairs with limited data. The confidence score 
        # is a weighted combination of the match volume score and the tournament 
        # variety score, providing a percentage that indicates how much trust 
        # can be placed in the statistics.
        match_vol_score = min(num_matches / MATCH_THRESHOLD, 1.0)
        tourney_var_score = min(num_tournaments / TOURNEY_THRESHOLD, 1.0)
        raw_confidence = (match_vol_score * 0.4) + (tourney_var_score * 0.6)
        stats["stats_confidence"] = round(raw_confidence * 100, 2)

        return stats