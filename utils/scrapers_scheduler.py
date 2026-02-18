import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List
from supabase import create_client, Client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, SUPABASE_KEY


class ScrapersScheduler:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("❌ Credentials for Supabase are missing in config.py or environment.")
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.scheduled_tasks = []

    def run(self):
        """
        To run one time at the beginning of each season to schedule the scrapers for the upcoming tournaments.
        For each tournament, schedule the corresponding scraper to run at the appropriate time.
        Players should run 3 days before the tournament starts, matches should run 3 days after the tournament
        and tournaments should run one day before it starts.
        
        :param self: Description
        """
        print("🚀 STARTING Scrapers Scheduler")
        print("===============================")
        tournaments: List[Dict] = self._get_upcoming_tournaments()
        for tournament in tournaments:
            tournament_id = tournament['tournaments_id']
            start_date_str = tournament['start_date']
            end_date_str = tournament['end_date']

            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            now = datetime.now()

            # Schedule Players Scraper 3 days before the tournament starts
            players_scraper_time = start_date - timedelta(days=3)
            if players_scraper_time > now:
                self.scheduled_tasks.append({
                    "task_type": "players",
                    "scheduled_date": players_scraper_time.strftime("%Y-%m-%d"),
                    "tournament_id": tournament_id,
                    "log": None

                })

            # Schedule Matches Scraper 3 days after the tournament ends
            matches_scraper_time = end_date + timedelta(days=3)
            if matches_scraper_time > now:
                self.scheduled_tasks.append({
                    "task_type": "matches",
                    "scheduled_date": matches_scraper_time.strftime("%Y-%m-%d"),
                    "tournament_id": tournament_id,
                    "log": None
                })

            # Schedule Tournament Scraper 1 day before the tournament starts
            tournament_scraper_time = start_date - timedelta(days=1)
            if tournament_scraper_time > now:
                self.scheduled_tasks.append({
                    "task_type": "tournaments",
                    "scheduled_date": tournament_scraper_time.strftime("%Y-%m-%d"),
                    "tournament_id": tournament_id,
                    "log": None
                })

            # Schedule Tournament Scraper 1 day after the tournament ends to update the status to finished
            finished_scraper_time = end_date + timedelta(days=1)
            if finished_scraper_time > now:
                self.scheduled_tasks.append({
                    "task_type": "tournaments",
                    "scheduled_date": finished_scraper_time.strftime("%Y-%m-%d"),
                    "tournament_id": tournament_id,
                    "log": None
                })

        self._save_scheduled_tasks()

    def _get_upcoming_tournaments(self) -> List[Dict]:
        """
        Fetch tournaments that have status = Upcoming. Plus we check 
        the end date to avoid scheduling scrapers for tournaments that 
        have already ended but haven't been marked as finished in the database.

        :return: List of upcoming tournaments
        """
        try:
            res = self.client.table('tournaments').select('*').eq('status', 'Upcoming').execute()
            data = res.data or []
            print(f"Found {len(data)} tournaments to schedule")
            return data # type: ignore
        except Exception as e:
            print(e)
            return []
    

    def _save_scheduled_tasks(self):
        """
        Save the scheduled tasks to the database.
        """
        if not self.scheduled_tasks:
            print("⚠️ No tasks to schedule.")
            return
        try:
            self.client.table("scraper_tasks").upsert(self.scheduled_tasks, on_conflict="task_type, scheduled_date", ignore_duplicates=True).execute()
            print("   ✅ Scheduled tasks saved to database.")
        except Exception as e:
            print(f"   ❌ Critical Error in saving scheduled tasks: {e}")
            
        
if __name__ == "__main__":
    scheduler = ScrapersScheduler().run()