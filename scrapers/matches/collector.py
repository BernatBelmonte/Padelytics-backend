import sys
import os
from supabase import create_client, Client 
from typing import List, Dict
# Scrapers Imports
from .premier import PremierMatchesScraper

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL, 
    SUPABASE_KEY
)

class MatchesCollector:
    """
    The MatchesCollector class is responsible for orchestrating the entire process of collecting match data from the
    Premier Padel website, specifically for tournaments that have been marked as "Results" in the database but have 
    not yet been scraped for matches.

    The method performs the following steps:
    1. Fetch tournaments from the database that are marked as "Results" and have not yet been scraped for matches.
    2. Use the PremierMatchesScraper to scrape match data for the identified tournaments.
    3. Save the scraped match data back to the database and update the tournament records.
    """
    def __init__(self):
        """
        Initializes the MatchesCollector with a Supabase client for database interactions.
        """
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def start(self) -> None:
        """
        The main method to start the match collection process. It orchestrates the entire workflow from fetching existing data,
        scraping new data, and saving it back to the database.
        """
        print("🚀 STARTING Padelytics MATCHES COLLECTOR")
        print("========================================")

        # 1. Load Tournaments to be scraped for matches
        tournaments_to_scrap = self._load_tournaments()
        if not tournaments_to_scrap:
            print("    ⚠️ There are no tournaments pending to be scraped.")
            return
        
        # 2. Scrape Matches for each tournament
        matches, tournaments_slugs_scraped = PremierMatchesScraper(tournaments_to_scrap).run()
        print("\n---------------------------------------\n")
        print("Premier Matches Data Collected:", len(matches), "matches")
        print("\n---------------------------------------\n")

        # 3. Save Matches and Update Tournaments
        self._save_matches(matches)
        for t in tournaments_to_scrap:
            if t['premier_slug'] in tournaments_slugs_scraped:  # type: ignore
                t['matches_scraped'] = True             # type: ignore
        self._save_tournaments(tournaments_to_scrap)

    def _load_tournaments(self) -> List[Dict]:
        """
        Loads tournaments from the database that are marked as "Results" and have not yet been scraped for matches.
        Returns:
            A list of tournament records that need to be scraped for matches.
        """
        try:
            res = self.client.table("tournaments").select("id, premier_slug, matches_scraped").eq("matches_scraped", False).eq("status", "Results").execute()
            data = res.data or []
            print(f"    Loaded {len(data)} tournaments to be scraped for matches.")
            return data # type: ignore
        except Exception as e:
            print(f"    Error loading tournaments: {e}")
            return []

    def _save_tournaments(self, tournaments_list: List[Dict]) -> None:
        """ 
        Update tournaments in Supabase with matches_scraped = True 
        for those that have been scraped for matches.

        Args:
            tournaments_list: A list of tournament dictionaries that have been scraped for matches, with their 'matches_scraped' field updated to True.
        """ 
        if not tournaments_list: 
            print("    No tournaments data to update.") 
            return 
        try: 
            self.client.table("tournaments").upsert(tournaments_list, on_conflict="id").execute() 
            print("     ✅ Tournaments database synchronization complete.") 
        except Exception as e: 
            print(f"    Error in Tournaments DB Upsert: {e}")

    def _save_matches(self, matches_list: List[Dict]) -> None: 
        """
        Save matches data to Supabase.
        
        Args:
            matches_list: A list of match dictionaries containing the match data to be saved to the database.
        """
        if not matches_list: 
            print("    No matches data to save.")
            return
        try:
            self.client.table("matches").upsert(matches_list, on_conflict="tournaments_match_id").execute()
            print("     ✅ Matches database synchronization complete.")
        except Exception as e:
            print(f"    Error in Matches DB Upsert: {e}")
    
if __name__ == "__main__":
    collector = MatchesCollector()
    collector.start()