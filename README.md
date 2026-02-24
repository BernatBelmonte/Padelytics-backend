# Padelytics Data Engine

Automated ETL pipeline for professional padel data. Scrapes player rankings, tournament info, and match statistics from Premier Padel and FIP sources, storing everything in Supabase.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Daily Runner                             │
│         (Executes scheduled tasks from scraper_tasks)           │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│    Players    │      │  Tournaments  │      │    Matches    │
│   Collector   │      │   Collector   │      │   Collector   │
└───────────────┘      └───────────────┘      └───────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌────────────────┐      ┌───────────────┐      ┌───────────────┐
│  FIP Scraper   │      │  FIP + Premier│      │Premier Scraper│
│ + Dynamic Pairs│      │  + Enricher   │      │               │
└────────────────┘      └───────────────┘      └───────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Data Enrichment     │
                    │ • ArcGIS Geocoding    │
                    │ • Weather Data        │
                    │ • Court Speed Index   │
                    └───────────────────────┘
```

## Usage

### Schedule Tasks (Run Once Per Season)

```bash
python -c "from utils.scrapers_scheduler import ScrapersScheduler; ScrapersScheduler().run()"
```

This populates the `scraper_tasks` table with:
- **Players**: 1 day before tournament + every Tuesday (skips tournament periods)
- **Tournaments**: 1 day before start + 2 days after end
- **Matches**: 3 days after tournament ends

### Run Daily Tasks

```bash
python daily_runner.py
```

Executes all tasks scheduled for today and sends an email summary.

### Run Individual Collectors

```bash
# Players
python -c "from scrapers.players.collector import PlayersCollector; PlayersCollector().start()"

# Tournaments
python -c "from scrapers.tournaments.collector import TournamentsCollector; TournamentsCollector().start()"

# Matches
python -c "from scrapers.matches.collector import MatchesCollector; MatchesCollector().start()"
```

## Project Structure

```
├── config.py                 # Environment & constants
├── daily_runner.py           # Task executor + email 
├── scrapers/
│   ├── players/
│   │   ├── collector.py      # Orchestrates player data pipeline
│   │   ├── fip.py            # FIP ranking scraper
│   │   └── dynamic_pairs.py  # Player partnership analysis
│   ├── tournaments/
│   │   ├── collector.py      # Orchestrates tournament pipeline
│   │   ├── fip.py            # FIP calendar scraper
│   │   ├── premier.py        # Premier Padel scraper
│   │   └── enricher.py       # Geocoding + weather enrichment
│   └── matches/
│       ├── collector.py      # Orchestrates match pipeline
│       └── premier.py        # Match stats scraper (70+ metrics)
└── utils/
    └── scrapers_scheduler.py # Season task scheduling logic
```

## Data Sources

| Source | Data | URL |
|--------|------|-----|
| FIP | Rankings, Player Profiles | padelfip.com |
| Premier Padel | Tournaments, Match Stats | premierpadel.com |
| Open-Meteo | Historical Weather | open-meteo.com |
| ArcGIS | Geocoding | arcgis.com |

## Scheduling Logic

The scheduler intelligently avoids redundant scraping:

1. **Tournament-based scheduling**: Players scraper runs 1 day before each tournament
2. **Weekly maintenance**: Players also run every Tuesday to catch ranking changes
3. **Conflict avoidance**: Tuesday scrapes are skipped if they fall within a tournament period (start date to 3 days after end)

## Database Tables

| Table | Purpose |
|-------|---------|
| `tournaments` | Tournament metadata, dates, locations, coordinates |
| `players` | Static player info (name, country, hand, image) |
| `players_dynamic` | Snapshots of rankings/points over time |
| `pairs_dynamic` | Snapshots of rankings, points and lots of statistics over time |
| `matches` | Match results with detailed statistics |
| `scraper_tasks` | Scheduled task queue with status tracking |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Geopy 509 errors | Already mitigated - uses ArcGIS instead of Nominatim |
| Empty scraper results | Verify source websites haven't changed structure |

## License
