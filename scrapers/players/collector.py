import os
import sys
import requests
from datetime import datetime
from supabase import create_client, Client


# Scrapers Imports
from .fip import FipPlayerScraper
from .dynamic_pairs import DynamicPairsProcessor

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL, 
    SUPABASE_KEY
)


class PlayersCollector:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("❌ Credentials for Supabase are missing in config.py or environment.")
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.processor = DynamicPairsProcessor()

    def start(self):
        print("🚀 STARTING VoleAI PLAYERS COLLECTOR")
        print("=====================================")

        static_players, dynamic_players = FipPlayerScraper().run(self._get_last_snapshot_date())
        if not static_players or not dynamic_players:
            print("No new player data to process. Exiting.")
            return
        static_players_with_images = self._save_player_images(static_players, [p['slug'] for p in self._load_static_players()]) # type: ignore
        self._save_static_players(static_players_with_images)
        self._save_dynamic_players(dynamic_players)
        print("\n---------------------------------------\n")

        snapshot_date: str = dynamic_players[0]['snapshot_date']
        pairs_data = DynamicPairsProcessor().run(dynamic_players, snapshot_date)
        self._save_dynamic_pairs(pairs_data)

    def _get_last_snapshot_date(self):
        try:
            last_snapshot = self.client.table('dynamic_players').select('snapshot_date').order('snapshot_date', desc=True).limit(1).execute()
            if last_snapshot.data:
                last_date_str: str = last_snapshot.data[0]['snapshot_date'] # type: ignore
                last_date = datetime.strptime(last_date_str.split(' ')[0], "%Y-%m-%d")
                print(f"Last scraped player snapshot date: {last_date.date()}")
                return last_date.date()
            else:
                print("No previously scraped player snapshots found.")
                return None
        except Exception as e:
            print(f"Error fetching last snapshot date: {e}")
            return None
        
    def _save_dynamic_pairs(self, pairs_list):
        if not pairs_list:
            print("⚠️ No data to save.")
            return
        try:
            self.client.table("dynamic_pairs").upsert(pairs_list, on_conflict="pair_slug, snapshot_date").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def _save_static_players(self, players_list):
        if not players_list:
            print("⚠️ No data to save.")
            return
        try:
            self.client.table("players").upsert(players_list, on_conflict="slug").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def _save_dynamic_players(self, players_list):
        if not players_list:
            print("⚠️ No data to save.")
            return
        try:
            self.client.table("dynamic_players").upsert(players_list, on_conflict="slug, snapshot_date").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def _load_static_players(self):
        all_players = []
        limit = 1000
        offset = 0

        while True:
            response = self.client.table("players") \
                .select("slug") \
                .range(offset, offset + limit - 1) \
                .execute()
            
            data = response.data
            all_players.extend(data)
            
            if len(data) < limit:
                break
                
            offset += limit

        return all_players

    def _save_player_images(self, players, existing_players):

        placeholder_url = "https://www.padelfip.com/wp-content/uploads/2023/02/generico.png"
        players_not_processed = []
        for player in players:
            if player['slug'] not in existing_players:
                players_not_processed.append(player)

        for player in players_not_processed:
            if player['image_url'] == placeholder_url:
                print(f"⚠️ Placeholder image detected for {player['slug']}. Skipping upload.")
                del player['image_url']
                continue
            if player['image_url']:
                try:
                    response = requests.get(player['image_url'], stream=True)
                    if response.status_code != 200:
                        print(f"⚠️ Can't download image for {player['slug']}. Most likely player image is missing.")
                    else:
                        file_extension = player['image_url'].split('.')[-1].split('?')[0]
                        file_path = f"{player['slug']}.{file_extension}"

                        if not player.get('image_public_url'):
                            try:
                                self.client.storage.from_("player-images").upload(
                                    path=file_path,
                                    file=response.content,
                                    file_options={"content-type": f"image/{file_extension}"}
                                )
                                print(f"✅ Picture uploaded: {file_path}")
                            except Exception as e:
                                print(f"ℹ️ The file might already exist in storage")

                        public_url = self.client.storage.from_("player-images").get_public_url(file_path)

                        player['image_public_url'] = public_url

                except Exception as e:
                    print(f"❌ Error procesando imagen para {player['slug']}: {e}")
            del player['image_url']
        return players_not_processed
        

        
        


if __name__ == "__main__":
    collector = PlayersCollector()
    collector.start()