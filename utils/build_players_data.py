import json
import os
import pandas as pd
import sys
import re
from unidecode import unidecode

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CLEAN_DATA_DIR, 
    RAW_PREMIER_PADEL_PLAYERS_FILE, 
    RAW_PREMIER_PADEL_TOURNAMENTS_FILE, 
    STATIC_PLAYERS_FILE, 
    DYNAMIC_PAIRS_FILE, 
    DYNAMIC_PLAYERS_FILE
)

class PlayersDataBuilder:
    def __init__(self):
        self.raw_entries = []
        self.tournaments = []
        
        self.static_players = {}
        self.dynamic_players = []
        self.dynamic_pairs = []
        self.existing_players = []
        self.existing_player_ids = set()

    def start(self):
        print("🏗️ Players Data Builder")
        print("========================")
        
        if not self._load_data():
            print("❌ Aborting: Missing input files.")
            return
        self._process_entries()
        self._save_data()

    def _load_data(self):
        try:
            if os.path.exists(RAW_PREMIER_PADEL_PLAYERS_FILE):
                with open(RAW_PREMIER_PADEL_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    self.raw_entries = json.load(f)
            else:
                print(f"⚠️ File not found: {RAW_PREMIER_PADEL_PLAYERS_FILE}")
                return False

            if os.path.exists(RAW_PREMIER_PADEL_TOURNAMENTS_FILE):
                with open(RAW_PREMIER_PADEL_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
                    self.tournaments = json.load(f)
            else:
                print(f"⚠️ File not found: {RAW_PREMIER_PADEL_TOURNAMENTS_FILE}")
                return False
            if os.path.exists(STATIC_PLAYERS_FILE):
                with open(STATIC_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    existing_players = json.load(f)
                    for player in existing_players:
                        pid = player.get('player_id')
                        self.existing_players.append(player)
                        if pid:
                            self.existing_player_ids.add(pid)

            print(f"🔄 Loaded {len(self.raw_entries)} player entries and {len(self.tournaments)} tournaments.")
            return True

        except Exception as e:
            print(f"❌ Error loading files: {e}")
            return False

    def _get_date_mapping(self):
        tourn_dates = {}
        for t in self.tournaments:
            t_id = t.get('tournaments_id')
            s_date = t.get('start_date_utc')
            if t_id:
                tourn_dates[t_id] = s_date
        return tourn_dates

    def _process_entries(self):
        print("⚙️ Processing datasets...")
        
        tourn_dates = self._get_date_mapping()
        for entry in self.raw_entries:
            t_id = entry.get('tournaments_id')
            timestamp = tourn_dates.get(t_id, "Unknown Date")
            
            p1_id = entry.get('player_id')
            p2_id = entry.get('partner_player_id')

            # STATIC DATASET
            if p1_id and p1_id not in self.existing_player_ids:
                self._add_static_profile(p1_id, entry, is_partner=False)
            if p2_id and p2_id not in self.existing_player_ids:
                self._add_static_profile(p2_id, entry, is_partner=True)

            # DYNAMIC PLAYERS DATASET
            common_info = {
                'timestamp': timestamp,
            }
            
            if p1_id:
                self.dynamic_players.append({
                    **common_info,
                    'player_id': p1_id,
                    'player_code': entry.get('playerId'),
                    'name': entry.get('player_name'),
                    'slug': self._clean_player_name(entry.get('player_name')),
                    'points': int(entry.get('player_point')) if entry.get('player_point') is not None else 0,
                })
            
            if p2_id:
                self.dynamic_players.append({
                    **common_info,
                    'player_id': p2_id,
                    'player_code': entry.get('partnerplayerId'),
                    'name': entry.get('partner_player_name'),
                    'slug': self._clean_player_name(entry.get('partner_player_name')),
                    'points': int(entry.get('partner_player_point')) if entry.get('partner_player_point') is not None else 0,
                })

            # DYNAMIC PAIRS DATASET
            if p1_id and p2_id:
                self._add_dynamic_pair(entry, p1_id, p2_id, timestamp)

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


    def _add_static_profile(self, pid, entry, is_partner=False):
        if pid not in self.static_players:
            prefix = "partner_" if is_partner else ""
            code_key = 'partnerplayerId' if is_partner else 'playerId'
            name_key = f'{prefix}player_name'
            img_key = f'{prefix}player_image'
            country_key = f'{prefix}player_countries_image'

            self.static_players[pid] = {
                'player_id': pid,
                'player_code': entry.get(code_key),
                'name': entry.get(name_key),
                'slug': self._clean_player_name(entry.get(name_key)),
                'player_image': entry.get(img_key),
                'country_image': entry.get(country_key)
            }
            self.existing_players.append({
                'player_id': pid,
                'player_code': entry.get(code_key),
                'name': entry.get(name_key),
                'slug': self._clean_player_name(entry.get(name_key)),
                'player_image': entry.get(img_key),
                'country_image': entry.get(country_key)
            })

    def _add_dynamic_pair(self, entry, p1_id, p2_id, timestamp):
        # Create a unique Pair ID by sorting player IDs (A+B == B+A)
        ids = sorted([p1_id, p2_id])
        pair_id = f"{ids[0]}-{ids[1]}"
        
        codes = sorted([entry.get('playerId'), entry.get('partnerplayerId')])
        pair_code = f"{codes[0]}-{codes[1]}"
        
        # Identify who is who in the sorted ID to assign names correctly
        if ids[0] == p1_id:
            u1_name, u1_code = entry.get('player_name'), entry.get('playerId')
            u2_name, u2_code = entry.get('partner_player_name'), entry.get('partnerplayerId')
        else:
            u1_name, u1_code = entry.get('partner_player_name'), entry.get('partnerplayerId')
            u2_name, u2_code = entry.get('player_name'), entry.get('playerId')
        u1_slug = self._clean_player_name(u1_name)
        u2_slug = self._clean_player_name(u2_name)
        pair_slug = '-'.join(sorted([u1_slug, u2_slug]))
        self.dynamic_pairs.append({
            'timestamp': timestamp,
            'pair_id': pair_id,
            'pair_code': pair_code,
            'pair_slug': pair_slug,
            'total_points': int(entry.get('total_point')) if entry.get('total_point') is not None else 0,
            'p1_id': ids[0],
            'p1_code': u1_code,
            'p1_name': u1_name,
            'p1_slug': u1_slug,
            'p2_id': ids[1],
            'p2_code': u2_code,
            'p2_name': u2_name,
            'p2_slug': u2_slug
        })

    def _save_data(self):
        if not os.path.exists(CLEAN_DATA_DIR):
            os.makedirs(CLEAN_DATA_DIR)
        try:
            # Save Static Players
            with open(STATIC_PLAYERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.existing_players, f, indent=4, ensure_ascii=False)
            
            # Save Dynamic Players
            formatted_players_data = []
            if self.dynamic_players:
                df_dyn_players = pd.DataFrame(self.dynamic_players)
                if 'timestamp' in df_dyn_players.columns:
                    # Sort by timestamp first, then points
                    df_dyn_players.sort_values(by=['timestamp', 'points'], inplace=True, ascending=[True, False])
                    
                    for ts, group in df_dyn_players.groupby('timestamp'):
                        # Remove timestamp from the inner records
                        records = group.drop(columns=['timestamp']).to_dict(orient='records')
                        formatted_players_data.append({
                            "timestamp": ts,
                            "players": records
                        })

            with open(DYNAMIC_PLAYERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(formatted_players_data, f, indent=4, ensure_ascii=False)

            # Save Dynamic Pairs
            formatted_pairs_data = []
            if self.dynamic_pairs:
                df_pairs = pd.DataFrame(self.dynamic_pairs)
                if 'timestamp' in df_pairs.columns:
                    # Sort by timestamp first, then points
                    df_pairs.sort_values(by=['timestamp', 'total_points'], inplace=True, ascending=[True, False])
                    
                    for ts, group in df_pairs.groupby('timestamp'):
                        records = group.drop(columns=['timestamp']).to_dict(orient='records')
                        
                        formatted_pairs_data.append({
                            "timestamp": ts,
                            "pairs": records
                        })

            with open(DYNAMIC_PAIRS_FILE, 'w', encoding='utf-8') as f:
                json.dump(formatted_pairs_data, f, indent=4, ensure_ascii=False)

            print("✅ Success! Generated 3 datasets:")
            print(f"   static_players.json ({len(self.existing_players)} new unique players)")
            print(f"   dynamic_players.json ({len(formatted_players_data)} timestamp groups)")
            print(f"   dynamic_pairs.json ({len(formatted_pairs_data)} timestamp groups)")
            
        except Exception as e:
            print(f"❌ Error saving datasets: {e}")

if __name__ == "__main__":
    builder = PlayersDataBuilder()
    builder.start()