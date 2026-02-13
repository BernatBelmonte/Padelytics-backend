# Padelytics Data Engine - ETL & Scraper Pipeline

This is the core data ingestion system for VoleAI. It manages the automated lifecycle of professional padel data, from raw web scraping to structured storage in Supabase.

## Key Features
### 1. Automated Task Scheduler
A calendar-driven logic that populates a `scheduled_tasks` table:
* **Players Scraper**: Triggered **3 days before** tournament start.
* **Tournaments Scraper**: Triggered **1 day before** tournament start (Syncs categories/locations).
* **Matches Scraper**: Triggered **3 days after** tournament end (Collects final results and 70+ performance metrics).

### 2. Data Enrichment
* **ArcGIS Geocoding**: Automatically converts city/country strings into Latitude/Longitude coordinates for map visualizations.
* **is_enriched Flag**: A boolean system to track which tournament records have been fully processed.

## Scraper Modules

| Scraper | Data Collected | Frequency |
| :--- | :--- | :--- |
| **Players** | Rank, points, age, hand, profile, and history. | Pre-Tournament |
| **Matches** | Winners, unforced errors, break points, set scores (10+ metrics). | Post-Tournament |
| **Tournaments** | Dates, categories (P1, P2, Major), city, and coordinates. | On Demand / Seasonal |

## Known Issue Fixes
* **Status 509 (Geopy)**: Switched from Nominatim to **ArcGIS** to avoid strict bandwidth limits and IP bans.
