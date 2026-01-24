import os
import sys
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    FINAL_TOURNAMENTS_FILE

)

class TodayMatchesInterceptor:
    def __init__(self):
        self.active_tournament = self._load_tournaments()

    def _load_tournaments(self):
        with open(FINAL_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
            tournaments = json.load(f)
            for tournament in tournaments:
                if tournament['status'] != 'Finished':
                    # Check if today lays within the tournament dates
                    if (datetime.strptime(tournament['start_date_utc'], '%Y-%m-%d %H:%M:%S') <= datetime.now() <= datetime.strptime(tournament['end_date_utc'], '%Y-%m-%d %H:%M:%S')):
                        # We know this tournament is active
                        return tournament
                    
    def start(self):
        if self.active_tournament:
            print(f"Active tournament found: {self.active_tournament['name']}")
        else:
            print("No active tournament found today.")


if __name__ == "__main__":
    interceptor = TodayMatchesInterceptor()
    interceptor.start()
                    