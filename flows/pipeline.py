import sys
import os

from prefect import flow, task

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.fip_tournaments_scraper import FipTournamentInterceptor
from scrapers.premier_tournaments_scraper import PremierTournamentInterceptor
from scrapers.premier_matches_scraper import PremierMatchesInterceptor
from scrapers.premier_players_scraper import PremierPlayersInterceptor

from utils.tournaments_processor import TournamentsProcessor
from utils.matches_processor import MatchesProcessor
from utils.build_players_data import PlayersDataBuilder
from utils.players_enricher import PlayersEnricher
from utils.pairs_features_enricher import PairsFeaturesEnricher
from utils.data_exploiter import JsonToCsvConverter

from backend.api_data_preparator import APIDataPreparator
from backend.model_trainer import ModelTrainer

# -----------------------
# ETL TASKS
# -----------------------

@task(retries=3, retry_delay_seconds=30)
def get_fip_tournaments():
    FipTournamentInterceptor().start()

@task(retries=3, retry_delay_seconds=30)
def get_premier_tournaments():
    PremierTournamentInterceptor().start()

@task
def tournaments_merger_enricher():
    TournamentsProcessor().start()

@task(retries=3, retry_delay_seconds=30)
def get_premier_matches():
    PremierMatchesInterceptor().start()

@task
def clean_matches_data():
    MatchesProcessor().start()

@task(retries=3, retry_delay_seconds=30)
def get_premier_players():
    PremierPlayersInterceptor().start()

@task
def build_players_datasets():
    PlayersDataBuilder().start()
    
@task
def players_enricher():
    PlayersEnricher().start()

@task
def pairs_enricher():
    PairsFeaturesEnricher().start()

@task
def data_exploiter():
    JsonToCsvConverter().process_all()

# -----------------------
# ETL SUBFLOWS
# -----------------------

@flow
def tournaments_flow():
    get_fip_tournaments()
    get_premier_tournaments()
    tournaments_merger_enricher()

@flow
def matches_flow():
    get_premier_matches()
    clean_matches_data()

@flow
def players_flow():
    get_premier_players()
    build_players_datasets()
    players_enricher()
    pairs_enricher()

@flow
def exploiter_flow():
    data_exploiter()

@flow
def data_pipeline_flow():
    tournaments_flow()
    matches_flow()
    players_flow()
    exploiter_flow()

# -----------------------
# ML TASKS & FLOWS
# -----------------------

@task
def prepare_api_data():
    APIDataPreparator().start()

@task
def train_models():
    ModelTrainer().train_and_evaluate()

@flow
def model_pipeline_flow():
    prepare_api_data()
    train_models()

# -----------------------
# FULL PIPELINE (ETL + ML)
# -----------------------

@flow(name="Full ETL + ML Pipeline", log_prints=True)
def full_pipeline():
    data_pipeline_flow()
    model_pipeline_flow()

if __name__ == "__main__":
    full_pipeline()


