# collector.py
import sys
import os
from supabase import create_client, Client 
from .premier import PremierMatchesScraper

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL, 
    SUPABASE_KEY
)

class MatchesCollector:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("❌ Credentials for Supabase are missing in config.py or environment.")
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


    def start(self):
        print("🚀 STARTING VoleAI MATCHES COLLECTOR")
        print("======================================")
        tournaments_to_scrap = self._load_tournaments()
        if not tournaments_to_scrap:
            print("⚠️ There are no tournaments pending to be scraped.")
            return
        matches, tournaments_slugs_scraped = PremierMatchesScraper(tournaments_to_scrap).run()
        print("\n---------------------------------------\n")
        print("Premier Matches Data Collected:", len(matches), "matches")
        print("\n---------------------------------------\n")
        self._save_matches(matches)
        for t in tournaments_to_scrap:
            if t['slug'] in tournaments_slugs_scraped:  # type: ignore
                t['matches_scraped'] = True             # type: ignore
        self._save_tournaments(tournaments_to_scrap)

    def _load_tournaments(self):
        """
        Load tournaments where matches_scraped is False, meaning they are 
        pending to be scraped for matches and their status is Finished
        
        :param self: Description
        """
        print("📂 Loading finished tournaments that have not been scraped for matches...")
        try:
            res = self.client.table("tournaments").select("*").eq("matches_scraped", False).eq("status", "Finished").execute()
            data = res.data or []
            print(f"   ✅ Loaded {len(data)} existing tournaments.")
            return data
        except Exception as e:
            print(f"   ❌ Error loading tournaments: {e}")
            return []

    def _save_tournaments(self, tournaments_list):
        """ 
        Update tournaments in Supabase with matches_scraped = True 
        for those that have been scraped for matches.

        :param self: Description 
        :param tournaments_list: Description 
        """ 
        if not tournaments_list: 
            print("⚠️ No tournaments data to update.") 
            return 
        try: 
            self.client.table("tournaments").upsert(tournaments_list, on_conflict="tournaments_id").execute() 
            print(" ✅ Tournaments database synchronization complete.") 
        except Exception as e: 
            print(f" ❌ Critical Error in Tournaments DB Upsert: {e}")

    def _save_matches(self, matches_list): 
        """
        Save matches data to Supabase.
        
        :param self: Description
        :param matches_list: Description
        """
        if not matches_list: 
            print("⚠️ No matches data to save.")
            return
        try:
            self.client.table("matches").upsert(matches_list, on_conflict="tournaments_match_id").execute()
            print(" ✅ Matches database synchronization complete.")
        except Exception as e:
            print(f" ❌ Critical Error in Matches DB Upsert: {e}")
    
if __name__ == "__main__":
    collector = MatchesCollector()
    collector.start()