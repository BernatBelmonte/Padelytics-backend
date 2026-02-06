import os
import sys
import requests
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim

# Config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    OPEN_METEO_URL
)  

class TournamentEnricher:
    """
    Docstring for TournamentEnricher
    Class to enrich tournament data with geographical and weather information.
    Methods:
        - __init__: Initializes the geolocator.
        - process: Merges and enriches Premier and FIP tournament data.
        - _find_fip_match: Finds matching FIP tournament for a given Premier tournament.
        - _get_coordinates: Retrieves latitude and longitude for a given city and country.
        - _get_weather_data: Fetches weather data for given coordinates and date range.
        - _calculate_smart_speed_index: Calculates court speed index based on conditions.
        - _prepare_data: Cleans and prepares the final enriched data.
    """
    def __init__(self):
        self.geolocator = Nominatim(user_agent="voleai_analytics_bot_v2")

    def process(self, premier_data, fip_data):
        print("📥 Merging and Enriching Data...")
        print("================================")
        enriched_list = []
        
        total = len(premier_data)
        for i, p_t in enumerate(premier_data):
            fip_match = self._find_fip_match(p_t, fip_data)
            start_date = str(p_t['start_date_utc']).split(' ')[0]
            end_date = str(p_t['end_date_utc']).split(' ')[0]
            
            tourney = {
                **p_t,
                'fip_source_url': fip_match['source_url'] if fip_match else None,
                'tournament_level': fip_match['tournament_level'] if fip_match else None,
                'venue': fip_match['venue'] if fip_match else None,
                'balls_used': fip_match['balls_used'] if fip_match else None,
                'venue_type': fip_match['venue_type'] if fip_match else None,
                'status': fip_match['status'] if fip_match else None
            }
            if fip_match and not tourney['club']:
                tourney['club'] = tourney['venue']
            del tourney['venue']
            tourney['prize_money'] = fip_match['prize_money'] if fip_match else None

            print(f"    [{i+1}/{total}] Enriching: {tourney['full_name']} ({tourney['city']})")
            
            if tourney['city']:
                lat, lon = self._get_coordinates(tourney['city'], tourney['country'])
                if lat:
                    weather = self._get_weather_data(lat, lon, start_date, end_date)
                    if weather:
                        tourney['altitude'] = weather['altitude']
                        tourney['avg_temperature'] = weather['avg_temperature']
                        tourney['avg_humidity'] = weather['avg_humidity']

                        tourney['court_speed_index'] = self._calculate_smart_speed_index(tourney)
            print(f"        Altitude={tourney['altitude']}, Temp={tourney['avg_temperature']}, Humidity={tourney['avg_humidity']}, SpeedIndex={tourney['court_speed_index']}")
            tourney['matches_scraped'] = False
            enriched_list.append(tourney)

        return self._prepare_data(enriched_list)

    def _find_fip_match(self, p_t, fip_data):
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

    def _get_coordinates(self, city, country):
        query = f"{city}, {country}" if country else city
        try:
            loc = self.geolocator.geocode(query, timeout=10) # type: ignore
            return (loc.latitude, loc.longitude) if loc else (None, None) # type: ignore
        except: return None, None

    def _get_weather_data(self, lat, lon, start, end):
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

    def _calculate_smart_speed_index(self, t):
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

    def _prepare_data(self, data):
        allowed_columns = [
            "tournaments_id", "event_code", "full_name", "city", "country",
            "country_code", "prize_money", "start_date", "end_date", "club",
            "slug", "status", "year", "fip_source_url", "tournament_level",
            "balls_used", "venue_type", "altitude", "avg_temperature",
            "avg_humidity", "court_speed_index", "matches_scraped"
        ]

        cleaned_data = []
        for entry in data:
            clean_entry = {k: v for k, v in entry.items() if k in allowed_columns}
            cleaned_data.append(clean_entry)

        return cleaned_data