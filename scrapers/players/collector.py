import os
import sys
import requests
from datetime import datetime
from supabase import create_client, Client
from typing import List, Dict, Optional

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
        """
        Initializes the PlayersCollector with a Supabase client for database interactions and a DynamicPairsProcessor 
        for processing player pair data.
        """
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.processor = DynamicPairsProcessor()

    def start(self):
        """
        The main method to start the player collection process. It orchestrates the entire workflow from fetching existing data,
        scraping new data, processing it, and saving it back to the database.

        The method performs the following steps:
        1. Fetches the last snapshot date from the database to determine the starting point for scraping new player data.
        2. Uses the FipPlayerScraper to scrape static and dynamic player data starting from the last snapshot date.
        3. Processes the scraped player data, including handling player images and preparing the data for database storage.
        """
        print("🚀 STARTING Padelytics PLAYERS COLLECTOR")
        print("=========================================")

        # 1. Get last snapshot date from DB and scrape new data
        static_players, dynamic_players = FipPlayerScraper().run(self._get_last_snapshot_date())
        if not static_players or not dynamic_players:
            return
        
        # 2. Process and save static and dynamic player data, including image handling
        static_players_with_images = self._save_player_images(static_players, self._load_static_players()) # type: ignore
        self._save_static_players(static_players_with_images)
        self._save_dynamic_players(dynamic_players)
        print("\n-----------------------------------------")

        # 3. Process dynamic pairs and save to DB
        snapshot_date: str = dynamic_players[0]['snapshot_date']
        pairs_data: List[Optional[Dict]] = DynamicPairsProcessor().run(dynamic_players, snapshot_date)
        self._save_dynamic_pairs(pairs_data)

    def _get_last_snapshot_date(self) -> Optional[datetime]:
        """
        Fetches the last snapshot date of player data from the database to determine the starting point for scraping new player data.
        Returns:
            A datetime object representing the last snapshot date of player data, or None if no snapshot date is found or if an error occurs.
        """
        try:
            last_snapshot = self.client.table('dynamic_players').select('snapshot_date').order('snapshot_date', desc=True).limit(1).execute()
            if last_snapshot.data:
                last_date_str: str = last_snapshot.data[0]['snapshot_date'] # type: ignore
                last_date = datetime.strptime(last_date_str.split(' ')[0], "%Y-%m-%d")
                print(f"Last scraped player snapshot date: {last_date.date()}")
                return last_date
            else:
                print("No previously scraped player snapshots found.")
                return None
        except Exception as e:
            print(f"Error fetching last snapshot date: {e}")
            return None
        
    def _save_dynamic_pairs(self, pairs_list: List[Optional[Dict]]) -> None:
        """
        Saves the processed dynamic pairs data to the database using an upsert operation.
        Args:
            pairs_list: A list of dictionaries containing the processed dynamic pairs data to be saved to the database.
        """
        if not pairs_list:
            print("No data to save.")
            return
        try:
            self.client.table("dynamic_pairs").upsert(pairs_list, on_conflict="pair_slug, snapshot_date").execute()
            print("    Database synchronization complete.")
        except Exception as e:
            print(f"Error in DB Upsert: {e}")

    def _save_static_players(self, players_list: List[Dict]) -> None:
        """
        Saves the static player data to the database using an upsert operation.
            players_list: A list of dictionaries containing the static player data to be saved to the database.
        """
        if not players_list:
            print("    No new static player data to save.")
            return
        try:
            self.client.table("players").upsert(players_list, on_conflict="slug").execute()
            print("    Database synchronization complete.")
        except Exception as e:
            print(f"Error in DB Upsert: {e}")

    def _save_dynamic_players(self, players_list: List[Dict]) -> None:
        """
        Saves the dynamic player data to the database using an upsert operation.
        Args:
            players_list: A list of dictionaries containing the dynamic player data to be saved to the database.
        """
        if not players_list:
            print("    No dynamic player data to save.")
            return
        try:
            self.client.table("dynamic_players").upsert(players_list, on_conflict="slug, snapshot_date").execute()
            print("    Database synchronization complete.")
        except Exception as e:
            print(f"Error in DB Upsert: {e}")

    def _load_static_players(self) -> List[str]:
        """
        Loads the list of existing player slugs from the database to check against when processing new player data.
        Returns:
            A list of player slugs currently stored in the database.
        """
        all_players = []
        limit = 1000
        offset = 0

        while True:
            response = self.client.table("players") \
                .select("slug") \
                .range(offset, offset + limit - 1) \
                .execute()
            
            data = response.data or []
            all_players.extend([player['slug'] for player in data]) # type: ignore
            
            if len(data) < limit:
                break
                
            offset += limit

        return all_players

    def _save_player_images(self, players: List[Dict], existing_players: List[str]) -> List[Dict]:
        """
        Processes player images by checking for placeholders, downloading valid images, and uploading them to Supabase storage.
        Args:
            players: A list of dictionaries containing player data, including image URLs.
            existing_players: A list of player slugs that already exist in the database to avoid reprocessing.
        Returns:
            A list of player dictionaries that were not processed (i.e., players that are new).
        """
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
                    print(f"    Error processing image for {player['slug']}: {e}")
            del player['image_url']

        return players_not_processed
        
if __name__ == "__main__":
    collector = PlayersCollector()
    collector.start()