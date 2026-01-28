import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from time import sleep

from scrapers.database import VoleAIDB
# --- CONFIGURATION ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    USER_AGENT,
    FIP_MEN_RANKING_URL
    
)  

class FipPlayerScraper:
    """Scrapes FIP player profiles starting from the Race Top 100 page."""

    def __init__(self, existing_dynamic_players):
        self.players = []
        self.existing_dynamic_players = existing_dynamic_players
        self.headers = {'User-Agent': USER_AGENT}

    def start(self):
        """Main method to start scraping players."""
        player_url = self.find_start_node()

        while player_url:
            print(f"Processing {player_url}")
            try:
                response = requests.get(player_url, headers=self.headers, timeout=10) # type: ignore
                player_data, next_url = self.parse_player_profile(response.content, player_url)
                if player_data:
                    self.players.append(player_data)
                    print(player_data)
                    player_url = next_url
            except Exception as e:
                print(f"❌ Error processing player at {player_url}: {e}")
                break
            sleep(1)  # Be polite to the server
        return self.players

    def find_start_node(self):
        """Finds the URL of the top-ranked player from the"""
        player_link = None
        try:
            response = requests.get(FIP_MEN_RANKING_URL, headers=self.headers, timeout=10)
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

    def parse_player_profile(self, html_content, current_url):
        """Extracts player details using precise CSS selectors."""
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {} 

        data['fip_url'] = current_url
        
        name_tag = soup.select_one('.slider__name.player__name')
        data['name'] = name_tag.get_text(strip=True) if name_tag else "Unknown"
        
        canonical = soup.find('link', rel='canonical')
        raw_slug = canonical['href'].rstrip('/').split('/')[-1] if canonical else current_url.rstrip('/').split('/')[-1] # type: ignore
        data['slug'] = raw_slug

        updated_day_tag = soup.select_one('.topSlider__update.topRanking__update')
        data['updated_day'] = updated_day_tag.get_text(strip=True) if updated_day_tag else None

        points_tag = soup.select_one('.slider__pointTNumber.player__pointTNumber')
        data['points'] = points_tag.get_text(strip=True) if points_tag else None
        
        country_tag = soup.select_one('.slider__country.player__country')
        data['country'] = country_tag.get_text(strip=True) if country_tag else None
        
        height_tag = soup.select_one('.additionalInfo__height .additionalInfo__data')
        data['height'] = height_tag.get_text(strip=True) if height_tag else None
        
        pos_tag = soup.select_one('.additionalInfo__hand .content')
        data['position'] = pos_tag.get_text(strip=True) if pos_tag else None
        
        birth_tag = soup.select_one('.additionalInfo__birth .additionalInfo__data')
        data['birth_date'] = birth_tag.get_text(strip=True) if birth_tag else None
        
        pair_tag = soup.select_one('.additionalInfo__paired .additionalInfo__data a')
        raw_slug_pair = pair_tag['href'].rstrip('/').split('/')[-1] if pair_tag else None # type: ignore
        data['current_pair'] = raw_slug_pair
        data['current_pair_url'] = pair_tag['href'] if pair_tag else None
        
        stats = self.extract_player_stats(soup)
        data.update(stats)

        img_container = soup.select_one('.slider__img.player__img')
        image_url = None
        if img_container:
            img_tag = img_container.find('img')
            if img_tag:
                image_url = img_tag.get('data-src') or img_tag.get('src')
                print(f"✅ URL de imagen encontrada: {image_url}")
            else:
                print("❌ No se encontró etiqueta <img> dentro del contenedor.")
        data['image_url'] = image_url

        next_link = soup.find('a', attrs={'title': ['Next Player', 'Siguiente jugador']}) or \
                    soup.find('a', attrs={'aria-label': ['Next Player', 'Siguiente jugador']})
        next_url = next_link['href'] if next_link else None
        
        return data, next_url
    
    def extract_player_stats(self, soup):
        stats = {}

        # En la web de la FIP, las estadísticas suelen estar en contenedores 
        # con clases como 'player-stats__item' o dentro de una lista 'overview'
        # Buscamos por el texto de la etiqueta para ser precisos
        
        mapping = {
            "Match played": "matches_played",
            "Match won": "matches_won",
            "Match lost": "matches_lost",
            "Cons. victories": "consecutive_victories",
            "Effectiveness": "effectiveness",
            "Titles": "titles",
            "Race": "race_position"
        }

        # Buscamos todos los bloques de información que contienen un título y un valor
        # Basado en la estructura común de overview__title vista en otros scrapers
        for label, key in mapping.items():
            # Buscamos el SPAN que contiene el texto de la estadística (ej: "Match played")
            label_el = soup.find(['span', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'], string=re.compile(rf'^{label}', re.IGNORECASE))
            
            if label_el:
                # El valor suele estar en el siguiente elemento hermano o en un elemento padre cercano
                # Intentamos encontrar el valor numérico asociado
                value_el = label_el.find_next(['p', 'span', 'div', 'b'])
                if value_el:
                    stats[key] = value_el.get_text(strip=True)
                else:
                    stats[key] = None
            else:
                stats[key] = None
        return stats
    
    def prepare_static_players(self):
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
                "fip_url": player['fip_url']     
            }
            static_players.append(static_data)

    def prepare_dynamic_players(self):
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
        

if __name__ == "__main__": 
    db = VoleAIDB()
    existing_dynamic_players = db.load_existing_dynamic_players()
    existing_static_players = db.load_existing_static_players()
    scraper = FipPlayerScraper(existing_dynamic_players)
    scraper.start()