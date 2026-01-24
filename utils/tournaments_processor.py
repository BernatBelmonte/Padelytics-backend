import json
import os
import sys
import time
import requests
import numpy as np
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    RAW_PREMIER_PADEL_TOURNAMENTS_FILE, 
    RAW_FIP_TOURNAMENTS_FILE, 
    JOINED_TOURNAMENTS_FILE, 
    FINAL_TOURNAMENTS_FILE, 
    OPEN_METEO_URL
)

class TournamentsProcessor:
    def __init__(self):
        self.premier_data = []
        self.fip_data = []
        self.existing_data = []
        self.geolocator = Nominatim(user_agent="padel_analytics_bot_v2")

    def start(self):
        print("🏟️  Tournaments Processor (Merger + Enricher)")
        print("=============================================")
        self._load_existing_data()
        if self._run_merger():
            print("\n🔹 PHASE 2: Enriching Data (Geo & Weather)...")
            self._run_enricher()
        else:
            print("❌ Merging failed. Aborting enrichment.")

    def _load_existing_data(self):
        if os.path.exists(FINAL_TOURNAMENTS_FILE):
            with open(FINAL_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
                self.existing_data = json.load(f)
            print(f"   📂 Loaded existing enriched data: {len(self.existing_data)} tournaments.")
        else:
            print("   ⚠️ No existing enriched data found.")

    def _run_merger(self):
        if not self._load_raw_data(): 
            return False

        print("\n   🔄 Initiating Merge...")
        merged_count = 0

        for t in self.premier_data:
            fip_match = self.find_fip_match(t)
            if fip_match:
                t['fip_source_url'] = fip_match.get('source_url')
                t['tournament_level'] = fip_match.get('tournament_level')
                t['venue'] = fip_match.get('venue')
                t['balls_used'] = fip_match.get('balls_used')
                t['venue_type'] = fip_match.get('venue_type')
                t['prize_money_fip'] = fip_match.get('prize_money')
                t['status'] = fip_match.get('status')
                t['is_enriched'] = False # Mark for enrichment later
                merged_count += 1

        with open(JOINED_TOURNAMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.premier_data, f, indent=4, ensure_ascii=False)

        print(f"   ✅ Merge Complete.")
        print(f"   - FIP data merged into: {merged_count} tournaments")
        print(f"   - Saved intermediate to: {JOINED_TOURNAMENTS_FILE}")
        return True

    def _load_raw_data(self):
        print("   📂 Loading raw datasets...")
        
        # 1. Premier Padel
        if os.path.exists(RAW_PREMIER_PADEL_TOURNAMENTS_FILE):
            with open(RAW_PREMIER_PADEL_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
                self.premier_data = json.load(f)
            print(f"      ✅ Premier Padel: {len(self.premier_data)} tournaments.")
        else:
            print(f"      ❌ Error: Not found {RAW_PREMIER_PADEL_TOURNAMENTS_FILE}")
            return False

        # 2. FIP
        if os.path.exists(RAW_FIP_TOURNAMENTS_FILE):
            with open(RAW_FIP_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
                self.fip_data = json.load(f)
            print(f"      ✅ FIP: {len(self.fip_data)} tournaments.")
        else:
            print("      ⚠️ FIP file not found. Skipping FIP merge data.")
            return False
        
        return True

    @staticmethod
    def _parse_premier_date(date_str):
        if not date_str: return None
        try:
            clean_date = str(date_str).split(' ')[0] 
            return datetime.strptime(clean_date, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(str(date_str), "%Y-%m-%d")
            except:
                return None

    @staticmethod
    def _parse_fip_date(date_str):
        if not date_str: return None
        try:
            return datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
        except ValueError:
            return None

    def find_fip_match(self, p_tournament):
        p_start_str = p_tournament.get('start_date_utc')
        if not p_start_str: return None

        p_date = self._parse_premier_date(p_start_str)
        if not p_date: return None

        for fip_t in self.fip_data:
            f_start_str = fip_t.get('start_date')
            if not f_start_str: continue

            f_date = self._parse_fip_date(f_start_str)
            if not f_date: continue

            delta = abs((p_date - f_date).days)
            if delta <= 3:
                return fip_t
        return None

    def _calculate_smart_speed_index(self, t):
        """ Calculates a Smart Court Speed Index based on multiple factors:
            - Indoor or Outdoor courts
            - Altitude
            - Average Temperature
            - Average Humidity
        """
        is_indoor = True if 'indoor' in str(t.get('venue_type', '')).lower() else False
        
        # Higher = Faster. 1000m = +12 points
        altitude_score = t['altitude'] * 0.012

        # Temperature Score (Non-linear)
        temp = t['avg_temperature']
        raw_temp_score = np.select(
            [temp < 10, (temp >= 10) & (temp <= 22), temp > 22],
            [(temp - 10) * 1.5, (temp - 10) * 0.5, 6 + (temp - 22) * 2.0], # Penalty / Neutral / Boost
            default=0
        )
        
        # Humidity Score 
        hum = t['avg_humidity']
        raw_hum_penalty = np.where(hum > 45, (hum - 45) * 0.5, 0)
        
        # If Indoor, weather impact is reduced to 20% (0.2). If Outdoor, 100% (1.0)
        weather_weight = np.where(is_indoor, 0.2, 1.0)
        
        final_temp_score = raw_temp_score * weather_weight
        final_hum_penalty = raw_hum_penalty * weather_weight
        
        # Indoor courts are naturally faster/more consistent. Add +5 base points.
        indoor_bonus = np.where(is_indoor, 5, 0)

        # Base 50 + Alt + (Dampened Weather) + Bonus
        speed_index = 50 + altitude_score + final_temp_score - final_hum_penalty + indoor_bonus
        
        return speed_index

    def _run_enricher(self):
        if not os.path.exists(JOINED_TOURNAMENTS_FILE):
            print(f"   ❌ Intermediate file not found: {JOINED_TOURNAMENTS_FILE}")
            return

        with open(JOINED_TOURNAMENTS_FILE, 'r', encoding='utf-8') as f:
            tournaments = json.load(f)

        total = len(tournaments)
        print(f"   🔍 Checking {total} tournaments for enrichment...")
        
        enriched_count = 0
        
        for i, t in enumerate(tournaments):
            if t.get('is_enriched') == True:
                continue

            name = t.get('name', 'Unknown')
            city = t.get('city')
            country = t.get('country')
            start = t.get('start_date_utc')
            end = t.get('end_date_utc')

            print(f"\n   [{i+1}/{total}] Processing: {name} ({city})")

            if not city or not start or not end:
                print("      ⏩ Missing City or Dates. Skipping.")
                continue
            is_enriched = False
            for ex_t in self.existing_data:
                if ex_t.get('tournaments_id') == t.get('tournaments_id') and ex_t.get('is_enriched'):
                    print("      ⏩ Already enriched in existing data. Skipping.")
                    t.update(ex_t)
                    is_enriched = True
                    break
            if is_enriched:
                continue
            # Geocoding
            lat, lon = self._get_coordinates(city, country)
            if not lat:
                print("      ❌ Could not find coordinates. Skipping.")
                continue
            
            time.sleep(1)

            # Weather
            weather = self._get_weather_data(lat, lon, start, end)
            
            if weather:
                proxy_msg = " (Historical Proxy)" if weather['is_proxy'] else ""
                print(f"      ✅ Data: Alt: {weather['altitude']}m | Temp: {weather['avg_temperature']}°C | Hum: {weather['avg_humidity']}%{proxy_msg}")
                
                t['altitude'] = weather['altitude']
                t['avg_temperature'] = weather['avg_temperature']
                t['avg_humidity'] = weather['avg_humidity']
                t['court_speed_index'] = self._calculate_smart_speed_index(t)
                t['is_enriched'] = True
                enriched_count += 1
            else:
                print("      ❌ Failed to fetch weather data.")
            
            time.sleep(1.5)

        with open(FINAL_TOURNAMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tournaments, f, indent=4, ensure_ascii=False)
        
        print(f"\n🎉 Enrichment Complete. Enriched {enriched_count} new tournaments.")
        print(f"💾 Final data saved to: {FINAL_TOURNAMENTS_FILE}")

    def _get_coordinates(self, city, country):
        if not city: return None, None
        location_query = f"{city}, {country}" if country else city
        try:
            location = self.geolocator.geocode(location_query, timeout=10) # type: ignore
            if location:
                return location.latitude, location.longitude # type: ignore
        except (GeocoderTimedOut, Exception) as e:
            print(f"      ⚠️ Geocoding error for {location_query}: {e}")
        return None, None

    def _get_weather_data(self, lat, lon, start_date, end_date):
        if not start_date or not end_date: return None

        now = datetime.now()
        start_date = str(start_date).split(' ')[0]
        end_date = str(end_date).split(' ')[0]
        try:
            s_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            e_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        except (ValueError, AttributeError, TypeError):
            return None 
        
        used_historical_proxy = False
        if s_date_obj > now:
            s_date_obj = s_date_obj - timedelta(days=365)
            e_date_obj = e_date_obj - timedelta(days=365)
            start_date = s_date_obj.strftime("%Y-%m-%d")
            end_date = e_date_obj.strftime("%Y-%m-%d")
            used_historical_proxy = True

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ["temperature_2m", "relative_humidity_2m"],
            "timezone": "auto"
        }
        try:
            response = requests.get(OPEN_METEO_URL, params=params)
            data = response.json()
            if "hourly" in data:
                times = data["hourly"].get("time", [])
                temps = data["hourly"].get("temperature_2m", [])
                hums = data["hourly"].get("relative_humidity_2m", [])
                
                valid_temps = []
                valid_hums = []

                for i, t_str in enumerate(times):
                    try:
                        hour = int(t_str.split('T')[1].split(':')[0])
                        if 11 <= hour <= 23:
                            if temps[i] is not None: valid_temps.append(temps[i])
                            if hums[i] is not None: valid_hums.append(hums[i])
                    except:
                        continue

                avg_temp = sum(valid_temps) / len(valid_temps) if valid_temps else None
                avg_hum = sum(valid_hums) / len(valid_hums) if valid_hums else None
                altitude = data.get("elevation", 0)

                return {
                    "altitude": int(altitude),
                    "avg_temperature": round(avg_temp, 1) if avg_temp else None,
                    "avg_humidity": round(avg_hum, 1) if avg_hum else None,
                    "is_proxy": used_historical_proxy
                }
            
        except Exception as e:
            print(f"      ⚠️ API Error: {e}")
        return None

if __name__ == "__main__":
    bot = TournamentsProcessor()
    bot.start()