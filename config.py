import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Localizamos la ruta de este archivo (config.py)
# 2. Subimos un nivel o buscamos el .env donde esté
# Si el .env está en la raíz de 'backend', y config.py también:
env_path = Path(__file__).parent / ".env"

# Cargamos el archivo .env explícitamente
load_dotenv(dotenv_path=env_path)

# Ahora os.getenv ya podrá leer los valores
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Debug opcional (bórralo después de comprobar)
if not SUPABASE_URL:
    print("⚠️ Error: No se ha podido cargar SUPABASE_URL desde el .env")
else:
    print(f"✅ Configuración cargada para: {SUPABASE_URL}")
# ------------------ Predictive Model Path ------------------
PREDICTIVE_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# ---- Premier Padel configuration constants
PREMIER_PADEL_TOURNAMENTS_URL = "https://premierpadel.com/en/tournaments"
PREMIER_PADEL_RESULTS_URL = "https://premierpadel.com/en/tournaments-results/"
PREMIER_PADEL_MATCH_STATS_URL = "https://premierpadel.com/en/matchstats/"

# ---- FIP configuration constants
FIP_CALENDAR_URL = "https://www.padelfip.com/calendar-premier-padel/"
FIP_PLAYER_URL = "https://www.padelfip.com/player/"
AVG_PRICE_MONEY = {'Finals': 600000, 'Major': 807900, 'P1': 474500, 'P2': 262250}
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# ---- Data file paths
RAW_DATA_DIR = os.path.join(PREDICTIVE_MODEL_PATH, "data/raw")
CLEAN_DATA_DIR = os.path.join(PREDICTIVE_MODEL_PATH, "data/clean")
EXPLOITATION_DATA_DIR = os.path.join(PREDICTIVE_MODEL_PATH, "data/exploitation")

# Raw data files
RAW_PREMIER_PADEL_TOURNAMENTS_FILE = os.path.join(RAW_DATA_DIR, "premier_tournaments.json")
RAW_FIP_TOURNAMENTS_FILE = os.path.join(RAW_DATA_DIR, "fip_tournaments.json")
RAW_PREMIER_PADEL_MATCHES_FILE = os.path.join(RAW_DATA_DIR, "premier_matches.json")
RAW_PREMIER_PADEL_PLAYERS_FILE = os.path.join(RAW_DATA_DIR, "premier_players.json")

# Cleaned data files
MATCHES_FILE = os.path.join(CLEAN_DATA_DIR, "matches.json")
STATIC_PLAYERS_FILE = os.path.join(CLEAN_DATA_DIR, "static_players.json")
DYNAMIC_PLAYERS_FILE = os.path.join(CLEAN_DATA_DIR, "dynamic_players.json")
DYNAMIC_PAIRS_FILE = os.path.join(CLEAN_DATA_DIR, "dynamic_pairs.json")
DYNAMIC_PAIRS_FEATURED_FILE = os.path.join(CLEAN_DATA_DIR, "dynamic_pairs_featured.json")
# Joined and final data files from tournaments
JOINED_TOURNAMENTS_FILE = os.path.join(RAW_DATA_DIR, "tournaments_merged.json")
FINAL_TOURNAMENTS_FILE = os.path.join(CLEAN_DATA_DIR, "tournaments.json")

# Exploitaition data files
EXP_DYNAMIC_PAIRS_FILE = os.path.join(EXPLOITATION_DATA_DIR, "dynamic_pairs.csv")
EXP_DYNAMIC_PLAYERS_FILE = os.path.join(EXPLOITATION_DATA_DIR, "dynamic_players.csv")
EXP_STATIC_PLAYERS_FILE = os.path.join(EXPLOITATION_DATA_DIR, "static_players.csv")
EXP_TOURNAMENTS_FILE = os.path.join(EXPLOITATION_DATA_DIR, "tournaments.csv")
EXP_MATCHES_FILE = os.path.join(EXPLOITATION_DATA_DIR, "matches.csv")
API_DATA_FILE = os.path.join(EXPLOITATION_DATA_DIR, "api_data.csv")
MODEL_DATA_FILE = os.path.join(EXPLOITATION_DATA_DIR, "model_data.csv")

# ---- Request configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
YEARS_TO_SCRAPE = ["2024", "2025"]

# ---- Images
EDA_PATH = os.path.join(PREDICTIVE_MODEL_PATH, "images/eda")

# ---- Models
ML_MODELS = os.path.join(PREDICTIVE_MODEL_PATH, "models")
EXPECTED_FEATURES = [
    'match_quality_sum', 
    'court_speed_index', 
    'diff_log_total_points', 
    'diff_points_change', 
    'diff_tournaments_played_together', 
    'diff_matches_last_14_days', 
    'diff_finals_conversion_rate', 
    'diff_season_win_pct', 
    'diff_avg_games_conceded_per_set', 
    'diff_tie_break_win_pct', 
    'diff_comeback_rate', 
    'diff_avg_height'
]

# --------------- WEB APP CONFIGURATION ------------------
WEB_APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_app")