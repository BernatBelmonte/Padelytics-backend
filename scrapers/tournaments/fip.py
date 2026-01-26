import requests
import re
from bs4 import BeautifulSoup
import os
import sys

# Import relativo de utilidades
from scrapers.utils import parse_dates, clean_money, calculate_status, imput_value

# Importar configuración
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FIP_CALENDAR_URL, USER_AGENT, YEARS_TO_SCRAPE, AVG_PRICE_MONEY

class FipTournamentsScraper:
    def __init__(self, existing_tournaments):
        self.headers = {"User-Agent": USER_AGENT}
        self.existing_tournaments = existing_tournaments # Para imputar datos
        self.scraped_data = []

    def run(self):
        print("   📥 Scraping FIP tournaments...")
        print("    ==============================")
        for year in YEARS_TO_SCRAPE:
            self._process_year(year)
        return self.scraped_data

    def _process_year(self, year):
        links = self._get_links(year)
        allready_scraped = {t['fip_source_url'] for t in self.existing_tournaments}
        for link in links:
            if link in allready_scraped:
                print(f"    ⚠️ Already scraped, skipping: {link}")
                continue
            print(f"    🕷️ Scraping: {link}")
            details = self._scrape_details(link, year)
            if details:
                self.scraped_data.append(details)

    def _get_links(self, year):
        reference_slugs = {t['slug'] for t in self.existing_tournaments}
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
                    if slug not in reference_slugs:
                        links.append(href)
            
            unique = list(set(links))
            print(f"   Found {len(unique)} tournament links.")
            return unique
        except Exception as e:
            print(f"❌ Error fetching calendar: {e}")
            return []

    def _scrape_details(self, url, season):
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.content, 'html.parser')
            data = {'source_url': url, 'season': str(season)}

            # Nombre y Lugar
            name_tag = soup.select_one('.event__name')
            data['name'] = name_tag.get_text(strip=True) if name_tag else "Unknown"

            place_tag = soup.select_one('.event__place')
            if place_tag:
                parts = place_tag.get_text(strip=True).split('-')
                data['city'] = parts[0].strip()
                data['country'] = parts[1].strip() if len(parts) > 1 else "Unknown"
            else:
                data['city'], data['country'] = None, None

            # Fechas
            date_tag = soup.select_one('.event__date')
            if date_tag:
                data['start_date'], data['end_date'] = parse_dates(date_tag.get_text(strip=True))
            else:
                data['start_date'], data['end_date'] = None, None

            data['status'] = calculate_status(data['start_date'], data['end_date'])

            # Helpers internos de BS4
            def get_overview(label):
                el = soup.find('span', class_='overview__title', string=lambda t: t and label in t) # type: ignore
                return el.find_next('p').get_text(strip=True) if el and el.find_next('p') else None # type: ignore

            # Nivel
            name_upper = data['name'].upper()
            if 'MAJOR' in name_upper: data['tournament_level'] = 'Major'
            elif 'P1' in name_upper: data['tournament_level'] = 'P1'
            elif 'P2' in name_upper: data['tournament_level'] = 'P2'
            elif 'FINALS' in name_upper: data['tournament_level'] = 'Finals'
            else: data['tournament_level'] = 'Other'

            # Info General (backup para Venue/Balls)
            gen_info_text = None
            gen_info_label = soup.find('span', class_='overview__title', string=lambda t: t and 'General info' in t) # type: ignore
            if gen_info_label:
                info_div = gen_info_label.find_next(class_='overview__listText')
                if info_div: gen_info_text = info_div.get_text(separator='\n', strip=True)

            # Venue
            data['venue'] = get_overview('Venue')
            if not data['venue'] and gen_info_text:
                for line in gen_info_text.split('\n'):
                    if 'VENUE' in line.upper() and 'VENUE TYPE' not in line.upper():
                        data['venue'] = re.sub(r'^VENUE\s*[:\.]?\s*', '', line, flags=re.IGNORECASE).strip()
                        break
            if not data['venue']:
                data['venue'] = imput_value(data, 'venue', self.existing_tournaments)

            # Balls
            data['balls_used'] = get_overview('Balls')
            if not data['balls_used'] and gen_info_text:
                for line in gen_info_text.split('\n'):
                    if 'BALL' in line.upper():
                        clean_ball = re.sub(r'^.*BALLS?\s*[:\.]?\s*', '', line, flags=re.IGNORECASE)
                        if clean_ball: data['balls_used'] = clean_ball.strip()
                        break
            if not data['balls_used']:
                data['balls_used'] = imput_value(data, 'balls_used', self.existing_tournaments)

            # Venue Type
            cond_text = get_overview('Court conditions') or gen_info_text
            data['venue_type'] = None
            if cond_text:
                if 'indoor' in cond_text.lower(): data['venue_type'] = 'indoor'
                elif 'outdoor' in cond_text.lower(): data['venue_type'] = 'outdoor'
            if not data['venue_type']:
                data['venue_type'] = imput_value(data, 'venue_type', self.existing_tournaments)

            # Prize Money
            prize = clean_money(get_overview('Prize Money'))
            if not prize:
                data['prize_money'] = AVG_PRICE_MONEY.get(data['tournament_level'], None)
            else:
                data['prize_money'] = prize

            return data

        except Exception as e:
            print(f"⚠️ Failed to scrape {url}: {e}")
            return None