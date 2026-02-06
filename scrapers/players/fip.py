import os
import re
import sys
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from time import sleep

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    USER_AGENT,
    FIP_MEN_RANKING_URL
    
)  

class FipPlayerScraper:

    def __init__(self):
        self.players = []
        self.headers = {'User-Agent': USER_AGENT}

    def run(self, last_scraped_day):
        """Main method to start scraping players."""
        updated_day = self._check_new_data()
        if not updated_day:
            print("❌ No new data available. Running scraper anyway to ensure data is up to date.")
        elif not last_scraped_day:
            print("❌ No previous data found. Running scraper to collect initial data.")
        elif updated_day == last_scraped_day:
            print("❌ Data is already up to date. Exiting scraper.")
            return [], []
        else:
            print(f"✅ New data available for date {updated_day}. Starting scraper.")

        player_url = self._find_start_node()
        while player_url:
            print(f"Processing {player_url}")
            try:
                response = requests.get(player_url, headers=self.headers, timeout=(10, 30)) # type: ignore
                player_data, next_url = self._parse_player_profile(response.content, player_url)
                if player_data:
                    self.players.append(player_data)
                    player_url = next_url
            except Exception as e:
                print(f"❌ Error processing player at {player_url}: {e}")
                break
            sleep(0.5)

        self._check_data()
        static_players = self._prepare_static_players()
        dynamic_players = self._prepare_dynamic_players()

        return static_players, dynamic_players

    def _check_new_data(self):
        """Checks if new data is available by comparing the updated day in main page."""
        try:
            response = requests.get(FIP_MEN_RANKING_URL, headers=self.headers, timeout=(10, 30))
            soup = BeautifulSoup(response.content, 'html.parser')
            updated_day_tag = soup.select_one('.topSlider__update')
            updated_day = updated_day_tag.get_text(strip=True) if updated_day_tag else None
            if updated_day in ["-", "--", ""] or updated_day is None:
                return False
            updated_day = datetime.strptime(updated_day, "%d/%m/%Y").strftime("%Y-%m-%d")
            updated_day = datetime.strptime(updated_day, "%Y-%m-%d")
            return updated_day.date()
        except Exception:
            return False
        
    
    def _find_start_node(self):
        """Finds the URL of the top-ranked player from the FIP"""
        player_link = None
        try:
            response = requests.get(FIP_MEN_RANKING_URL, headers=self.headers, timeout=(10, 30))
            soup = BeautifulSoup(response.content, 'html.parser')
            
            first_player_container = soup.select_one('.slider__rankings .slider__item')

            if first_player_container:
                # 3. Buscamos el enlace dentro del nombre del jugador
                name_tag = first_player_container.select_one('.slider__name a')
                
                if name_tag:
                    player_name = name_tag.get_text(strip=True)
                    player_link = name_tag.get('href')
                    
                    print(f"Jugador Número 1: {player_name}")
                    print(f"Enlace al perfil: {player_link}")
                else:
                    print("No se encontró el enlace del jugador.")
            else:
                print("No se encontró el contenedor del ranking.")

        except Exception:
            pass
                
        return player_link

    def _parse_player_profile(self, html_content, current_url):
        """Extracts player details."""
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {} 

        data['fip_url'] = current_url
        
        name_tag = soup.select_one('.slider__name.player__name')
        data['name'] = name_tag.get_text(strip=True) if name_tag else "Unknown"
        
        canonical = soup.find('link', rel='canonical')
        raw_slug = canonical['href'].rstrip('/').split('/')[-1] if canonical else current_url.rstrip('/').split('/')[-1] # type: ignore
        data['slug'] = raw_slug

        updated_day_tag = soup.select_one('.topSlider__update.topRanking__update')
        updated_day = updated_day_tag.get_text(strip=True)if updated_day_tag else None
        if updated_day in ["-", "--", ""] or updated_day is None:
            updated_day = None
        else:
            updated_day = datetime.strptime(updated_day, "%d/%m/%Y").strftime("%Y-%m-%d")
        data['updated_day'] = updated_day

        points_tag = soup.select_one('.slider__pointTNumber.player__pointTNumber')
        data['points'] = points_tag.get_text(strip=True) if points_tag else None
        
        country_tag = soup.select_one('.slider__country.player__country')
        data['country'] = country_tag.get_text(strip=True) if country_tag else None
        
        height_tag = soup.select_one('.additionalInfo__height .additionalInfo__data')
        data['height'] = height_tag.get_text(strip=True) if height_tag else None
        
        pos_tag = soup.select_one('.additionalInfo__hand .content')
        data['position'] = pos_tag.get_text(strip=True) if pos_tag else None
        
        birth_tag = soup.select_one('.additionalInfo__birth .additionalInfo__data')
        birth_date = birth_tag.get_text(strip=True) if birth_tag else None
        if birth_date in ["-", "--", ""] or birth_date is None:
            birth_date = None
        else:
            birth_date = datetime.strptime(birth_date, "%d/%m/%Y").strftime("%Y-%m-%d")
        data['birth_date'] = birth_date
        
        pair_tag = soup.select_one('.additionalInfo__paired .content a')
        raw_slug_pair = pair_tag['href'].rstrip('/').split('/')[-1] if pair_tag else None # type: ignore
        data['current_pair'] = raw_slug_pair
        
        stats = self._extract_player_stats(soup)
        data.update(stats)

        img_container = soup.select_one('.slider__img.player__img')
        image_url = None
        if img_container:
            img_tag = img_container.find('img')
            if img_tag:
                image_url = img_tag.get('data-src') or img_tag.get('src')
            else:
                print("❌ No se encontró etiqueta <img> dentro del contenedor.")
        data['image_url'] = image_url

        next_link = soup.find('a', attrs={'title': ['Next Player', 'Siguiente jugador']}) or \
                    soup.find('a', attrs={'aria-label': ['Next Player', 'Siguiente jugador']})
        next_url = next_link['href'] if next_link else None
        
        return data, next_url

    def _check_data(self):
        """Cleans data fields with invalid placeholders."""
        int_fields = ["points", "matches_played", "matches_won", "matches_lost",
                          "consecutive_victories", "titles", "race_position"]
        numeric_fields = ["effectiveness", "height"]
        
        for player in self.players:
            for key, value in player.items():
                if key in numeric_fields:
                    try:
                        player[key] = float(value) if value is not None else None
                    except:
                        player[key] = None
                elif key in int_fields:
                    try:
                        player[key] = int(value) if value is not None else None
                    except:
                        player[key] = None
                if value is None or str(value).strip() in ["-", "--", "", "N/A", "null", ""]:
                    if key  == 'titles':
                        player[key] = 0
                    else:
                        player[key] = None 

    def _extract_player_stats(self, soup):
        """Extracts player statistics from the profile page soup."""
        stats = {}

        mapping = {
            "Match played": "matches_played",
            "Match won": "matches_won",
            "Match lost": "matches_lost",
            "Cons. victories": "consecutive_victories",
            "Effectiveness": "effectiveness",
            "Titles": "titles",
            "Race": "race_position"
        }

        for label, key in mapping.items():
            label_el = soup.find(['span', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'], string=re.compile(rf'^{label}', re.IGNORECASE))
            
            if label_el:
                value_el = label_el.find_next(['p', 'span', 'div', 'b'])
                if value_el:
                    stats[key] = value_el.get_text(strip=True).replace('%', '')
                else:
                    stats[key] = None
            else:
                stats[key] = None
        return stats
    
    def _prepare_static_players(self):
        """Returns the list of newly scraped static data for players."""
        static_players = []
        for player in self.players:
            static_data = {
                "slug": player['slug'],
                "name": player['name'],
                "country": player['country'],
                "height": player['height'],
                "position": player['position'],
                "birth_date": player['birth_date'],
                "fip_url": player['fip_url'],
                "image_url": player['image_url'],
                "image_public_url": None,  # To be filled after image upload
            }
            static_players.append(static_data)
        return static_players

    def _prepare_dynamic_players(self):
        """Returns the list of newly scraped time data for players."""
        dynamic_players = []
        for player in self.players:
            dynamic_data = {
                "slug": player['slug'],
                "snapshot_date": player['updated_day'],
                "points": player['points'],
                "matches_played": player['matches_played'],
                "matches_won": player['matches_won'],
                "matches_lost": player['matches_lost'],
                "consecutive_victories": player['consecutive_victories'],
                "effectiveness": player['effectiveness'],
                "titles": player['titles'],
                "race_position": player.get('race_position'),
                "paired_with_slug": player['current_pair'],
            }
            dynamic_players.append(dynamic_data)
        return dynamic_players