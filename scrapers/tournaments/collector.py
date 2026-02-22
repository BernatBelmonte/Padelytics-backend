import os
import sys
from datetime import datetime
from supabase import create_client, Client
from typing import List, Dict, Set, Optional

# Scrapers Imports
from .fip import FipTournamentsScraper
from .premier import PremierTournamentsScraper
from .enricher import TournamentEnricher

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL, 
    SUPABASE_KEY
)

class TournamentsCollector:
    """
    The TournamentsCollector class orchestrates the entire process of collecting, enriching, and saving tournament data from both the FIP and Premier Padel sources. It handles database interactions with Supabase to fetch existing tournament data, determine which tournaments need to be scraped, and upsert the enriched tournament data back into the database. The collector ensures that only new or updated tournaments are processed, optimizing the scraping and enrichment workflow.
    Key Responsibilities:
    1. Fetch finished tournaments from the database to determine which tournaments have already been processed.
    2. Use the FipTournamentsScraper and PremierTournamentsScraper to scrape new tournament data starting from the last finished tournament date.
    3. Enrich the scraped data using the TournamentEnricher, which adds additional information such as weather data, coordinates, and a calculated court speed index.
    4. Save the enriched tournament data back to the Supabase database using an upsert operation to ensure data integrity and avoid duplicates.
    """
    def __init__(self):
        """
        Initializes the TournamentsCollector with a Supabase client for database interactions.
        """
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def start(self):
        """
        The main method to start the tournament collection process. It orchestrates the entire workflow from fetching existing data, scraping new data, enriching it, and saving it back to the database.
        The method performs the following steps:
        
        1. Fetches the last snapshot date from the database to determine the starting point for scraping new tournament data.
        2. Uses the FipTournamentsScraper and PremierTournamentsScraper to scrape tournament data starting from the last finished tournament date.
        3. Enriches the scraped tournament data using the TournamentEnricher, which adds additional information such as weather data, coordinates, and a calculated court speed index.
        4. Saves the enriched tournament data back to the database using an upsert operation to ensure that existing records are updated and new records are inserted without creating duplicates.
        """
        print("🚀 STARTING Padelytics TOURNAMENT COLLECTOR")
        print("============================================")
        
        # 1. Get Finished Tournaments from DB
        finished_tournaments = self._get_finished_tournaments()
        start_from_date = self._get_last_finished_tournament_date(finished_tournaments)

        # 2. Scrape Data
        fip_data = FipTournamentsScraper({t['fip_slug'] for t in finished_tournaments}).run(start_from_date) # type: ignore
        premier_data = PremierTournamentsScraper({t['premier_slug'] for t in finished_tournaments}).run(start_from_date) # type: ignore
        print("Scraped FIP Tournaments:    ", len(fip_data))
        print("Scraped Premier Tournaments:", len(premier_data))
        print("--------------------------------")

        # 3. Merge and Enrich
        all_tournaments = self._get_all_tournaments()
        final_data = TournamentEnricher(all_tournaments).process(premier_data, fip_data)
        print("Enrichment complete. Total tournaments ready for DB: ", len(final_data))

        # 4. Save to Database (Upsert)
        self._save_tournaments(final_data)
        

    def _get_finished_tournaments(self) -> List[Dict]:
        """
        Fetches the list of finished tournaments from the Supabase database. This method retrieves tournaments that have a status of "Results" and orders them by end date in descending order to identify the most recent finished tournament.
        
        Returns:
            A list of dictionaries containing the finished tournaments with their end date, FIP slug, and Premier slug.
        """
        try:
            res = self.client.table("tournaments").select("end_date, fip_slug, premier_slug").eq("status", "Results").order("end_date", desc=True).execute()
            return res.data if res.data else [] # type: ignore
        except Exception as e:
            print(f"Error fetching finished tournaments: {e}")
            return []
        
    def _get_all_tournaments(self) -> List[Dict]:
        """
        Fetches all tournaments from the Supabase database, regardless of their status. This method retrieves the FIP slug, Premier slug, matches scraped, and enrichment status for all tournaments to provide a comprehensive view of the existing tournament data in the database. This information is crucial for the enrichment process to determine which tournaments have already been scraped and enriched.
        
        Returns:
            A list of dictionaries containing all tournaments with their FIP slug, Premier slug, matches scraped, and enrichment status.
        """
        try:
            res = self.client.table("tournaments").select("*").execute()
            return res.data if res.data else [] # type: ignore
        except Exception as e:
            print(f"Error fetching all tournaments: {e}")
            return []

    def _get_last_finished_tournament_date(self, finished_tournaments: List[Dict]) -> Optional[datetime]:
        """
        Determines the date of the last finished tournament from the list of finished tournaments. This date is used as a reference point to decide which tournaments need to be scraped, ensuring that only new tournaments that have ended after this date are processed. 
        Args:
            finished_tournaments: A list of dictionaries containing finished tournaments with their end dates.
        Returns:
            The date of the last finished tournament as a datetime object, or None if there are no finished tournaments or if there is an error parsing the date.
        """
        if not finished_tournaments:
            return None
        try:
            last_date_str = finished_tournaments[0]['end_date']
            last_date = datetime.strptime(last_date_str.split(' ')[0], "%Y-%m-%d")
            print(f"Last finished tournament date: {last_date.date()}")
            return last_date
        except Exception as e:
            print(f"Error parsing last finished tournament date: {e}")
            return None
        
    def _save_tournaments(self, tournaments_list: List[Dict]) -> None:
        """
        Saves the enriched tournament data to the Supabase database using an upsert operation. This method takes a list of tournament dictionaries and attempts to insert them into the "tournaments" table. If a tournament with the same ID already exists, it will be updated with the new data instead of creating a duplicate entry. This ensures that the database remains clean and up-to-date with the latest information.
        
        Args:
            tournaments_list: A list of dictionaries containing the enriched tournament data to be saved to the database.
        """
        if not tournaments_list:
            print("No data to save.")
            return
        print(f"💾 Saving {len(tournaments_list)} tournaments to Supabase...")
        try:
            self.client.table("tournaments").upsert(tournaments_list, on_conflict="id").execute()
            print("    Database synchronization complete.")
        except Exception as e:
            print(f"Error in DB Upsert: {e}")
    
if __name__ == "__main__":
    collector = TournamentsCollector()
    collector.start()