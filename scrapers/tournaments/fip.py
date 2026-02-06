import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Utils
from scrapers.utils import parse_dates, clean_money, calculate_status

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    FIP_CALENDAR_URL, 
    USER_AGENT, 
    YEARS_TO_SCRAPE, 
    AVG_PRICE_MONEY
)

class FipTournamentsScraper:
    """
    Docstring for FipTournamentsScraper
    Class to scrape tournament data from the FIP website.
    Methods:
        - __init__: Initializes the scraper with existing tournaments.
        - run: Main method to start scraping process.
        - _process_year: Processes tournaments for a specific year.
        - _get_links: Retrieves tournament links for a given year.
        - _scrape_details: Scrapes detailed information for a specific tournament.
    """
    
    def __init__(self, existing_slugs):
        self.headers = {"User-Agent": USER_AGENT}
        self.existing_slugs = existing_slugs
        self.scraped_data = []

    def run(self, last_date: datetime):
        print("📥 Scraping FIP tournaments...")
        print("==============================")
        years_to_scrape = [year for year in YEARS_TO_SCRAPE if not last_date or year >= last_date.year]
        for year in years_to_scrape:
            self._process_year(year)
        return self.scraped_data

    def _process_year(self, year):
        links = self._get_links(year)
        if not links:
            print(f"    No new tournaments found for year {year}.")
            return
        for link in links:
            print(f"    Scraping: {link}")
            details = self._scrape_details(link, year)
            if details:
                self.scraped_data.append(details)

    def _get_links(self, year):
        url = f"{FIP_CALENDAR_URL}?events-year={year}"
        print(f"    📅 Scanning FIP Calendar for {year}...")
        links = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/events/' in href and 'padelfip.com' in href:
                    slug = href.split('/')[-2] # type: ignore
                    if slug not in self.existing_slugs:
                        links.append(href)
            
            unique = list(set(links))
            print(f"   Found {len(unique)} tournament links.")
            return unique
        except Exception as e:
            print(f"    ❌ Error fetching calendar: {e}")
            return []

    def _scrape_details(self, url, season):
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.content, 'html.parser')

            # Tournament Source URL and Season
            data = {'source_url': url, 'season': str(season)}

            # Name and Location
            name_tag = soup.select_one('.event__name')
            data['name'] = name_tag.get_text(strip=True) if name_tag else None

            place_tag = soup.select_one('.event__place')
            data['city'], data['country'] = None, None
            if place_tag:
                parts = place_tag.get_text(strip=True).split('-')
                data['city'] = parts[0].strip()
                data['country'] = parts[1].strip() if len(parts) > 1 else None

            # Dates
            date_tag = soup.select_one('.event__date')
            if date_tag:
                data['start_date'], data['end_date'] = parse_dates(date_tag.get_text(strip=True))
            else:
                data['start_date'], data['end_date'] = None, None

            data['status'] = calculate_status(data['start_date'], data['end_date'])

            # Category
            name_upper = data['name'].upper() if data['name'] else ""
            if 'MAJOR' in name_upper: data['tournament_level'] = 'Major'
            elif 'P1' in name_upper: data['tournament_level'] = 'P1'
            elif 'P2' in name_upper: data['tournament_level'] = 'P2'
            elif 'FINALS' in name_upper: data['tournament_level'] = 'Finals'
            else: data['tournament_level'] = None

            # General Info
            gen_info_text = None
            gen_info_label = soup.find('span', class_='overview__title', string=lambda t: t and 'General info' in t) # type: ignore
            if gen_info_label:
                info_div = gen_info_label.find_next(class_='overview__listText')
                if info_div: gen_info_text = info_div.get_text(separator='\n', strip=True)

            # Helpers
            def get_overview(label):
                el = soup.find('span', class_='overview__title', string=lambda t: t and label in t) # type: ignore
                return el.find_next('p').get_text(strip=True) if el and el.find_next('p') else None # type: ignore
            data['venue'] = None
            data['balls_used'] = None
            data['venue_type'] = None

            # Venue
            data['venue'] = get_overview('Venue')
            if not data['venue'] and gen_info_text:
                for line in gen_info_text.split('\n'):
                    if 'VENUE' in line.upper() and 'VENUE TYPE' not in line.upper():
                        data['venue'] = re.sub(r'^VENUE\s*[:\.]?\s*', '', line, flags=re.IGNORECASE).strip()
                        break

            # Balls
            data['balls_used'] = get_overview('Balls')
            if not data['balls_used'] and gen_info_text:
                for line in gen_info_text.split('\n'):
                    if 'BALL' in line.upper():
                        clean_ball = re.sub(r'^.*BALLS?\s*[:\.]?\s*', '', line, flags=re.IGNORECASE)
                        if clean_ball: data['balls_used'] = clean_ball.strip()
                        break

            # Venue Type
            cond_text = get_overview('Court conditions') or gen_info_text
            if cond_text:
                if 'indoor' in cond_text.lower(): data['venue_type'] = 'indoor'
                elif 'outdoor' in cond_text.lower(): data['venue_type'] = 'outdoor'

            # Prize Money
            prize = clean_money(get_overview('Prize Money'))
            if not prize:
                data['prize_money'] = AVG_PRICE_MONEY[data['tournament_level']] if data['tournament_level'] else None
            else:
                data['prize_money'] = prize

            return data

        except Exception as e:
            print(f"⚠️ Failed to scrape {url}: {e}")
            return None