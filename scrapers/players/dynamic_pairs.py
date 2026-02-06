import logging
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, SUPABASE_KEY

class DynamicPairsProcessor:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("❌ Missing Supabase credentials in config.py or environment.")
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        self.round_weights = {
            'Men F': 10, 'Men SF': 8, 'Men QF': 6,
            'Men R16': 4, 'Men R32': 2, 'Men R64': 1,
            'Men Q3':0.75, 'Men Q2':0.50, 'Men Q1':0.25    
        }

    def run(self, scraped_players, snapshot_date_str):

        print(f" 🚀 Calculating Dynamic Pairs Stats for {snapshot_date_str}...")
        
        # 1. Identify pairs and calculate base points
        pairs_data = self._identify_pairs(scraped_players)
        if not pairs_data:
            return

        # 2. Get leader points to calculate distances
        leader_points = max(p['points'] for p in pairs_data.values())
        
        # 3. Process each pair
        final_payload = []
        for pair_slug, base_info in pairs_data.items():
            print(f" 📈 Processing {pair_slug}...")
            
            # Obtener historial de partidos de Supabase
            matches = self._fetch_pair_matches(pair_slug, snapshot_date_str)
            
            # Obtener snapshot anterior para cambios de ranking/puntos
            prev_snapshot = self._fetch_previous_pair_stat(pair_slug, snapshot_date_str)
            
            # Calcular KPIs
            kpis = self._calculate_advanced_kpis(pair_slug, matches, snapshot_date_str)
            
            # Construir registro
            record = {
                "pair_slug": pair_slug,
                "snapshot_date": snapshot_date_str,
                "points": base_info['points'],
                "points_behind_leader": leader_points - base_info['points'],
                "is_number_one": base_info['is_no1'],
                **kpis
            }

            # Añadir comparativas históricas
            if prev_snapshot:
                record["rank_change"] = (prev_snapshot.get('race_position') or 0) - base_info['rank'] if base_info['rank'] else 0 # type: ignore
                record["points_change"] = base_info['points'] - float(prev_snapshot.get('points', 0)) # type: ignore
                record["is_new_pair"] = False
            else:
                record["rank_change"] = None
                record["points_change"] = None
                record["is_new_pair"] = True

            final_payload.append(record)

        # 4. Upsert a Supabase
        return final_payload

    def _identify_pairs(self, players):
        pairs = {}
        processed_slugs = set()

        for p in players:
            slug = p['slug']
            partner = p['paired_with_slug']
            if not partner or slug in processed_slugs: continue

            # Canonical slug (Alphabetical)
            pair_slug = "/".join(sorted([slug, partner]))
            if partner not in [pl['slug'] for pl in players]: continue  # Validar que el partner también esté en el scrape
            # Buscamos al partner en el scrape para sumar puntos
            partner_data = next((x for x in players if x['slug'] == partner), None)
            total_pts = p.get('points', 0) + (partner_data.get('points', 0) if partner_data else 0)
            
            pairs[pair_slug] = {
                "points": total_pts,
                "rank": p['race_position'],
                "is_no1": p['race_position'] == 1
            }
            processed_slugs.update([slug, partner])
        return pairs

    def _fetch_pair_matches(self, pair_slug, date_str):
        all_matches = []
        limit = 1000
        offset = 0

        while True:
            res = self.supabase.table("matches").select("*")\
            .or_(f"team1_slug.eq.{pair_slug},team2_slug.eq.{pair_slug}")\
            .lt("date", date_str)\
            .order("date", desc=True).execute()
            
            data = res.data
            all_matches.extend(data)
            
            if len(data) < limit:
                break
                
            offset += limit

        return all_matches

    def _fetch_previous_pair_stat(self, pair_slug, date_str):
        res = self.supabase.table("dynamic_pairs").select("*")\
            .eq("pair_slug", pair_slug)\
            .lt("snapshot_date", date_str)\
            .order("snapshot_date", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def _calculate_advanced_kpis(self, pair_slug, matches, snapshot_date_str):
        """Métrica core adaptada de tu script local"""
        stats = {
            "form_guide": "", "streak_numeric": 0, "matches_last_14_days": 0,
            "season_matches_played": len(matches), "season_win_pct": 0,
            "dominance_ratio": 0, "straight_sets_win_rate": 0,
            "avg_games_conceded_per_set": 0, "tie_break_win_pct": 0,
            "closing_efficiency": 0, "comeback_rate": 0, "average_round_value": 0,
            "partnership_time_days": 0, "tournaments_played_together": 0,
            "days_since_last_match": 0, 'finals_conversion_rate': 0, "stats_confidence": 0  # default confidence level
        }

        MATCH_THRESHOLD = 30
        TOURNEY_THRESHOLD = 5

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

        for i, m in enumerate(matches):
            is_team1 = m['team1_slug'] == pair_slug
            # Determinar si ganó el equipo
            won_match = (is_team1 and m['winner_team'] == 1) or (not is_team1 and m['winner_team'] == 2)

            if i == 0:
                first_match_won = won_match
                streak_val = 1
            elif won_match == first_match_won:
                streak_val += 1

            if i + 1 == streak_val:
                stats["streak_numeric"] = streak_val if first_match_won else -streak_val

            if won_match: wins += 1
            if i < 5: form.append("W" if won_match else "L")
            
            if m['round_name'] == 'Men F':
                finals_played += 1
                if won_match: finals_won += 1
            # Actividad 14 días
            match_date = datetime.strptime(m['date'], "%Y-%m-%d")
            match_dates.append(match_date)
            t_id = m.get('tournament_id')
            if t_id: unique_tournaments.add(t_id)
            
            current_round_weight = self.round_weights.get(m['round_name'], 0)
        
            if t_id not in tournament_max_weights or current_round_weight > tournament_max_weights[t_id]:
                tournament_max_weights[t_id] = current_round_weight

            if (snap_date - match_date).days <= 14: 
                stats["matches_last_14_days"] += 1

            # Lógica de Sets y Juegos
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
                        closing_attempts += 1 # Ganó el 1ero
                        first_set_won = True
                else: 
                    m_sets_lost += 1
                    if s == 1: 
                        comeback_attempts += 1 # Perdió el 1ero
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
            earliest_match = min(match_dates)
            latest_match = max(match_dates)
            
            stats["partnership_time_days"] = (today - earliest_match).days
            stats["days_since_last_match"] = (today - latest_match).days
            stats["tournaments_played_together"] = len(unique_tournaments)
            


        # Cálculos finales
        stats["form_guide"] = "-".join(form)
        stats["season_win_pct"] = round((wins / len(matches)) * 100, 2) if matches else None
        stats["dominance_ratio"] = round(games_won / games_lost, 2) if games_lost > 0 else None
        stats["straight_sets_win_rate"] = round((straight_sets_wins / len(matches)) * 100, 2) if matches else None
        stats["avg_games_conceded_per_set"] = round(games_lost / (sets_won + sets_lost), 2) if (sets_won + sets_lost) > 0 else None
        stats["tie_break_win_pct"] = round((tb_won / tb_played) * 100, 2) if tb_played > 0 else None
        stats["closing_efficiency"] = round((closing_wins / closing_attempts) * 100, 2) if closing_attempts > 0 else None
        stats["comeback_rate"] = round((comeback_wins / comeback_attempts) * 100, 2) if comeback_attempts > 0 else None
        stats["finals_conversion_rate"] = round((finals_won / finals_played) * 100, 2) if finals_played > 0 else None

        # Confidence heuristic
        match_vol_score = min(num_matches / MATCH_THRESHOLD, 1.0)
        tourney_var_score = min(num_tournaments / TOURNEY_THRESHOLD, 1.0)
        raw_confidence = (match_vol_score * 0.4) + (tourney_var_score * 0.6)
        stats["stats_confidence"] = round(raw_confidence * 100, 2)

        return stats