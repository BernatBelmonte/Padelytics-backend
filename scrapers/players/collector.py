# collector.py
from scrapers.database import VoleAIDB
from .fip import FipPlayerScraper

class PlayersCollector:
    def __init__(self):
        self.db = VoleAIDB()

    def start(self):
        print("🚀 INICIANDO VoleAI PLAYERS COLLECTOR")
        print("========================================")

        static_players, dynamic_players = FipPlayerScraper().run()
        print("\n---------------------------------------\n")
        static_players_with_images = self.db.save_player_images(static_players)
        self.db.save_static_players(static_players_with_images)
        self.db.save_dynamic_players(dynamic_players)
        


if __name__ == "__main__":
    collector = PlayersCollector()
    collector.start()