import os
import re
import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from bs4 import BeautifulSoup
from time import sleep

from typing import Any, List, Dict, Optional, Tuple

from supabase import create_client, Client

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    USER_AGENT,
    FIP_MEN_RANKING_URL,
    SUPABASE_URL,
    SUPABASE_KEY
)  

class FipPlayerScraper:
    """
    A scraper designed to extract player data from the FIP website.

    The scraper starts from the top-ranked player and follows the "Next Player" links to traverse the entire rankings.
    It collects both static data (name, country, birth date, etc.) and dynamic data (points, matches played, etc.) for each player.
    """

    def __init__(self):
        """
        Initializes the scraper with an empty player list, request headers, and a robust session with retry logic.
        """
        self.players: List[Dict] = []
        self.headers = {'User-Agent': USER_AGENT}
        self.session: requests.Session = self._create_robust_session()
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def run(self, last_scraped_day: Optional[datetime]) -> Tuple[List[Dict], List[Dict]]:
        """
        Runs the scraper to collect player data.
        If last_scraped_day is provided, it checks if the data is up to date.
        If not, it scrapes all players from the beginning.
        Args:
            last_scraped_day: The date of the last scraped player data snapshot. Used to determine if new data is available.
        
        Returns:
            A tuple containing two lists: static player data and dynamic player data.
        """
        updated_day = self._check_new_data()
        if not updated_day:
            print("    No updated day found. Running scraper anyway to ensure data is up to date.")
        elif not last_scraped_day:
            print("    No previous data found. Running scraper to collect initial data.")
        elif updated_day == last_scraped_day:
            print("    Data is already up to date. Exiting scraper...")
            return [], []
        else:
            print(f"    ✅ New data available for date {updated_day}. Starting scraper.")

        print("🔍 Finding starting point for scraping: ", end="")
        print("📥 Scraping players...")
        index = 0
        player_url = self._find_start_node()
        while player_url:
            print(f"    {index}: Processing {player_url}")
            try:
                response = self.session.get(player_url, headers=self.headers, timeout=(15, 30)) # type: ignore
                player_data, next_url = self._parse_player_profile(response.content, player_url) # type: ignore
                if player_data:
                    if player_data['points'] == "0":
                        break
                    self.players.append(player_data)
                    player_url = next_url
            except Exception as e:
                print(f"    Error processing {player_url}: {e}")
                break
            index += 1
            sleep(0.5)

        self._check_data()
        static_players = self._prepare_static_players()
        dynamic_players = self._prepare_dynamic_players()

        return static_players, dynamic_players

    def _create_robust_session(self) -> requests.Session:
        """
        Creates a requests session with retry logic to handle transient network issues and rate limiting.
        Returns:
            A configured requests.Session object with retry capabilities.
        """
        session = requests.Session()
    
        retry_strategy = Retry(
            total=5,  # Max number of retries
            backoff_factor=1,  # Wait 1 second before the first retry, then 2 seconds, then 4 seconds, etc.
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to trigger a retry
            allowed_methods=["HEAD", "GET", "OPTIONS"]  # Retry only for these HTTP methods
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session

    def _check_new_data(self) -> Optional[datetime]:
        """
        Checks the FIP rankings page for the date of the last update.
        Returns:
            The date of the last update as a datetime object, or None if it cannot be determined.
        """
        try:
            response = self.session.get(FIP_MEN_RANKING_URL, headers=self.headers, timeout=(15, 30))
            soup = BeautifulSoup(response.content, 'html.parser')

            updated_day_tag = soup.select_one('.topSlider__update')
            updated_day = updated_day_tag.get_text(strip=True) if updated_day_tag else None

            if updated_day in ["-", "--", ""] or updated_day is None:
                return None
            
            # Convert date from "dd/mm/yyyy" to "yyyy-mm-dd"
            updated_day = datetime.strptime(updated_day, "%d/%m/%Y").strftime("%Y-%m-%d")
            updated_day = datetime.strptime(updated_day, "%Y-%m-%d")
            return updated_day
        
        except Exception:
            return None
        
    
    def _find_start_node(self):
        """
        Finds the URL of the top-ranked player to start the scraping process.
        Returns:
            The URL of the top-ranked player's profile page, or None if it cannot be found.
        """
        player_link = None
        try:
            response = self.session.get(FIP_MEN_RANKING_URL, headers=self.headers, timeout=(15, 30))
            soup = BeautifulSoup(response.content, 'html.parser')          
            first_player_container = soup.select_one('.slider__rankings .slider__item')

            if first_player_container:
                name_tag = first_player_container.select_one('.slider__name a')
                
                if name_tag:
                    player_name = name_tag.get_text(strip=True)
                    player_link = name_tag.get('href')   
                    print(f"Found number 1 player: {player_name} with link: {player_link}")
                else:
                    print("Did not find the player's name link in the first player container.")
            else:
                print("Did not find the first player container on the rankings page.")
        except Exception:
            pass
                
        return player_link

    def _parse_player_profile(self, html_content: str, current_url: str) -> Tuple[Dict, Optional[str]]:
        """
        Parses the player's profile page to extract relevant data and the URL of the next player.
        Args:
            html_content: The HTML content of the player's profile page.
            current_url: The URL of the current player's profile page (used for reference and debugging).
        
        Returns:
            A tuple containing a dictionary of the player's data and the URL of the next player's profile page
        """
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

        overall_position_tag = soup.select_one('.slider__number.player__number')
        data['overall_position'] = overall_position_tag.get_text(strip=True) if overall_position_tag else None

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
                print("    Did not find img tag in the player's profile page.")
        data['image_url'] = image_url

        next_link = soup.find('a', attrs={'title': ['Next Player', 'Siguiente jugador']}) or \
                    soup.find('a', attrs={'aria-label': ['Next Player', 'Siguiente jugador']})
        next_url = next_link['href'] if next_link else None
        
        return data, next_url # type: ignore

    def _check_data(self) -> None:
        """
        Checks the scraped data for consistency and converts numeric fields to the appropriate types.
        If any field contains invalid data (like "-", "N/A", etc.), it sets it to None (or 0 for titles).
        """
        int_fields = ["points", "matches_played", "matches_won", "matches_lost",
                          "consecutive_victories", "titles", "overall_position"]
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

    def _extract_player_stats(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extracts player statistics from the profile page soup.
        The method looks for specific labels (like "Match played", "Effectiveness", etc.) and retrieves the corresponding values.
        It uses a mapping to convert the labels into the desired dictionary keys.
        Args:
            soup: BeautifulSoup object of the player's profile page.
        
        Returns:
            A dictionary containing the extracted player statistics with standardized keys.
        """
        stats = {}

        mapping = {
            "Match played": "matches_played",
            "Match won": "matches_won",
            "Match lost": "matches_lost",
            "Cons. victories": "consecutive_victories",
            "Effectiveness": "effectiveness",
            "Titles": "titles",
        }

        for label, key in mapping.items():
            label_el = soup.find(['span', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'], string=re.compile(rf'^{label}', re.IGNORECASE)) # type: ignore
            
            if label_el:
                value_el = label_el.find_next(['p', 'span', 'div', 'b'])
                if value_el:
                    stats[key] = value_el.get_text(strip=True).replace('%', '')
                else:
                    stats[key] = None
            else:
                stats[key] = None
        return stats
    
    def _prepare_static_players(self) -> List[Dict]:
        """
        Prepares the static player data for storage by extracting relevant fields and structuring them in a consistent format.
        Returns:
            A list of dictionaries, each containing the static data for a player.
        """
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

    def _fetch_previous_player_stat(self, slug: str) -> Optional[Dict]:
        """
        Fetches the most recent previous statistics for a given player before a specified date.
        Args:
            slug: The player's unique slug identifier.
            date_str: The cutoff date (in "YYYY-MM-DD" format) for fetching previous statistics.
        Returns:
            A dictionary containing the most recent previous statistics for the player, or None if no such record exists.
        """
        try:
            res = self.supabase.table("dynamic_players").select("*")\
                .eq("slug", slug)\
                .order("snapshot_date", desc=True).limit(1).execute()
            return res.data[0] if res.data else None  # type: ignore
        except Exception as e:
            print(f"Error fetching previous stats for player {slug}: {e}")
            return None

    def _prepare_dynamic_players(self) -> List[Dict]:
        """
        Prepares the dynamic player data for storage by extracting relevant fields and structuring them in a consistent format.
        Returns:
            A list of dictionaries, each containing the dynamic data for a player.
        """
        dynamic_players = []
        for player in self.players:
                current_ranking = player['overall_position']
                
                # Fetch previous stats to calculate ranking change
                prev_snapshot = self._fetch_previous_player_stat(player['slug'])
                
                if prev_snapshot:
                    prev_ranking = prev_snapshot.get('ranking_position')
                    if prev_ranking is not None and current_ranking is not None:
                        ranking_change = prev_ranking - current_ranking  # Positive means improved
                    else:
                        ranking_change = None
                else:
                    ranking_change = None
                
                dynamic_data = {
                    "slug": player['slug'],
                    "snapshot_date": player['updated_day'],
                    "points": player['points'],
                    "ranking_position": current_ranking,
                    "ranking_change": ranking_change,
                    "matches_played": player.get('matches_played') or 0,
                    "matches_won": player.get('matches_won') or 0,
                    "matches_lost": player.get('matches_lost') or 0,
                    "consecutive_victories": player.get('consecutive_victories') or 0,
                    "effectiveness": player.get('effectiveness') or 0.0,
                    "titles": player.get('titles') or 0,
                    "paired_with_slug": player['current_pair'],
                }
                dynamic_players.append(dynamic_data)
        return dynamic_players