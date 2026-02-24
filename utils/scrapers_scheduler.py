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
        now = datetime.now()

        for tournament in tournaments:
            tournament_id = tournament['id']
            start_date_str = tournament['start_date']
            end_date_str = tournament['end_date']

            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

            # Schedule Players Scraper 1 days before the tournament starts
            players_scraper_time = start_date - timedelta(days=1)
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

            # Schedule Tournament Scraper 2 day after the tournament ends to update the status to finished
            finished_scraper_time = end_date + timedelta(days=2)
            if finished_scraper_time > now:
                self.scheduled_tasks.append({
                    "task_type": "tournaments",
                    "scheduled_date": finished_scraper_time.strftime("%Y-%m-%d"),
                    "tournament_id": tournament_id,
                    "log": None
                })

        tournament_ranges = []
        for tournament in tournaments:
            start_date = datetime.strptime(tournament['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(tournament['end_date'], "%Y-%m-%d") + timedelta(days=3)  # Extend end date by 3 days to cover matches scraper period
            tournament_ranges.append((start_date, end_date))

        # Plus we will scrap players once a week too. From now to the end of the year, every Tuesday.
        # Skip Tuesdays that fall within a tournament date range (players already run 1 days before)
        next_tuesday = now + timedelta(days=(1 - now.weekday() + 7) % 7)  # Next Tuesday
        while next_tuesday.year == now.year:
            is_during_tournament = any(
                start <= next_tuesday <= end for start, end in tournament_ranges
            )
            if not is_during_tournament:
                self.scheduled_tasks.append({
                    "task_type": "players",
                    "scheduled_date": next_tuesday.strftime("%Y-%m-%d"),
                    "tournament_id": None,
                    "log": None
                })
            next_tuesday += timedelta(days=7)

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