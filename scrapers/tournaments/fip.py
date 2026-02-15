import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Set, Optional

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    AVG_PRICE_MONEY,
    FIP_CALENDAR_URL, 
    USER_AGENT, 
    YEARS_TO_SCRAPE, 
)

class FipTournamentsScraper:
    """
    A scraper designed to extract tournament data from the FIP Padel website.

    This class fetches the calendar page for each year, identifies tournament links,
    and then scrapes details from each tournament page, including name, location, dates,
    """
    def __init__(self, finished_tournaments: Set[str]):
        """
        Initializes the scraper with a set of finished tournament slugs to avoid re-scraping.

        Args:
            finished_tournaments: A set of tournament slugs that have already been
                processed and should be ignored during scraping.
        """
        self.headers = {"User-Agent": USER_AGENT}
        self.finished_tournaments: Set[str] = finished_tournaments
        self.scraped_data: List[Dict] = []

    def run(self, last_date: Optional[datetime]) -> List[Dict]:
        """
        Runs the scraping process for all years in YEARS_TO_SCRAPE that are greater than or equal to last_date.

        Args:
            last_date: The date of the last finished tournament. Only years 
                from this date forward will be processed.

        Returns:
            scraped_data: A list of dictionaries containing the raw tournament data objects
            scraped from each tournament page.
        """
        print("📥 Scraping FIP tournaments...")
        years_to_scrape = [year for year in YEARS_TO_SCRAPE if not last_date or year >= last_date.year]
        for year in years_to_scrape:
            self._process_year(year)
        print(f"------------------------------")
        return self.scraped_data

    def _process_year(self, year: int) -> None:
        """
        Processes a single year by fetching tournament links and scraping their details.

        Args:
            year: The year to process.
        """
        links = self._get_links(year)
        if not links:
            print(f"        No new tournaments found for year {year}.")
            return
        for link in links:
            print(f"        Scraping: {link}")
            details = self._scrape_details(link)
            if details:
                self.scraped_data.append(details)

    def _get_links(self, year: int) -> List[str]:
        """
        Fetches the calendar page for the given year and extracts tournament links that are not in the finished_tournaments set.

        Args:
            year: The year for which to fetch tournament links.
        Returns:
            A list of tournament URLs to scrape.
        """
        url = f"{FIP_CALENDAR_URL}?events-year={year}"
        print(f"    Scanning FIP Calendar for {year}:", end=" ")
        links = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/events/' in href and 'padelfip.com' in href:
                    slug = href.split('/')[-2] # type: ignore
                    if slug not in self.finished_tournaments:
                        links.append(href)
            
            unique = list(set(links))
            print(f"Found {len(unique)} tournaments.")
            return unique
        except Exception as e:
            print(f"    Error fetching calendar: {e}")
            return []

    def _scrape_details(self, url: str) -> Optional[Dict]:
        """
        Fetches the tournament page and extracts relevant details such as name, location, dates, venue, balls used, venue type, and prize money.

        Args:
            url: The URL of the tournament page to scrape.
        Returns:
            A dictionary containing the scraped tournament details, or None if scraping fails.
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.content, 'html.parser')
            data = {}
            
            # Fip slug & URL
            data['fip_url'] = url
            data['fip_slug'] = url.split('/')[-2] # type: ignore

            # Name
            name_tag = soup.select_one('.event__name')
            data['name'] = name_tag.get_text(strip=True) if name_tag else None
            
            # City & Country
            place_tag = soup.select_one('.event__place')
            data['city'], data['country'] = None, None
            if place_tag:
                parts = place_tag.get_text(strip=True).split('-')
                data['city'] = parts[0].strip()
                data['country'] = parts[1].strip() if len(parts) > 1 else None

             # Dates
            date_tag = soup.select_one('.event__date')
            if date_tag:
                data['start_date'], data['end_date'] = self._parse_dates(date_tag.get_text(strip=True))
            else:
                data['start_date'], data['end_date'] = None, None
            
            # General Info
            gen_info_text = None
            gen_info_label = soup.find('span', class_='overview__title', string=lambda t: t and 'General info' in t) # type: ignore
            if gen_info_label:
                info_div = gen_info_label.find_next(class_='overview__listText')
                if info_div: gen_info_text = info_div.get_text(separator='\n', strip=True)
            
             # Category
            name_upper = data['name'].upper() if data['name'] else ""
            if 'MAJOR' in name_upper: data['tournament_level'] = 'Major'
            elif 'P1' in name_upper: data['tournament_level'] = 'P1'
            elif 'P2' in name_upper: data['tournament_level'] = 'P2'
            elif 'FINALS' in name_upper: data['tournament_level'] = 'Finals'
            else: data['tournament_level'] = None

            # Helper
            def get_overview(label):
                el = soup.find('span', class_='overview__title', string=lambda t: t and label in t) # type: ignore
                return el.find_next('p').get_text(strip=True) if el and el.find_next('p') else None # type: ignore
            data['venue'] = None
            data['balls_used'] = None
            data['venue_type'] = None
            data['prize_money'] = None

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
            prize = self._clean_money(get_overview('Prize Money'))
            if not prize:
                data['prize_money'] = AVG_PRICE_MONEY[data['tournament_level']] if data['tournament_level'] else None
            else:
                data['prize_money'] = prize
            
            return data

        except Exception as e:
            print(f"        Failed to scrape {url}: {e}")
            return None
    
    @staticmethod
    def _parse_dates(date_str: str) -> tuple[Optional[str], Optional[str]]:
        """
        Converts a date range string in the format "DD/MM/YYYY - DD/MM/YYYY" to a tuple of (start_date, end_date) in "YYYY-MM-DD" format.

        Args:
            date_str: The date range string to parse.
        Returns:
            A tuple containing the start date and end date as strings in "YYYY-MM-DD" format, or (None, None) if parsing fails.
        """
        try:
            parts = date_str.replace('\n', '').split('-')
            start = datetime.strptime(parts[0].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            end = datetime.strptime(parts[1].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            return start, end
        except:
            return None, None

    @staticmethod
    def _clean_money(money_str: Optional[str]) -> Optional[int]:
        """
        Cleans a money string by extracting numeric values, removing formatting, and summing amounts if multiple are found.

        Args:
            money_str: The raw money string to clean.
        Returns:
            The total prize money as an integer, or None if no valid amount is found.
        """
        if not money_str: return None
        matches = re.findall(r'[0-9][0-9.,]*', money_str)
        total_purse = 0
        for m in matches:
            clean_val = m.strip('.,')
            if len(clean_val) > 3 and clean_val[-3] in ['.', ',']:
                if clean_val.endswith('.00') or clean_val.endswith(',00'):
                    clean_val = clean_val[:-3]
            final_digits = re.sub(r'[^\d]', '', clean_val)
            if final_digits:
                try:
                    amount = int(final_digits)
                    if amount > 10000:
                        total_purse += amount
                except:
                    continue
        return total_purse if total_purse > 0 else None