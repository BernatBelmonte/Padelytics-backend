import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import os
import sys
from difflib import SequenceMatcher
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    AVG_PRICE_MONEY, 
    FIP_CALENDAR_URL, 
    RAW_FIP_TOURNAMENTS_FILE, 
    USER_AGENT, 
    RAW_DATA_DIR, 
    YEARS_TO_SCRAPE
)

class FipTournamentInterceptor:
    def __init__(self):
        self.headers = {"User-Agent": USER_AGENT}
        self.reference_data = []
        self.scraped_data = []

    def start(self):
        print("🎾 FIP Tournament Scraper")
        print("=========================")
        self._load_existing_data()
        # Pass 0: Initial scrape
        # Pass 1: Second pass to better impute missing values using the data gathered in Pass 0
        for i in range(2): 
            if i == 1:
                print("\n🔄 Starting second pass to impute missing data (using newly scraped context)...")
                self._load_existing_data() 
            
            self.scraped_data = [] # Reset buffer for this pass
            
            for year in YEARS_TO_SCRAPE:
                self._process_year(year)
            
            full_dataset = self.scraped_data + self.reference_data
            self._save_to_db(full_dataset)

    def _load_existing_data(self):
        if os.path.exists(RAW_FIP_TOURNAMENTS_FILE):
            try:
                with open(RAW_FIP_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
                    self.reference_data = json.load(f)
                print(f"📚 Loaded {len(self.reference_data)} existing tournaments for reference.")
            except Exception as e:
                print(f"⚠️ Error loading reference data: {e}")
                self.reference_data = []
        else:
            self.reference_data = []

    def _save_to_db(self, data):
        if not os.path.exists(RAW_DATA_DIR):
            os.makedirs(RAW_DATA_DIR)
        try:
            with open(RAW_FIP_TOURNAMENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"💾 Saved {len(data)} tournaments to {RAW_FIP_TOURNAMENTS_FILE}")
        except Exception as e:
            print(f"❌ Error saving data: {e}")

    def _process_year(self, year):
        links = self._get_tournament_links(year)
        
        for link in links:
            print(f"🕷️ Scraping: {link}")
            # We pass self.reference_data to help fill in missing info
            tournament_details = self._scrape_tournament_details(link, year)
            if tournament_details:
                self.scraped_data.append(tournament_details)

    def _get_tournament_links(self, year):
        # Avoid re-scraping URLs we already have in reference data
        reference_slugs = {t['source_url'].split('/')[-2] for t in self.reference_data if 'source_url' in t}
        
        url = f"{FIP_CALENDAR_URL}?events-year={year}"
        print(f"📅 Scanning Calendar for {year}...")
        
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
            
            unique_links = list(set(links))
            print(f"   found {len(unique_links)} new links.")
            return unique_links
        except Exception as e:
            print(f"❌ Error fetching calendar: {e}")
            return []

    def _scrape_tournament_details(self, url, season):
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            data = {'source_url': url, 'season': str(season)}

            # Basic Info
            name_tag = soup.select_one('.event__name')
            data['name'] = name_tag.get_text(strip=True) if name_tag else "Unknown"

            place_tag = soup.select_one('.event__place')
            if place_tag:
                parts = place_tag.get_text(strip=True).split('-')
                data['city'] = parts[0].strip()
                data['country'] = parts[1].strip() if len(parts) > 1 else "Unknown"
            else:
                data['city'], data['country'] = None, None

            # Dates & Status
            date_tag = soup.select_one('.event__date')
            if date_tag:
                data['start_date'], data['end_date'] = self._parse_dates(date_tag.get_text(strip=True))
            else:
                data['start_date'], data['end_date'] = None, None

            data['status'] = self._calculate_status(data['start_date'], data['end_date'])

            # Helper to extract overview items
            def get_overview(label):
                el = soup.find('span', class_='overview__title', string=lambda t: t and label in t) # type: ignore
                return el.find_next('p').get_text(strip=True) if el and el.find_next('p') else None # type: ignore

            # Tournament Level
            name_upper = data['name'].upper()
            if 'MAJOR' in name_upper: data['tournament_level'] = 'Major'
            elif 'P1' in name_upper: data['tournament_level'] = 'P1'
            elif 'P2' in name_upper: data['tournament_level'] = 'P2'
            elif 'FINALS' in name_upper: data['tournament_level'] = 'Finals'
            else: data['tournament_level'] = 'Other'

            # General Info Text
            gen_info_text = None
            gen_info_label = soup.find('span', class_='overview__title', string=lambda t: t and 'General info' in t) # type: ignore
            if gen_info_label:
                info_div = gen_info_label.find_next(class_='overview__listText')
                if info_div:
                    gen_info_text = info_div.get_text(separator='\n', strip=True)

            # Venue
            data['venue'] = get_overview('Venue')
            if not data['venue'] and gen_info_text:
                for line in gen_info_text.split('\n'):
                    if 'VENUE' in line.upper():
                        if 'VENUE TYPE' in line.upper(): continue
                        data['venue'] = re.sub(r'^VENUE\s*[:\.]?\s*', '', line, flags=re.IGNORECASE).strip()
                        break
            if not data['venue']:
                data['venue'] = self._imput_value(data, 'venue')

            # Balls
            data['balls_used'] = get_overview('Balls')
            if not data['balls_used'] and gen_info_text:
                for line in gen_info_text.split('\n'):
                    if 'BALL' in line.upper():
                        clean_ball = re.sub(r'^.*BALLS?\s*[:\.]?\s*', '', line, flags=re.IGNORECASE)
                        if clean_ball != '':
                            data['balls_used'] = clean_ball.strip()
                        break
            if not data['balls_used']:
                data['balls_used'] = self._imput_value(data, 'balls_used')

            # Venue Type
            condition_text = get_overview('Court conditions')
            if not condition_text and gen_info_text:
                condition_text = gen_info_text
            
            data['venue_type'] = None 
            if condition_text:
                text_clean = condition_text.lower()
                if 'indoor' in text_clean: data['venue_type'] = 'indoor'
                elif 'outdoor' in text_clean: data['venue_type'] = 'outdoor'
            if not data['venue_type']:
                data['venue_type'] = self._imput_value(data, 'venue_type')

            # Prize Money
            prize_money = self._clean_money(get_overview('Prize Money'))
            if prize_money == 0 or prize_money is None:
                data['prize_money'] = AVG_PRICE_MONEY.get(data['tournament_level'], None)
            else:
                data['prize_money'] = prize_money

            return data

        except Exception as e:
            print(f"⚠️ Failed to scrape {url}: {e}")
            return None

    def _imput_value(self, target_data, key):
        target_country = target_data.get('country')
        target_city = target_data.get('city') 

        if not target_country or not target_city:
            return None

        best_match_value = None
        best_score = 0
        best_city_found = None

        try:
            for candidate in self.reference_data:
                cand_country = candidate.get('country')
                cand_city = candidate.get('city')
                cand_value = candidate.get(key)

                if not cand_country or not cand_city or not cand_value:
                    continue

                if cand_country.lower().strip() != target_country.lower().strip():
                    continue

                score = self._similar(target_city, cand_city)
                
                if score > 0.7 and score > best_score:
                    best_score = score
                    best_match_value = cand_value
                    best_city_found = cand_city

            if best_match_value:
                print(f"   ℹ️ Imputed {key}: '{best_match_value}' (Matched '{target_city}' with '{best_city_found}' - {best_score:.0%})")
                return best_match_value

        except Exception as e:
            print(f"   ⚠️ Error imputing {key}: {e}")
        
        return None
    
    @staticmethod
    def _similar(a, b):
        if a is None or b is None: return 0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def _parse_dates(date_str):
        try:
            parts = date_str.replace('\n', '').split('-')
            start = datetime.strptime(parts[0].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            end = datetime.strptime(parts[1].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            return start, end
        except:
            return None, None

    @staticmethod
    def _calculate_status(start_date, end_date):
        if not start_date or not end_date:
            return "Unknown"
        today = datetime.now().strftime("%Y-%m-%d")
        if today > end_date:
            return "Finished"
        elif today >= start_date and today <= end_date:
            return "Active"
        else:
            return "Upcoming"

    @staticmethod
    def _clean_money(money_str):
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

if __name__ == "__main__":
    bot = FipTournamentInterceptor()
    bot.start()