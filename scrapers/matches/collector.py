# collector.py
from scrapers.database import VoleAIDB
from .premier import PremierMatchesScraper

class PlayersCollector:
    def __init__(self):
        self.db = VoleAIDB()

    def start(self):
        print("🚀 STARTING VoleAI PLAYERS COLLECTOR")
        print("========================================")
        existing_matches = self.db.load_existing_matches()
        existing_tournaments = self.db.load_existing_tournaments()
        existing_tournaments_to_scrap = [t for t in existing_tournaments if not t['matches_scraped']] # type: ignore
        if not existing_tournaments_to_scrap:
            print("⚠️ There are no tournaments pending to be scraped.")
            return
        matches, tournaments_slugs_scraped = PremierMatchesScraper(existing_matches, existing_tournaments_to_scrap).run()
        print("\n---------------------------------------\n")
        print("Premier Matches Data Collected:", len(matches), "matches")
        print("\n---------------------------------------\n")
        self.db.save_matches(matches)
        for t in existing_tournaments:
            if t['slug'] in tournaments_slugs_scraped:  # type: ignore
                t['matches_scraped'] = True             # type: ignore
        self.db.save_tournaments(existing_tournaments)

if __name__ == "__main__":
    collector = PlayersCollector()
    collector.start()