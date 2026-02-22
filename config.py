import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not SUPABASE_URL:
    print("⚠️ Could not load SUPABASE_URL from .env file. Please ensure it is set correctly.")
else:
    print(f"✅ Supabase URL loaded successfully: {SUPABASE_URL}")

# ---- Premier Padel configuration constants
PREMIER_PADEL_TOURNAMENTS_URL = "https://premierpadel.com/en/tournaments"
PREMIER_PADEL_RESULTS_URL = "https://premierpadel.com/en/tournaments-results/"
PREMIER_PADEL_MATCH_STATS_URL = "https://premierpadel.com/en/matchstats/"

# ---- FIP configuration constants
FIP_CALENDAR_URL = "https://www.padelfip.com/calendar-premier-padel/"
FIP_MEN_RANKING_URL = "https://www.padelfip.com/ranking-male/"
FIP_MEN_RACE_URL = "https://www.padelfip.com/race-fip-top-100-male/"
FIP_PLAYER_URL = "https://www.padelfip.com/player/"

# ---- Open Meteo API configuration
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# ---- Request configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# ---- Prize Money Averages for Missing Data Imputation 
AVG_PRICE_MONEY = {'Finals': 600000, 'Major': 807900, 'P1': 474500, 'P2': 262250}

# ---- Years to Scrape for Premier Padel and FIP
YEARS_TO_SCRAPE = [2024, 2025, 2026]

# ---- Email Notification Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # App password for Gmail
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))