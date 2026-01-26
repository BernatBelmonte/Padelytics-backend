import time
import requests
import re
import numpy as np
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

class TournamentEnricher:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="voleai_analytics_bot_v2")
        self.open_meteo_url = "https://archive-api.open-meteo.com/v1/archive"

    def process(self, premier_data, fip_data):
        print("\n🔹 Merging and Enriching Data...")
        enriched_list = []
        
        total = len(premier_data)
        for i, p_t in enumerate(premier_data):
            # 1. MERGE CON FIP
            fip_match = self._find_fip_match(p_t, fip_data)
            
            # 2. LIMPIEZA BÁSICA
            start_date = str(p_t.get('start_date_utc', '')).split(' ')[0]
            end_date = str(p_t.get('end_date_utc', '')).split(' ')[0]
            

            # 3. OBJETO BASE
            tourney = {
                **p_t,
                'fip_source_url': fip_match.get('source_url') if fip_match else None,
                'tournament_level': fip_match.get('tournament_level') if fip_match else None,
                'venue': fip_match.get('venue') if fip_match else None,
                'balls_used': fip_match.get('balls_used') if fip_match else None,
                'venue_type': fip_match.get('venue_type') if fip_match else None,
                'status': fip_match.get('status') if fip_match else None
            }
            tourney['prize_money'] = fip_match.get('prize_money') if fip_match else None

            # 4. GEOCODING & WEATHER
            print(f"    [{i+1}/{total}] Enriching: {tourney['full_name']} ({tourney['city']})")
            
            if tourney['city']:
                lat, lon = self._get_coordinates(tourney['city'], tourney['country'])
                if lat:
                    weather = self._get_weather_data(lat, lon, start_date, end_date)
                    if weather:
                        tourney['altitude'] = weather['altitude']
                        tourney['avg_temperature'] = weather['avg_temperature']
                        tourney['avg_humidity'] = weather['avg_humidity']
                        
                        # 5. SPEED INDEX
                        tourney['court_speed_index'] = self._calculate_smart_speed_index(tourney)
            print(f"        Altitude={tourney.get('altitude')}, Temp={tourney.get('avg_temperature')}, Humidity={tourney.get('avg_humidity')}, SpeedIndex={tourney.get('court_speed_index')}")
            enriched_list.append(tourney)
            # time.sleep(1) # Respetar APIs

        return enriched_list

    def _find_fip_match(self, p_t, fip_data):
        p_start = str(p_t.get('start_date_utc', '')).split(' ')[0]
        if not p_start: return None
        try:
            p_date = datetime.strptime(p_start, "%Y-%m-%d")
        except: return None

        for f_t in fip_data:
            f_start = f_t.get('start_date')
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
        # Lógica de proxy histórico si la fecha es futura
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
            r = requests.get(self.open_meteo_url, params=params).json()
            if "hourly" in r:
                # Filtrar horas de juego (11h - 23h)
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
        is_indoor = True if 'indoor' in str(t.get('venue_type', '')).lower() else False
        alt = t.get('altitude') or 0
        temp = t.get('avg_temperature') or 20
        hum = t.get('avg_humidity') or 50

        alt_score = alt * 0.012
        
        # Temperatura (No lineal)
        if temp < 10: temp_score = (temp - 10) * 1.5
        elif temp <= 22: temp_score = (temp - 10) * 0.5
        else: temp_score = 6 + (temp - 22) * 2.0
        
        # Humedad
        hum_penalty = (hum - 45) * 0.5 if hum > 45 else 0

        # Peso del clima (menos impacto si es Indoor)
        weight = 0.2 if is_indoor else 1.0
        
        indoor_bonus = 5 if is_indoor else 0

        return 50 + alt_score + (temp_score * weight) - (hum_penalty * weight) + indoor_bonus