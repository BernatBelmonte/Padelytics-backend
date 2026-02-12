import os
import sys
from datetime import datetime
from supabase import create_client, Client

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
    Docstring for TournamentsCollector
    Class to collect, enrich, and store tournament data from various sources.
    Methods:
        - __init__: Initializes enricher and Supabase client instances.
        - start: Main method to orchestrate the data collection and storage process.
        - _load_tournaments: Loads existing tournaments from the database.
        - _save_tournaments: Saves enriched tournament data to the database.
        - _update_finished_status: Updates the status of old tournaments to 'Finished'.
    """
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def start(self):
        print("🚀 STARTING VoleAI TOURNAMENT COLLECTOR")
        print("========================================")

        # 1. Load existing tournaments from DB
        existing_tournaments = self._load_tournaments()
        self._update_finished_status(existing_tournaments) # Auto-close old tournaments

        last_scraped_tournament = max([t['end_date'] for t in existing_tournaments]) if existing_tournaments else None # type: ignore
        if last_scraped_tournament:
            last_date = datetime.strptime(last_scraped_tournament.split(' ')[0], "%Y-%m-%d")
            print(f"Last scraped tournament date: {last_date.date()}")
        else:
            last_date = None
            print("No previously scraped tournaments found.")

        # 2. Scrape sources
        fip_data = FipTournamentsScraper({t['fip_source_url'] for t in existing_tournaments}).run(last_date) # type: ignore
        print("\n----------------------------------------\n")
        premier_data = PremierTournamentsScraper({t['tournaments_id'] for t in existing_tournaments}).run(last_date) # type: ignore
        print("\n----------------------------------------\n")
        
        # 3. Merge and Enrich (Merge + Geo + Weather)
        final_data = TournamentEnricher(existing_tournaments).process(premier_data, fip_data)
        print("\n----------------------------------------\n")
        print("Fip Data Collected:", len(fip_data), "tournaments")
        print("Premier Data Collected:", len(premier_data), "tournaments")
        print("Final Enriched Tournaments:", len(final_data))
        print("\n----------------------------------------\n")

        # 4. Save to Database (Upsert)
        self._save_tournaments(final_data)

    def _load_tournaments(self):
        print("📂 Loading existing tournaments from Supabase...")
        try:
            res = self.client.table("tournaments").select("*").execute()
            data = res.data or []
            print(f"   ✅ Loaded {len(data)} existing tournaments.")
            return data
        except Exception as e:
            print(f"   ❌ Error loading tournaments: {e}")
            return []
        
    def _save_tournaments(self, tournaments_list):
        if not tournaments_list:
            print("⚠️ No data to save.")
            return
        print(f"💾 Saving {len(tournaments_list)} tournaments to Supabase...")
        try:
            self.client.table("tournaments").upsert(tournaments_list, on_conflict="tournaments_id").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")
    
    def _update_finished_status(self, tournaments):
        """Check old tournaments and mark them as Finished if the date has passed."""
        updated_count = 0
        to_update = []
        
        for t in tournaments:
            if t['status'] != 'Finished':
                end_date_str = t['end_date']
                if end_date_str:
                    try:
                        # Clean date if it comes with time
                        clean_date = end_date_str.split(' ')[0]
                        end_date = datetime.strptime(clean_date, "%Y-%m-%d")
                        if end_date < datetime.now():
                            t['status'] = 'Finished'
                            to_update.append(t)
                            updated_count += 1
                    except:
                        continue
        
        if to_update:
            print(f"🔄 Auto-closing {updated_count} finished tournaments...")
            self._save_tournaments(to_update)

if __name__ == "__main__":
    collector = TournamentsCollector()
    collector.start()