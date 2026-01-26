# collector.py
from scrapers.database import TournamentsDB
from .fip import FipTournamentsScraper
from .premier import PremierTournamentsScraper
from .enricher import TournamentEnricher

class TournamentsCollector:
    def __init__(self):
        self.db = TournamentsDB()
        self.enricher = TournamentEnricher()

    def start(self):
        print("🚀 INICIANDO VoleAI TOURNAMENT COLLECTOR")
        print("========================================")

        # 1. Cargar datos existentes y actualizar estados
        existing_data = self.db.load_existing_tournaments()
        self.db.update_finished_status(existing_data)

        # 2. Scrapear fuentes
        # Pasamos existing_data para que los scrapers puedan imputar valores
        fip_data = FipTournamentsScraper(existing_data).run()
        print("\n----------------------------------------\n")
        
        premier_data = PremierTournamentsScraper(existing_data).run()
        print("\n----------------------------------------\n")
        
        # 3. Unir y Enriquecer (Merge + Geo + Weather)
        final_data = self.enricher.process(premier_data, fip_data)
        print("\n----------------------------------------\n")
        print("Fip Data Collected:", len(fip_data), "tournaments")
        print("Final Enriched Tournaments:", len(final_data))
        print("Premier Data Collected:", len(premier_data), "tournaments")
        print("\n----------------------------------------\n")
        # 4. Guardar en Base de Datos (Upsert)
        self.db.save_tournaments(final_data)


if __name__ == "__main__":
    collector = TournamentsCollector()
    collector.start()