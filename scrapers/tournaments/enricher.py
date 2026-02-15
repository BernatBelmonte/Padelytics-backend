import os
import sys
import requests
import time
from datetime import datetime, timedelta
from geopy.geocoders import ArcGIS
from typing import List, Dict, Optional

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    OPEN_METEO_URL
)  

class TournamentEnricher:
    """
    A class responsible for merging and enriching tournament data from Premier Padel and FIP sources.
    This class takes raw tournament data from both sources, attempts to match them based on name, city, and date proximity, and then enriches the combined data with additional information such as weather conditions and a calculated court speed index.
        The enrichment process includes:
        - Geocoding the tournament location to obtain latitude and longitude.
        - Fetching historical weather data for the tournament dates and location.
        - Calculating a "smart" court speed index based on altitude, temperature, humidity, and whether the venue is indoor or outdoor.
        - Handling both new tournaments and updates to existing tournaments in the database.
    """
    def __init__(self, existing_tournaments: List[Dict]):
        """
        Initializes the enricher with a geolocator and a list of existing tournaments for reference during the enrichment process.
        Args:
            existing_tournaments: A list of dictionaries representing tournaments that have already been enriched and stored in the database. This is used to determine whether a tournament from the Premier Padel data is new or an update to an existing record.
        """
        self.geolocator = ArcGIS(timeout=10) # type: ignore
        self.existing_tournaments = existing_tournaments

    def process(self, premier_data: List[Dict], fip_data: List[Dict]) -> List[Dict]:
        """
        Merges and enriches tournament data from Premier Padel and FIP sources.
        For each tournament in the Premier Padel data, the method attempts to find a matching tournament in the FIP data based on name, city, and date proximity. If a match is found, it checks if the tournament already exists in the database. If it does, it updates the existing record with any new information. If it doesn't, it creates a new enriched tournament record. The enrichment process includes fetching weather data and calculating a court speed index.
        
        Args:
            premier_data: A list of dictionaries containing raw tournament data from the Premier Padel source.
            fip_data: A list of dictionaries containing raw tournament data from the FIP source.
        Returns:
            A list of dictionaries representing the enriched tournament data, ready for insertion or update in the database.
        """
        print("📥 Merging and Enriching Data...")
        enriched_list = []
        
        total = len(premier_data)
        for i, p_t in enumerate(premier_data):
            fip_t = self._find_fip_match(p_t, fip_data)
            if not fip_t:
                print(f" [{i+1}/{total}] No FIP match found for: {p_t['full_name']} ({p_t['city']})")
                continue

            print(f" [{i+1}/{total}] Enriching: {p_t['full_name']} ({p_t['city']})", end="")
            is_new = True
            for ext_t in self.existing_tournaments:
                if ext_t['fip_slug'] == fip_t['fip_slug'] and ext_t['premier_slug'] == p_t['slug']:
                    enriched_list.append(self._process_existing_tournament(ext_t, p_t, fip_t))
                    is_new = False
                    print(" -> Updating existing tournament.")
                    break
            if is_new:
                enriched_list.append(self._process_new_tournament(p_t, fip_t))
                print(" -> Creating new tournament.")
            time.sleep(1)
        print("-------------------------------")
        return enriched_list

    def _process_new_tournament(self, p_t: Dict, fip_t: Dict) -> Dict:
        """
        Creates a new enriched tournament record by combining data from the Premier Padel and FIP sources, and then fetching additional information such as weather data and calculating the court speed index.
        
        Args:
            p_t: A dictionary containing raw tournament data from the Premier Padel source.
            fip_t: A dictionary containing raw tournament data from the FIP source that matches the Premier Padel tournament.
        Returns:
            A dictionary representing the enriched tournament data, ready for insertion into the database.
        """
        start_date = str(p_t['start_date_utc']).split(' ')[0]
        end_date = str(p_t['end_date_utc']).split(' ')[0]
        tourney = {
                "name": p_t.get('full_name'),
                "premier_slug": p_t.get('slug'),
                "fip_slug": fip_t.get('fip_slug'),
                "season": int(p_t.get('year')) if p_t.get('year') else None, # type: ignore
                "city": p_t.get('city') or fip_t.get('city'),
                "country": p_t.get('country') or fip_t.get('country'),
                "country_code": p_t.get('country_code'),
                "venue": p_t.get('club') or fip_t.get('venue'),
                "start_date": start_date,
                "end_date": end_date,
                "status": p_t.get('tournaments_type'),
                "tournament_level": p_t.get('type'),
                "prize_money": self._clean_prize_money(p_t.get('prize_money') or fip_t.get('prize_money')),
                "balls_used": fip_t.get('balls_used'),
                "venue_type": fip_t.get('venue_type'),
                "is_enriched": False
            }
            
        if tourney['city'] and tourney['country']:
            lat, lon = self._get_coordinates(tourney['city'], tourney['country'])
            if lat:
                weather = self._get_weather_data(lat, lon, start_date, end_date) # type: ignore
                if weather:
                    tourney['altitude'] = weather['altitude']
                    tourney['avg_temperature'] = weather['avg_temperature']
                    tourney['avg_humidity'] = weather['avg_humidity']
                    tourney['court_speed_index'] = self._calculate_smart_speed_index(tourney)
                    print(f"        Altitude={tourney['altitude']}, Temp={tourney['avg_temperature']}, Humidity={tourney['avg_humidity']}, SpeedIndex={tourney['court_speed_index']}")
                    tourney['is_enriched'] = True
                else:
                    print("        ⚠️ Weather data not found.")
        tourney['matches_scraped'] = False
        return tourney

    def _process_existing_tournament(self, ext_t: Dict, p_t: Dict, fip_t: Dict) -> Dict:
        """
        Updates an existing enriched tournament record with any new information from the Premier Padel and FIP sources. If the tournament has not already been enriched, it also fetches weather data and calculates the court speed index.
        
        Args:
            ext_t: A dictionary representing the existing enriched tournament record from the database.
            p_t: A dictionary containing raw tournament data from the Premier Padel source.
            fip_t: A dictionary containing raw tournament data from the FIP source that matches the Premier Padel tournament.
        Returns:
            A dictionary representing the updated enriched tournament data, ready for update in the database.
        """
        tourney = {
            "premier_slug": ext_t.get('premier_slug'),
            "fip_slug": ext_t.get('fip_slug'),
            "venue": ext_t.get('venue') or p_t.get('club') or fip_t.get('venue'),
            "status": p_t.get('tournaments_type'),
            "prize_money": self._clean_prize_money(p_t.get('prize_money') or fip_t.get('prize_money') or ext_t.get('prize_money')),
            "balls_used": ext_t.get('balls_used') or fip_t.get('balls_used'),
            "venue_type": ext_t.get('venue_type') or fip_t.get('venue_type'),
        }

        if not ext_t.get('is_enriched'):
            start_date = str(p_t['start_date_utc']).split(' ')[0]
            end_date = str(p_t['end_date_utc']).split(' ')[0]
            if p_t.get('city') and p_t.get('country'):
                lat, lon = self._get_coordinates(p_t.get('city'), p_t.get('country')) # type: ignore
                if lat:
                    weather = self._get_weather_data(lat, lon, start_date, end_date) # type: ignore
                    if weather:
                        tourney['altitude'] = weather['altitude']
                        tourney['avg_temperature'] = weather['avg_temperature']
                        tourney['avg_humidity'] = weather['avg_humidity']
                        tourney['court_speed_index'] = self._calculate_smart_speed_index(tourney)
                        print(f"        Altitude={tourney['altitude']}, Temp={tourney['avg_temperature']}, Humidity={tourney['avg_humidity']}, SpeedIndex={tourney['court_speed_index']}")
                        tourney['is_enriched'] = True
                    else:
                        print("        Weather data not found.")
        else:
            print("        Already enriched, skipping weather and speed index.")
        return tourney
    
    @staticmethod
    def _clean_prize_money(value: Optional[str]) -> Optional[int]:
        """
        Cleans a prize money string by removing formatting and converting it to an integer.

        Args:
            value: The raw prize money string to clean.
        Returns:
            The cleaned prize money as an integer, or None if the input is invalid or cannot be converted.
        """
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        # Remove commas, currency symbols, and spaces, then convert to int
        try:
            clean_val = str(value).replace(",", "").replace("€", "").replace("$", "").strip()
            return int(clean_val)
        except ValueError:
            return None
    
    def _find_fip_match(self, p_t: Dict, fip_data: List[Dict]) -> Optional[Dict]:
        """
        Attempts to find a matching tournament in the FIP data based on name, city, and date proximity.
        
        Args:
            p_t: A dictionary containing raw tournament data from the Premier Padel source.
            fip_data: A list of dictionaries containing raw tournament data from the FIP source.
        Returns:
            A dictionary representing the matching FIP tournament data if a match is found, or None if no match is found.
        """
        p_start = str(p_t['start_date_utc']).split(' ')[0]
        if not p_start: return None
        try:
            p_date = datetime.strptime(p_start, "%Y-%m-%d")
        except: return None

        for f_t in fip_data:
            f_start = f_t['start_date']
            if not f_start: continue
            try:
                f_date = datetime.strptime(f_start, "%Y-%m-%d")
                if abs((p_date - f_date).days) <= 3:
                    return f_t
            except: continue
        return None

    def _get_coordinates(self, city: str, country: str) -> tuple[Optional[float], Optional[float]]:
        """
        Uses geopy to geocode the city and country into latitude and longitude coordinates.
        
        Args:
            city: The city where the tournament is held.
            country: The country where the tournament is held.
        Returns:
            A tuple containing the latitude and longitude of the tournament location, or (None, None) if geocoding fails.
        """
        query = f"{city}, {country}" if country else city
        try:
            loc = self.geolocator.geocode(query, timeout=10) # type: ignore
            return (loc.latitude, loc.longitude) if loc else (None, None) # type: ignore
        except Exception as e:
            print(e)
            return None, None

    def _get_weather_data(self, lat: float, lon: float, start: str, end: str) -> Optional[Dict]:
        """
        Fetches historical weather data from the Open-Meteo API for the given latitude, longitude, and date range. The method processes the hourly weather data to calculate average temperature and humidity during typical tournament hours (11:00 to 23:00) and returns this information along with the altitude of the location.

        Args:
            lat: The latitude of the tournament location.
            lon: The longitude of the tournament location.
            start: The start date of the tournament in "YYYY-MM-DD" format.
            end: The end date of the tournament in "YYYY-MM-DD" format.
        Returns:
            A dictionary containing the altitude, average temperature, and average humidity for the tournament location and dates, or None if the weather data cannot be retrieved or processed.
        """
        if not start or not end: return None
        now = datetime.now()
        try:
            s_obj = datetime.strptime(start, "%Y-%m-%d")
            e_obj = datetime.strptime(end, "%Y-%m-%d")
            if s_obj > now:
                s_obj -= timedelta(days=365)
                e_obj -= timedelta(days=365)
                start = s_obj.strftime("%Y-%m-%d")
                end = e_obj.strftime("%Y-%m-%d")
        except: return None

        params = {
            "latitude": lat, "longitude": lon, 
            "start_date": start, "end_date": end,
            "hourly": ["temperature_2m", "relative_humidity_2m"],
            "timezone": "auto"
        }
        try:
            r = requests.get(OPEN_METEO_URL, params=params).json()
            if "hourly" in r:
                times = r['hourly']['time']
                temps = r['hourly']['temperature_2m']
                hums = r['hourly']['relative_humidity_2m']
                valid_temps, valid_hums = [], []
                
                for i, t in enumerate(times):
                    h = int(t.split('T')[1].split(':')[0])
                    if 11 <= h <= 23:
                        if temps[i]: valid_temps.append(temps[i])
                        if hums[i]: valid_hums.append(hums[i])
                
                return {
                    "altitude": r.get('elevation', 0),
                    "avg_temperature": round(sum(valid_temps)/len(valid_temps), 1) if valid_temps else None,
                    "avg_humidity": round(sum(valid_hums)/len(valid_hums), 1) if valid_hums else None
                }
        except: pass
        return None

    def _calculate_smart_speed_index(self, t: Dict) -> Optional[float]:
        """
        Calculates a "smart" court speed index based on various factors such as altitude, average temperature, average humidity, and whether the venue is indoor or outdoor. The formula is designed to reflect how these environmental conditions can affect the speed of play on a padel court.
        Args:
            t: A dictionary containing tournament information, including 'venue_type', 'altitude', 'avg_temperature', and 'avg_humidity'.
        Returns:
            A calculated court speed index as a float, or None if the necessary information is not available to perform the calculation.
        """
        is_indoor = True if 'indoor' in str(t['venue_type']).lower() else False
        alt = t['altitude'] or 0
        temp = t['avg_temperature'] or 20
        hum = t['avg_humidity'] or 50

        alt_score = alt * 0.012
        
        if temp < 10: temp_score = (temp - 10) * 1.5
        elif temp <= 22: temp_score = (temp - 10) * 0.5
        else: temp_score = 6 + (temp - 22) * 2.0
        
        hum_penalty = (hum - 45) * 0.5 if hum > 45 else 0

        weight = 0.2 if is_indoor else 1.0
        
        indoor_bonus = 5 if is_indoor else 0

        return 50 + alt_score + (temp_score * weight) - (hum_penalty * weight) + indoor_bonus