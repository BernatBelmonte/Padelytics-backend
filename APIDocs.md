# VoleAI 2.0 | API Documentation

Base URL (dev): `http://localhost:8000`

All responses are JSON.

---

## ⚠️ Important: Null Value Handling

This API uses special sentinel values to represent missing/null data in JSON responses:

| Data Type | Sentinel Value | Meaning |
|-----------|---------------|---------|
| **Numeric** (integer/float) | `-999999` | Value is null/unknown |
| **Boolean** | `false` | Value is null/unknown |
| **String** | `"Unknown"` | Value is null/unknown |

**Example:** If a player's `height` is `-999999`, it means the height data is not available.

---

## Ranking

### GET `/api/ranking`

**Description**  
Returns the current player ranking sorted by points (descending).

**Path params**  
- None

**Query params**  
- None

**Response (200)**  
Array of player ranking objects:

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | integer | Unique player identifier |
| `name` | string | Player full name |
| `slug` | string | URL-friendly player identifier (e.g. `arturo-coello`) |
| `country` | string \| `"Unknown"` | Player's country |
| `points` | integer \| null | Current ranking points |

---

## Players

### GET `/api/players`

**Description**  
Returns all players with their stats at the latest available snapshot date.

**Path params**  
- None

**Query params**  
- None

**Response (200)**  
Array of player objects:

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | integer | Unique player identifier |
| `player_code` | string | Internal player code |
| `name` | string | Player full name |
| `slug` | string | URL-friendly identifier (e.g. `arturo-coello`) |
| `country` | string \| `"Unknown"` | Player's country |
| `height` | number \| `-999999` | Height in cm. **-999999 = null** |
| `position` | string \| `"Unknown"` | Playing position ("Right" / "Left") |
| `birth_date` | string \| null | Birth date (`YYYY-MM-DD` format) |
| `snapshot_date` | string | Data snapshot date (`YYYY-MM-DD`) |
| `points` | integer \| null | Current ranking points |

---

### GET `/api/players/{player_slug}`

**Description**  
Returns the latest stats for a single player.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `player_slug` | string | Player slug (e.g. `arturo-coello`) |

**Query params**  
- None

**Response (200)**  
Single player object with the same structure as `/api/players`.

**Response (404)**  
```json
{ "error": "Player not found" }
```

---

### GET `/api/players/{player_slug}/history`

**Description**  
Returns all historical stats for a player across all snapshot dates (time series), ordered oldest → newest.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `player_slug` | string | Player slug |

**Query params**  
- None

**Response (200)**  
Array of player objects (same structure as `/api/players`) for different `snapshot_date` values.

**Response (404)**  
Returns empty array `[]` if player not found.

---

## Tournaments

### GET `/api/tournaments`

**Description**  
Returns all tournaments.

**Path params**  
- None

**Query params**  
- None

**Response (200)**  
Array of tournament objects:

| Field | Type | Description |
|-------|------|-------------|
| `tournament_id` | integer | Unique tournament identifier |
| `event_code` | string \| `"Unknown"` | Event code |
| `full_name` | string \| `"Unknown"` | Full tournament name |
| `slug` | string \| `"Unknown"` | URL-friendly identifier |
| `city` | string \| `"Unknown"` | Host city |
| `country` | string \| `"Unknown"` | Host country |
| `country_code` | string \| `"Unknown"` | ISO country code |
| `status` | string \| `"Unknown"` | Tournament status (e.g. "Active") |
| `year` | integer \| null | Tournament year |
| `tournament_level` | string \| `"Unknown"` | Level (e.g. "Major", "P1", "P2") |
| `venue` | string \| `"Unknown"` | Venue name |
| `venue_type` | string \| `"Unknown"` | "indoor" / "outdoor" |
| `balls_used` | string \| `"Unknown"` | Ball brand used |
| `prize_money_fip` | number \| null | Prize money (numeric) |
| `start_date_utc` | string \| null | Start date (`YYYY-MM-DD`) |
| `end_date_utc` | string \| null | End date (`YYYY-MM-DD`) |
| `altitude` | number \| null | Venue altitude in meters. **-999999 = null** |
| `avg_temperature` | number \| null | Average temperature. **-999999 = null** |
| `avg_humidity` | number \| null | Average humidity %. **-999999 = null** |
| `court_speed_index` | number \| null | Court speed index. **-999999 = null** |

---

### GET `/api/tournaments/{tournament_id}`

**Description**  
Returns details for a single tournament.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `tournament_id` | integer | Tournament identifier |

**Query params**  
- None

**Response (200)**  
Single tournament object (same structure as `/api/tournaments`).

**Response (404)**  
```json
{ "error": "Tournament not found" }
```

---

### GET `/api/tournaments/{tournament_id}/matches`

**Description**  
Returns all matches for a given tournament, sorted by date and match ID.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `tournament_id` | integer | Tournament identifier |

**Query params**  
- None

**Response (200)**  
Array of match objects (same structure as `/api/matches`).

**Response (404)**  
Returns empty array `[]` if tournament has no matches.

---

## Matches

### GET `/api/matches`

**Description**  
Returns all historical matches.

**Path params**  
- None

**Query params**  
- None

**Response (200)**  
Array of match objects:

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | integer | Unique match identifier |
| `tournament_id` | integer | Parent tournament ID |
| `date` | string | Match date (`YYYY-MM-DD`) |
| `match_code` | string \| `"Unknown"` | Internal match code |
| `round_name` | string \| `"Unknown"` | Round name (e.g. "Final", "Semi-Final") |
| `team1_slug` | string \| `"Unknown"` | Team 1 slug |
| `team1_player1_slug` | string \| `"Unknown"` | Team 1, Player 1 slug |
| `team1_player2_slug` | string \| `"Unknown"` | Team 1, Player 2 slug |
| `team2_slug` | string \| `"Unknown"` | Team 2 slug |
| `team2_player1_slug` | string \| `"Unknown"` | Team 2, Player 1 slug |
| `team2_player2_slug` | string \| `"Unknown"` | Team 2, Player 2 slug |
| `winner_team` | integer \| null | `1` = team1 won, `2` = team2 won |
| `winner_slug` | string \| null | Winning team's slug |
| `team1_set1` | number \| `-999999` | Team 1, Set 1 games. **-999999 = null** |
| `team1_set2` | number \| `-999999` | Team 1, Set 2 games. **-999999 = null** |
| `team1_set3` | number \| `-999999` | Team 1, Set 3 games. **-999999 = null** |
| `team2_set1` | number \| `-999999` | Team 2, Set 1 games. **-999999 = null** |
| `team2_set2` | number \| `-999999` | Team 2, Set 2 games. **-999999 = null** |
| `team2_set3` | number \| `-999999` | Team 2, Set 3 games. **-999999 = null** |
| `score` | string | Final score string (e.g. `"6-2 6-3"`) or `"N/D"` |

---

### GET `/api/matches/{match_id}`

**Description**  
Returns details for a single match.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `match_id` | integer | Match identifier (`tournaments_match_id`) |

**Query params**  
- None

**Response (200)**  
Single match object (same structure as `/api/matches`).

**Response (404)**  
```json
{ "error": "No hay datos de partidos" }
```

---

### GET `/api/matches/team/{team_slug}`

**Description**  
Returns all matches where the given team participated (as team1 or team2), sorted by date (oldest first).

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `team_slug` | string | Team slug (e.g. `agustin-tapia-arturo-coello`) |

**Query params**  
- None

**Response (200)**  
Array of match objects (same structure as `/api/matches`).

**Response (404)**  
Returns empty array `[]` if no matches found.

---

## Pairs (Teams)

Pair slug format: `<player1_slug>-<player2_slug>` (e.g. `arturo-coello-agustin-tapia`)

### GET `/api/pairs`

**Description**  
Returns all pairs with their stats at the latest available snapshot date.

**Path params**  
- None

**Query params**  
- None

**Response (200)**  
Array of pair objects:

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_date` | string | Data snapshot date (`YYYY-MM-DD`) |
| `pair_id` | string \| `"Unknown"` | Pair identifier (e.g. `"3-4"`) |
| `pair_code` | string \| `"Unknown"` | Internal pair code |
| `pair_slug` | string \| `"Unknown"` | URL-friendly pair identifier |
| `total_points` | number \| `-999999` | Combined ranking points. **-999999 = null** |
| `p1_id` | number \| `-999999` | Player 1 ID. **-999999 = null** |
| `p1_code` | string \| `"Unknown"` | Player 1 code |
| `p1_name` | string \| `"Unknown"` | Player 1 name |
| `p1_slug` | string \| `"Unknown"` | Player 1 slug |
| `p2_id` | number \| `-999999` | Player 2 ID. **-999999 = null** |
| `p2_code` | string \| `"Unknown"` | Player 2 code |
| `p2_name` | string \| `"Unknown"` | Player 2 name |
| `p2_slug` | string \| `"Unknown"` | Player 2 slug |
| `points_behind_leader` | number \| `-999999` | Points behind #1 pair. **-999999 = null** |
| `is_number_one` | boolean \| null | Is this the #1 ranked pair? |
| `rank_change` | number \| `-999999` | Rank change since last snapshot. **-999999 = null** |
| `points_change` | number \| `-999999` | Points change since last snapshot. **-999999 = null** |
| `is_new_pair` | boolean \| null | Is this a new partnership? |
| `partnership_time_days` | number \| `-999999` | Days as partners. **-999999 = null** |
| `tournaments_played_together` | number \| `-999999` | Tournaments played together. **-999999 = null** |
| `form_guide` | string \| `"Unknown"` | Recent form (e.g. `"W-L-W"`) |
| `streak_numeric` | number \| `-999999` | Current streak (+ for wins, - for losses). **-999999 = null** |
| `matches_last_14_days` | number \| `-999999` | Matches in last 14 days. **-999999 = null** |
| `days_since_last_match` | number \| `-999999` | Days since last match. **-999999 = null** |
| `average_round_value` | number \| `-999999` | Average round reached. **-999999 = null** |
| `finals_conversion_rate` | number \| `-999999` | % of finals won. **-999999 = null** |
| `season_matches_played` | number \| `-999999` | Matches played this season. **-999999 = null** |
| `season_win_pct` | number \| `-999999` | Season win percentage (0-1). **-999999 = null** |
| `stats_confidence` | number \| `-999999` | Confidence score for stats. **-999999 = null** |
| `dominance_ratio` | number \| `-999999` | Dominance ratio. **-999999 = null** |
| `straight_sets_win_rate` | number \| `-999999` | % of wins in straight sets. **-999999 = null** |
| `avg_games_conceded_per_set` | number \| `-999999` | Avg games lost per set. **-999999 = null** |
| `tie_break_win_pct` | number \| `-999999` | Tie-break win %. **-999999 = null** |
| `closing_efficiency` | number \| `-999999` | Match closing efficiency. **-999999 = null** |
| `comeback_rate` | number \| `-999999` | Comeback win rate. **-999999 = null** |

---

### GET `/api/pairs/{pair_slug}`

**Description**  
Returns the latest stats for a specific pair.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `pair_slug` | string | Pair slug (e.g. `arturo-coello-agustin-tapia`) |

**Query params**  
- None

**Response (200)**  
Array with single pair object (same structure as `/api/pairs`).

**Response (404)**  
```json
{ "error": "Pair not found" }
```

---

### GET `/api/pairs/{pair_slug}/history`

**Description**  
Returns full historical stats for a pair across all snapshots (time series), sorted oldest → newest.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `pair_slug` | string | Pair slug |

**Query params**  
- None

**Response (200)**  
Array of pair objects (same structure as `/api/pairs`) for different `snapshot_date` values.

**Response (404)**  
Returns empty array `[]` if pair not found.

---

## Head-to-Head & History

### GET `/api/h2h/{slug1}/{slug2}`

**Description**  
Returns head-to-head match history between two teams (last 5 matches), ordered newest → oldest.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `slug1` | string | Team 1 slug |
| `slug2` | string | Team 2 slug |

**Query params**  
- None

**Response (200)**  
Array of H2H match objects:

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Match date (`YYYY-MM-DD`) |
| `team1` | string | Formatted team 1 name |
| `team2` | string | Formatted team 2 name |
| `winner` | string | Formatted winner name |
| `score` | string | Score string (e.g. `"6-3 6-4"`) |
| `country` | string | Match country (or `"N/A"`) |
| `city` | string | Match city (or `"N/A"`) |
| `tournament` | string | Tournament name (or `"N/A"`) |
| `round` | string | Round name (or `"N/A"`) |

---

### GET `/api/team-history/{slug}`

**Description**  
Returns recent match history for a team (last 10 matches), ordered newest → oldest.

**Path params**  
| Param | Type | Description |
|-------|------|-------------|
| `slug` | string | Team slug |

**Query params**  
- None

**Response (200)**  
Array of match history objects:

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Match date (`YYYY-MM-DD`) |
| `team1` | string | Formatted requested team name |
| `team2` | string | Formatted opponent name |
| `winner` | string | Formatted winner name |
| `score` | string | Score string (e.g. `"6-3 6-4"`) |
| `country` | string | Match country (or `"N/A"`) |
| `city` | string | Match city (or `"N/A"`) |
| `tournament` | string | Tournament name (or `"N/A"`) |
| `round` | string | Round name (or `"N/A"`) |

**Response (404)**  
Returns empty array `[]` if no data available.

