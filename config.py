import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not SUPABASE_URL:
    print("⚠️ Error: No se ha podido cargar SUPABASE_URL desde el .env")
else:
    print(f"✅ Configuración cargada para: {SUPABASE_URL}")

# ------------------ Predictive Model Path ------------------
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# ---- Premier Padel configuration constants
PREMIER_PADEL_TOURNAMENTS_URL = "https://premierpadel.com/en/tournaments"
PREMIER_PADEL_RESULTS_URL = "https://premierpadel.com/en/tournaments-results/"
PREMIER_PADEL_MATCH_STATS_URL = "https://premierpadel.com/en/matchstats/"

# ---- FIP configuration constants
FIP_CALENDAR_URL = "https://www.padelfip.com/calendar-premier-padel/"
FIP_MEN_RANKING_URL = "https://www.padelfip.com/ranking-male/"
FIP_PLAYER_URL = "https://www.padelfip.com/player/"
AVG_PRICE_MONEY = {'Finals': 600000, 'Major': 807900, 'P1': 474500, 'P2': 262250}
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# ---- Request configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
YEARS_TO_SCRAPE = [2024, 2025, 2026]
MONTHS_TO_SCRAPE = ["January", "February", "March", "April", "May", "June", 
                    "July", "August", "September", "October", "November", "December"]

# ---- Models
ML_MODELS = os.path.join(BACKEND, "models")
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