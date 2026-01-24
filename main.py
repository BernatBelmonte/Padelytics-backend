import os
import sys
import pickle
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ML_MODELS,
    EXPECTED_FEATURES,
    EXP_DYNAMIC_PAIRS_FILE,
    EXP_DYNAMIC_PLAYERS_FILE,
    EXP_STATIC_PLAYERS_FILE,
    EXP_TOURNAMENTS_FILE,
    EXP_MATCHES_FILE,
    API_DATA_FILE,
)

import pandas as pd
import numpy as np

# --- ADD THIS HELPER FUNCTION ---
def clean_and_stringify(df):
    """
    Cleans the dataframe by filling NaNs based on column type,
    without converting the entire dataframe to string (preserving dates).
    """
    if df is None or df.empty:
        return df

    # 1. Fill Numeric columns (int/float) with -999999
    # This prevents 'nan' in JSON for numbers
    num_cols = df.select_dtypes(include=['number']).columns
    if len(num_cols) > 0:
        df[num_cols] = df[num_cols].fillna(-999999)

    # 2. Fill Boolean columns with False
    bool_cols = df.select_dtypes(include=['bool']).columns
    if len(bool_cols) > 0:
        df[bool_cols] = df[bool_cols].fillna(False)

    # 3. Fill Object (String) columns with "Unknown"
    # This targets text columns like city, venue, etc.
    # Note: If a column is object but contains dates (strings), it will also get 'Unknown'.
    obj_cols = df.select_dtypes(include=['object']).columns
    if len(obj_cols) > 0:
        df[obj_cols] = df[obj_cols].fillna("Unknown")

    return df
# Diccionario global para guardar los activos cargados
ml_assets = {}

def clean_val(val, default="N/A"):
    if pd.isna(val): return default
    return val

def get_score_str(row):
    """Construye el string del marcador 6-2, 6-3 etc."""
    sets = []
    for i in range(1, 4):
        s1 = row.get(f'team1_set{i}')
        s2 = row.get(f'team2_set{i}')
        if pd.notna(s1) and pd.notna(s2):
            sets.append(f"{int(s1)}-{int(s2)}")
    return " ".join(sets) if sets else "N/D"

def format_team_name(slug):
    if not isinstance(slug, str) or pd.isna(slug): return "Equipo Desconocido"
    parts = slug.split('-')
    if len(parts) >= 4:
        p1 = " ".join(parts[:2]).title()
        p2 = " ".join(parts[2:]).title()
        return f"{p1} / {p2}"
    return slug.replace('-', ' ').title()

def get_team_streak(df, team_slug, limit=5):
    if pd.isna(team_slug): return []
    team_matches = df[(df['team1_slug'] == team_slug) | (df['team2_slug'] == team_slug)].copy()
    team_matches['date'] = pd.to_datetime(team_matches['date'])
    team_matches = team_matches.sort_values('date', ascending=False).head(limit)
    
    streak = []
    for _, row in team_matches.iterrows():
        if row['team1_slug'] == team_slug:
            streak.append('W' if row['target_team1_wins'] == 1 else 'L')
        else:
            streak.append('W' if row['target_team1_wins'] == 0 else 'L')
    return streak[::-1]

def format_birth_date(value):
    """Convierte fechas de nacimiento DD/MM/YYYY a YYYY-MM-DD."""
    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.strptime(value, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return value

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- INICIANDO PADELYTICS ENGINE ---")
    model_path = os.path.join(ML_MODELS, "voting_soft_model.pkl")
    if os.path.exists(API_DATA_FILE):
        ml_assets["df"] = pd.read_csv(API_DATA_FILE)
        print(f"✅ Dataset cargado")
    else:
        print("Api data doesn't exist")
    if os.path.exists(model_path):
        try:
            with open(model_path, 'rb') as f:
                ml_assets["model"] = pickle.load(f)
            print(f"✅ Modelo cargado")
        except: print(f"⚠️ Error modelo")
    else:
        print("Model doesn't exist")

    # Cargar datos de explotación para la API REST
    try:
        if os.path.exists(EXP_DYNAMIC_PLAYERS_FILE):
            ml_assets["dynamic_players"] = pd.read_csv(
                EXP_DYNAMIC_PLAYERS_FILE,
                parse_dates=["snapshot_date"],
            )
            ml_assets["dynamic_players"] = clean_and_stringify(ml_assets["dynamic_players"])
            print("✅ dynamic_players.csv cargado")
        else:
            print("dynamic_players.csv no encontrado")

        if os.path.exists(EXP_STATIC_PLAYERS_FILE):
            ml_assets["static_players"] = pd.read_csv(EXP_STATIC_PLAYERS_FILE)
            ml_assets["static_players"] = clean_and_stringify(ml_assets["static_players"])
            print("✅ static_players.csv cargado")
        else:
            print("static_players.csv no encontrado")

        if os.path.exists(EXP_DYNAMIC_PAIRS_FILE):
            ml_assets["dynamic_pairs"] = pd.read_csv(
                EXP_DYNAMIC_PAIRS_FILE,
                parse_dates=["snapshot_date"],
            )
            ml_assets["dynamic_pairs"] = clean_and_stringify(ml_assets["dynamic_pairs"])
            print("✅ dynamic_pairs.csv cargado")
        else:
            print("dynamic_pairs.csv no encontrado")

        if os.path.exists(EXP_TOURNAMENTS_FILE):
            ml_assets["tournaments"] = pd.read_csv(
                EXP_TOURNAMENTS_FILE,
                parse_dates=["start_date_utc", "end_date_utc"],
            )
            ml_assets["tournaments"] = clean_and_stringify(ml_assets["tournaments"])
            print("✅ tournaments.csv cargado")
        else:
            print("tournaments.csv no encontrado")

        if os.path.exists(EXP_MATCHES_FILE):
            ml_assets["matches"] = pd.read_csv(
                EXP_MATCHES_FILE,
                parse_dates=["date"],
            )
            ml_assets["matches"] = clean_and_stringify(ml_assets["matches"])
            print("✅ matches.csv cargado")
        else:
            print("matches.csv no encontrado")
    except Exception as e:
        print(f"⚠️ Error cargando datos de explotación: {e}")
    yield
    ml_assets.clear()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/ranking")
async def get_ranking():
    """Devuelve el ranking actual de jugadores."""
    df_dy = ml_assets.get("dynamic_players")
    latest_ts = df_dy["snapshot_date"].max() # type: ignore
    latest_df = df_dy[df_dy["snapshot_date"] == latest_ts].copy() # type: ignore
    df_st = ml_assets.get("static_players")
    df = latest_df.merge(
        df_st,
        on=["player_id", "slug", "name", "player_code"],
        how="left",
    )
    if df is None:
        return []
    df = df.sort_values("points", ascending=False)
    ranking = []
    for _, row in df.iterrows():
        ranking.append({
            "player_id": int(row["player_id"]),
            "name": row["name"],
            "slug": row["slug"],
            "country": row.get("country"),
            "points": int(row["points"]) if pd.notna(row["points"]) else None,
        })
    return ranking

@app.get("/api/h2h/{slug1}/{slug2}")
async def get_h2h(slug1: str, slug2: str):
    df = ml_assets["df"]
    h2h_df = df[((df['team1_slug'] == slug1) & (df['team2_slug'] == slug2)) | ((df['team1_slug'] == slug2) & (df['team2_slug'] == slug1))].copy()
    h2h_df['date'] = pd.to_datetime(h2h_df['date'])
    h2h_df = h2h_df.sort_values('date', ascending=False).head(5)
    
    history = []
    for _, row in h2h_df.iterrows():
        history.append({
            "date": row['date'].strftime("%Y-%m-%d"),
            "team1": format_team_name(row['team1_slug']),
            "team2": format_team_name(row['team2_slug']),
            "winner": format_team_name(row['team1_slug']) if row['target_team1_wins'] == 1 else format_team_name(row['team2_slug']),
            "score": get_score_str(row),
            "country": clean_val(row['country']),
            "city": clean_val(row['city']),
            "tournament": clean_val(row['full_name']),
            "round": clean_val(row['round_name'])
        })
    return history

@app.get("/api/team-history/{slug}")
async def get_team_history(slug: str):
    if "df" not in ml_assets: return []
    df = ml_assets["df"]
    history_df = df[(df['team1_slug'] == slug) | (df['team2_slug'] == slug)].copy()
    history_df['date'] = pd.to_datetime(history_df['date'])
    history_df = history_df.sort_values('date', ascending=False).head(10)
    
    results = []
    for _, row in history_df.iterrows():
        is_t1 = row['team1_slug'] == slug
        won = (row['target_team1_wins'] == 1) if is_t1 else (row['target_team1_wins'] == 0)
        results.append({
            "date": row['date'].strftime("%Y-%m-%d"),
            "team1": format_team_name(slug),
            "team2": format_team_name(row['team2_slug'] if is_t1 else row['team1_slug']),
            "winner": format_team_name(slug) if won else format_team_name(row['team2_slug'] if is_t1 else row['team1_slug']),
            "score": get_score_str(row),
            "country": clean_val(row['country']),
            "city": clean_val(row['city']),
            "tournament": clean_val(row['full_name']),
            "round": clean_val(row['round_name'])
        })
    return results


@app.get("/api/players")
async def get_players():
    """Devuelve todos los jugadores con sus stats en el último snapshot disponible."""
    dyn = ml_assets.get("dynamic_players")
    stat = ml_assets.get("static_players")
    if dyn is None or stat is None:
        return []

    latest_ts = dyn["snapshot_date"].max()
    dyn_latest = dyn[dyn["snapshot_date"] == latest_ts].copy()

    merged = dyn_latest.merge(
        stat,
        on=["player_id", "slug", "name", "player_code"],
        how="left",
    )

    players = []
    for _, row in merged.iterrows():
        players.append({
            "player_id": int(row["player_id"]),
            "player_code": row["player_code"],
            "name": row["name"],
            "slug": row["slug"],
            "country": row.get("country"),
            "height": row.get("height"),
            "position": row.get("position"),
            "birth_date": format_birth_date(row.get("birth_date")),
            "snapshot_date": row["snapshot_date"].strftime("%Y-%m-%d"),
            "points": int(row["points"]) if pd.notna(row["points"]) else None,
        })
    return players


@app.get("/api/players/{player_slug}")
async def get_player(player_slug: str):
    """Devuelve un jugador concreto en el último snapshot global."""
    dyn = ml_assets.get("dynamic_players")
    stat = ml_assets.get("static_players")
    if dyn is None or stat is None:
        return {"error": "No hay datos de jugadores"}

    latest_ts = dyn["snapshot_date"].max()
    dyn_latest = dyn[(dyn["snapshot_date"] == latest_ts) & (dyn["slug"] == player_slug)].copy()
    if dyn_latest.empty:
        return {"error": "Player not found"}

    merged = dyn_latest.merge(
        stat,
        on=["player_id", "slug", "name", "player_code"],
        how="left",
    ).iloc[0]

    return {
        "player_id": int(merged["player_id"]),
        "player_code": merged["player_code"],
        "name": merged["name"],
        "slug": merged["slug"],
        "country": merged.get("country"),
        "height": merged.get("height"),
        "position": merged.get("position"),
        "birth_date": format_birth_date(merged.get("birth_date")),
        "snapshot_date": merged["snapshot_date"].strftime("%Y-%m-%d"),
        "points": int(merged["points"]) if pd.notna(merged["points"]) else None,
    }


@app.get("/api/players/{player_slug}/history")
async def get_player_history(player_slug: str):
    """Devuelve el histórico completo de un jugador (todos los snapshots)."""
    dyn = ml_assets.get("dynamic_players")
    stat = ml_assets.get("static_players")
    if dyn is None or stat is None:
        return []

    dyn_player = dyn[dyn["slug"] == player_slug].copy()
    if dyn_player.empty:
        return []

    merged = dyn_player.merge(
        stat,
        on=["player_id", "slug", "name", "player_code"],
        how="left",
    ).sort_values("snapshot_date")

    history = []
    for _, row in merged.iterrows():
        history.append({
            "player_id": int(row["player_id"]),
            "player_code": row["player_code"],
            "name": row["name"],
            "slug": row["slug"],
            "country": row.get("country"),
            "height": row.get("height"),
            "position": row.get("position"),
            "birth_date": format_birth_date(row.get("birth_date")),
            "snapshot_date": row["snapshot_date"].strftime("%Y-%m-%d"),
            "points": int(row["points"]) if pd.notna(row["points"]) else None,
        })
    return history


@app.get("/api/tournaments")
async def get_tournaments():
    """Devuelve todos los torneos disponibles."""
    t_df = ml_assets.get("tournaments")
    if t_df is None:
        return []

    tournaments = []
    for _, row in t_df.iterrows():
        tournaments.append({
            "tournament_id": int(row["tournaments_id"]),
            "event_code": row.get("event_code"),
            "full_name": row.get("full_name"),
            "slug": row.get("slug"),
            "city": row.get("city"),
            "country": row.get("country"),
            "country_code": row.get("country_code"),
            "status": row.get("status"),
            "year": int(row["year"]) if pd.notna(row.get("year")) else None,
            "tournament_level": row.get("tournament_level"),
            "venue": row.get("venue"),
            "venue_type": row.get("venue_type"),
            "balls_used": row.get("balls_used"),
            "prize_money_fip": float(row["prize_money_fip"]) if pd.notna(row.get("prize_money_fip")) else None,
            "start_date_utc": row["start_date_utc"].strftime("%Y-%m-%d") if not pd.isna(row.get("start_date_utc")) else None,
            "end_date_utc": row["end_date_utc"].strftime("%Y-%m-%d") if not pd.isna(row.get("end_date_utc")) else None,
            "altitude": float(row["altitude"]) if pd.notna(row.get("altitude")) else None,
            "avg_temperature": float(row["avg_temperature"]) if pd.notna(row.get("avg_temperature")) else None,
            "avg_humidity": float(row["avg_humidity"]) if pd.notna(row.get("avg_humidity")) else None,
            "court_speed_index": float(row["court_speed_index"]) if pd.notna(row.get("court_speed_index")) else None,
        })
    return tournaments


@app.get("/api/tournaments/{tournament_id}")
async def get_tournament(tournament_id: int):
    """Devuelve un torneo concreto por ID."""
    t_df = ml_assets.get("tournaments")
    if t_df is None:
        return {"error": "No hay datos de torneos"}

    row = t_df[t_df["tournaments_id"] == tournament_id]
    if row.empty:
        return {"error": "Tournament not found"}
    
    tournaments = []
    for _, row in row.iterrows():
        tournaments.append({
            "tournament_id": int(row["tournaments_id"]),
            "event_code": row.get("event_code"),
            "full_name": row.get("full_name"),
            "slug": row.get("slug"),
            "city": row.get("city"),
            "country": row.get("country"),
            "country_code": row.get("country_code"),
            "status": row.get("status"),
            "year": int(row["year"]) if pd.notna(row.get("year")) else None,
            "tournament_level": row.get("tournament_level"),
            "venue": row.get("venue"),
            "venue_type": row.get("venue_type"),
            "balls_used": row.get("balls_used"),
            "prize_money_fip": float(row["prize_money_fip"]) if pd.notna(row.get("prize_money_fip")) else None,
            "start_date_utc": row["start_date_utc"].strftime("%Y-%m-%d") if not pd.isna(row.get("start_date_utc")) else None,
            "end_date_utc": row["end_date_utc"].strftime("%Y-%m-%d") if not pd.isna(row.get("end_date_utc")) else None,
            "altitude": float(row["altitude"]) if pd.notna(row.get("altitude")) else None,
            "avg_temperature": float(row["avg_temperature"]) if pd.notna(row.get("avg_temperature")) else None,
            "avg_humidity": float(row["avg_humidity"]) if pd.notna(row.get("avg_humidity")) else None,
            "court_speed_index": float(row["court_speed_index"]) if pd.notna(row.get("court_speed_index")) else None,
        })
    return tournaments[0]   


@app.get("/api/matches")
async def get_matches():
    """Devuelve todos los partidos históricos."""
    m_df = ml_assets.get("matches")
    if m_df is None:
        return []

    matches = []
    for _, row in m_df.iterrows():
        winner_team = int(row["winner_team"]) if pd.notna(row.get("winner_team")) else None
        if winner_team == 1:
            winner_slug = row["team1_slug"]
        elif winner_team == 2:
            winner_slug = row["team2_slug"]
        else:
            winner_slug = None

        matches.append({
            "match_id": int(row["tournaments_match_id"]),
            "tournament_id": int(row["tournament_id"]),
            "date": row["date"].strftime("%Y-%m-%d"),
            "match_code": row.get("matchId"),
            "round_name": row.get("round_name"),
            "team1_slug": row.get("team1_slug"),
            "team1_player1_slug": row.get("team1_player1_slug"),
            "team1_player2_slug": row.get("team1_player2_slug"),
            "team2_slug": row.get("team2_slug"),
            "team2_player1_slug": row.get("team2_player1_slug"),
            "team2_player2_slug": row.get("team2_player2_slug"),
            "winner_team": winner_team,
            "winner_slug": winner_slug,
            "team1_set1": row.get("team1_set1"),
            "team1_set2": row.get("team1_set2"),
            "team1_set3": row.get("team1_set3"),
            "team2_set1": row.get("team2_set1"),
            "team2_set2": row.get("team2_set2"),
            "team2_set3": row.get("team2_set3"),
            "score": get_score_str(row),
        })
    return matches


@app.get("/api/matches/{match_id}")
async def get_match(match_id: int):
    """Devuelve un partido concreto por ID."""
    m_df = ml_assets.get("matches")
    if m_df is None:
        return {"error": "No hay datos de partidos"}

    row = m_df[m_df["tournaments_match_id"] == match_id]

    matches = []
    for _, row in row.iterrows():
        winner_team = int(row["winner_team"]) if pd.notna(row.get("winner_team")) else None
        if winner_team == 1:
            winner_slug = row["team1_slug"]
        elif winner_team == 2:
            winner_slug = row["team2_slug"]
        else:
            winner_slug = None
        matches.append({
            "match_id": int(row["tournaments_match_id"]),
            "tournament_id": int(row["tournament_id"]),
            "date": row["date"].strftime("%Y-%m-%d"),
            "match_code": row.get("matchId"),
            "round_name": row.get("round_name"),
            "team1_slug": row.get("team1_slug"),
            "team1_player1_slug": row.get("team1_player1_slug"),
            "team1_player2_slug": row.get("team1_player2_slug"),
            "team2_slug": row.get("team2_slug"),
            "team2_player1_slug": row.get("team2_player1_slug"),
            "team2_player2_slug": row.get("team2_player2_slug"),
            "winner_team": winner_team,
            "winner_slug": winner_slug,
            "team1_set1": row.get("team1_set1"),
            "team1_set2": row.get("team1_set2"),
            "team1_set3": row.get("team1_set3"),
            "team2_set1": row.get("team2_set1"),
            "team2_set2": row.get("team2_set2"),
            "team2_set3": row.get("team2_set3"),
            "score": get_score_str(row),
        })
    return matches[0]
@app.get("/api/matches/team/{team_slug}")
async def get_matches_by_team(team_slug: str):
    """Devuelve todos los partidos donde participa un equipo (team_slug)."""
    m_df = ml_assets.get("matches")
    if m_df is None:
        return []

    team_df = m_df[(m_df["team1_slug"] == team_slug) | (m_df["team2_slug"] == team_slug)].copy()
    if team_df.empty:
        return []

    team_df = team_df.sort_values("date")

    matches = []
    for _, row in team_df.iterrows():
        winner_team = int(row["winner_team"]) if pd.notna(row.get("winner_team")) else None
        if winner_team == 1:
            winner_slug = row["team1_slug"]
        elif winner_team == 2:
            winner_slug = row["team2_slug"]
        else:
            winner_slug = None

        matches.append({
            "match_id": int(row["tournaments_match_id"]),
            "tournament_id": int(row["tournament_id"]),
            "date": row["date"].strftime("%Y-%m-%d"),
            "match_code": row.get("matchId"),
            "round_name": row.get("round_name"),
            "team1_slug": row.get("team1_slug"),
            "team1_player1_slug": row.get("team1_player1_slug"),
            "team1_player2_slug": row.get("team1_player2_slug"),
            "team2_slug": row.get("team2_slug"),
            "team2_player1_slug": row.get("team2_player1_slug"),
            "team2_player2_slug": row.get("team2_player2_slug"),
            "winner_team": winner_team,
            "winner_slug": winner_slug,
            "team1_set1": row.get("team1_set1"),
            "team1_set2": row.get("team1_set2"),
            "team1_set3": row.get("team1_set3"),
            "team2_set1": row.get("team2_set1"),
            "team2_set2": row.get("team2_set2"),
            "team2_set3": row.get("team2_set3"),
            "score": get_score_str(row),
        })
    return matches


@app.get("/api/tournaments/{tournament_id}/matches")
async def get_tournament_matches(tournament_id: int):
    """Devuelve todos los partidos de un torneo concreto."""
    m_df = ml_assets.get("matches")
    if m_df is None:
        return []

    t_matches = m_df[m_df["tournament_id"] == tournament_id].copy()
    if t_matches.empty:
        return []

    t_matches = t_matches.sort_values(["date", "matchId"])

    matches = []
    for _, row in t_matches.iterrows():
        winner_team = int(row["winner_team"]) if pd.notna(row.get("winner_team")) else None
        if winner_team == 1:
            winner_slug = row["team1_slug"]
        elif winner_team == 2:
            winner_slug = row["team2_slug"]
        else:
            winner_slug = None

        matches.append({
            "match_id": int(row["tournaments_match_id"]),
            "tournament_id": int(row["tournament_id"]),
            "date": row["date"].strftime("%Y-%m-%d"),
            "match_code": row.get("matchId"),
            "round_name": row.get("round_name"),
            "team1_slug": row.get("team1_slug"),
            "team1_player1_slug": row.get("team1_player1_slug"),
            "team1_player2_slug": row.get("team1_player2_slug"),
            "team2_slug": row.get("team2_slug"),
            "team2_player1_slug": row.get("team2_player1_slug"),
            "team2_player2_slug": row.get("team2_player2_slug"),
            "winner_team": winner_team,
            "winner_slug": winner_slug,
            "team1_set1": row.get("team1_set1"),
            "team1_set2": row.get("team1_set2"),
            "team1_set3": row.get("team1_set3"),
            "team2_set1": row.get("team2_set1"),
            "team2_set2": row.get("team2_set2"),
            "team2_set3": row.get("team2_set3"),
            "score": get_score_str(row),
        })
    return matches

@app.get("/api/pairs")
async def get_pairs():
    """Devuelve todas las parejas en el último snapshot disponible global."""
    p_df = ml_assets.get("dynamic_pairs")
    if p_df is None:
        return []

    latest_ts = p_df["snapshot_date"].max()
    latest = p_df[p_df["snapshot_date"] == latest_ts].copy()

    pairs = []
    for _, row in latest.iterrows():
        pairs.append({
            "snapshot_date": row["snapshot_date"].strftime("%Y-%m-%d"),
            "pair_id": row.get("pair_id"),
            "pair_code": row.get("pair_code"),
            "pair_slug": row.get("pair_slug"),
            "total_points": row.get("total_points"),
            "p1_id": row.get("p1_id"),
            "p1_code": row.get("p1_code"),
            "p1_name": row.get("p1_name"),
            "p1_slug": row.get("p1_slug"),
            "p2_id": row.get("p2_id"),
            "p2_code": row.get("p2_code"),
            "p2_name": row.get("p2_name"),
            "p2_slug": row.get("p2_slug"),
            "points_behind_leader": row.get("points_behind_leader"),
            "is_number_one": bool(row.get("is_number_one")) if not pd.isna(row.get("is_number_one")) else None,
            "rank_change": row.get("rank_change"),
            "points_change": row.get("points_change"),
            "is_new_pair": bool(row.get("is_new_pair")) if not pd.isna(row.get("is_new_pair")) else None,
            "partnership_time_days": row.get("partnership_time_days"),
            "tournaments_played_together": row.get("tournaments_played_together"),
            "form_guide": row.get("form_guide"),
            "streak_numeric": row.get("streak_numeric"),
            "matches_last_14_days": row.get("matches_last_14_days"),
            "days_since_last_match": row.get("days_since_last_match"),
            "average_round_value": row.get("average_round_value"),
            "finals_conversion_rate": row.get("finals_conversion_rate"),
            "season_matches_played": row.get("season_matches_played"),
            "season_win_pct": row.get("season_win_pct"),
            "stats_confidence": row.get("stats_confidence"),
            "dominance_ratio": row.get("dominance_ratio"),
            "straight_sets_win_rate": row.get("straight_sets_win_rate"),
            "avg_games_conceded_per_set": row.get("avg_games_conceded_per_set"),
            "tie_break_win_pct": row.get("tie_break_win_pct"),
            "closing_efficiency": row.get("closing_efficiency"),
            "comeback_rate": row.get("comeback_rate"),
        })
    return pairs


@app.get("/api/pairs/{pair_slug}")
async def get_pair(pair_slug: str):
    """Devuelve una pareja concreta en el último snapshot global (si existe)."""
    p_df = ml_assets.get("dynamic_pairs")
    if p_df is None:
        return {"error": "No hay datos de parejas"}

    latest_ts = p_df["snapshot_date"].max()
    pair_df = p_df[(p_df["snapshot_date"] == latest_ts) & (p_df["pair_slug"] == pair_slug)].copy()
    if pair_df.empty:
        return {"error": "Pair not found"}
    pairs = []
    for _, row in pair_df.iterrows():
        pairs.append({
            "snapshot_date": row["snapshot_date"].strftime("%Y-%m-%d"),
            "pair_id": row.get("pair_id"),
            "pair_code": row.get("pair_code"),
            "pair_slug": row.get("pair_slug"),
            "total_points": row.get("total_points"),
            "p1_id": row.get("p1_id"),
            "p1_code": row.get("p1_code"),
            "p1_name": row.get("p1_name"),
            "p1_slug": row.get("p1_slug"),
            "p2_id": row.get("p2_id"),
            "p2_code": row.get("p2_code"),
            "p2_name": row.get("p2_name"),
            "p2_slug": row.get("p2_slug"),
            "points_behind_leader": row.get("points_behind_leader"),
            "is_number_one": bool(row.get("is_number_one")) if not pd.isna(row.get("is_number_one")) else None,
            "rank_change": row.get("rank_change"),
            "points_change": row.get("points_change"),
            "is_new_pair": bool(row.get("is_new_pair")) if not pd.isna(row.get("is_new_pair")) else None,
            "partnership_time_days": row.get("partnership_time_days"),
            "tournaments_played_together": row.get("tournaments_played_together"),
            "form_guide": row.get("form_guide"),
            "streak_numeric": row.get("streak_numeric"),
            "matches_last_14_days": row.get("matches_last_14_days"),
            "days_since_last_match": row.get("days_since_last_match"),
            "average_round_value": row.get("average_round_value"),
            "finals_conversion_rate": row.get("finals_conversion_rate"),
            "season_matches_played": row.get("season_matches_played"),
            "season_win_pct": row.get("season_win_pct"),
            "stats_confidence": row.get("stats_confidence"),
            "dominance_ratio": row.get("dominance_ratio"),
            "straight_sets_win_rate": row.get("straight_sets_win_rate"),
            "avg_games_conceded_per_set": row.get("avg_games_conceded_per_set"),
            "tie_break_win_pct": row.get("tie_break_win_pct"),
            "closing_efficiency": row.get("closing_efficiency"),
            "comeback_rate": row.get("comeback_rate"),
        })
    return pairs


@app.get("/api/pairs/{pair_slug}/history")
async def get_pair_history(pair_slug: str):
    """Devuelve el histórico completo de una pareja (todos los snapshots)."""
    p_df = ml_assets.get("dynamic_pairs")
    if p_df is None:
        return []

    pair_df = p_df[p_df["pair_slug"] == pair_slug].copy()
    if pair_df.empty:
        return []

    pair_df = pair_df.sort_values("snapshot_date")

    history = []
    for _, row in pair_df.iterrows():
        history.append({
            "snapshot_date": row["snapshot_date"].strftime("%Y-%m-%d"),
            "pair_id": row.get("pair_id"),
            "pair_code": row.get("pair_code"),
            "pair_slug": row.get("pair_slug"),
            "total_points": row.get("total_points"),
            "p1_id": row.get("p1_id"),
            "p1_code": row.get("p1_code"),
            "p1_name": row.get("p1_name"),
            "p1_slug": row.get("p1_slug"),
            "p2_id": row.get("p2_id"),
            "p2_code": row.get("p2_code"),
            "p2_name": row.get("p2_name"),
            "p2_slug": row.get("p2_slug"),
            "points_behind_leader": row.get("points_behind_leader"),
            "is_number_one": bool(row.get("is_number_one")) if not pd.isna(row.get("is_number_one")) else None,
            "rank_change": row.get("rank_change"),
            "points_change": row.get("points_change"),
            "is_new_pair": bool(row.get("is_new_pair")) if not pd.isna(row.get("is_new_pair")) else None,
            "partnership_time_days": row.get("partnership_time_days"),
            "tournaments_played_together": row.get("tournaments_played_together"),
            "form_guide": row.get("form_guide"),
            "streak_numeric": row.get("streak_numeric"),
            "matches_last_14_days": row.get("matches_last_14_days"),
            "days_since_last_match": row.get("days_since_last_match"),
            "average_round_value": row.get("average_round_value"),
            "finals_conversion_rate": row.get("finals_conversion_rate"),
            "season_matches_played": row.get("season_matches_played"),
            "season_win_pct": row.get("season_win_pct"),
            "stats_confidence": row.get("stats_confidence"),
            "dominance_ratio": row.get("dominance_ratio"),
            "straight_sets_win_rate": row.get("straight_sets_win_rate"),
            "avg_games_conceded_per_set": row.get("avg_games_conceded_per_set"),
            "tie_break_win_pct": row.get("tie_break_win_pct"),
            "closing_efficiency": row.get("closing_efficiency"),
            "comeback_rate": row.get("comeback_rate"),
        })
    return history

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)