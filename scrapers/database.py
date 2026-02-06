import os
import sys
import requests
from datetime import datetime
from supabase import create_client, Client

# Importar configuración desde el directorio padre
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, SUPABASE_KEY

class VoleAIDB:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("❌ Faltan credenciales de Supabase en config.py o entorno.")
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def load_existing_tournaments(self):
        print("   📂 Loading existing tournaments from Supabase...")
        res = self.client.table("tournaments").select("*").execute()
        data = res.data
        print(f"   ✅ Loaded {len(data)} existing tournaments")
        return data

    def load_existing_static_players(self):
        print("   📂 Loading existing players from Supabase...")
        all_players = []
        limit = 1000
        offset = 0

        while True:
            response = self.client.table("players") \
                .select("*") \
                .range(offset, offset + limit - 1) \
                .execute()
            
            data = response.data
            all_players.extend(data)
            
            # Si recibimos menos de 1000, significa que llegamos al final
            if len(data) < limit:
                break
                
            offset += limit

        print(f"Total recuperado: {len(all_players)}")
        return all_players
    
    def load_existing_dynamic_players(self):
        print("   📂 Loading existing dynamic players from Supabase...")
        all_players = []
        limit = 1000
        offset = 0

        while True:
            response = self.client.table("dynamic_players") \
                .select("*") \
                .range(offset, offset + limit - 1) \
                .execute()
            
            data = response.data
            all_players.extend(data)
            
            # Si recibimos menos de 1000, significa que llegamos al final
            if len(data) < limit:
                break
                
            offset += limit

        print(f"Total recuperado: {len(all_players)}")
        return all_players

    def load_existing_matches(self):
        print("   📂 Loading existing matches from Supabase...")
        all_matches = []
        limit = 1000
        offset = 0

        while True:
            response = self.client.table("matches") \
                .select("*") \
                .range(offset, offset + limit - 1) \
                .execute()
            
            data = response.data
            all_matches.extend(data)
            
            # Si recibimos menos de 1000, significa que llegamos al final
            if len(data) < limit:
                break
                
            offset += limit

        print(f"Total recuperado: {len(all_matches)}")
        return all_matches
    
    def save_tournaments(self, tournaments_list):
        if not tournaments_list:
            print("⚠️ No data to save.")
            return

        allowed_columns = [
            "tournaments_id", "event_code", "full_name", "city", "country",
            "country_code", "prize_money", "start_date", "end_date", "club",
            "slug", "status", "year", "fip_source_url", "tournament_level",
            "venue", "balls_used", "venue_type", "altitude", "avg_temperature",
            "avg_humidity", "court_speed_index", "matches_scraped"
        ]

        cleaned_data = []
        for entry in tournaments_list:
            clean_entry = {k: v for k, v in entry.items() if k in allowed_columns}
            cleaned_data.append(clean_entry)

        try:
            self.client.table("tournaments").upsert(cleaned_data, on_conflict="tournaments_id").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def save_static_players(self, players_list):
        if not players_list:
            print("⚠️ No data to save.")
            return
        try:
            self.client.table("players").upsert(players_list).execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def save_dynamic_players(self, players_list):
        if not players_list:
            print("⚠️ No data to save.")
            return
        try:
            self.client.table("dynamic_players").upsert(players_list, on_conflict="slug, snapshot_date").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def save_player_images(self, players):

        placeholder_url = "https://www.padelfip.com/wp-content/uploads/2023/02/generico.png"

        for player in players:
            if player['image_url'] == placeholder_url:
                print(f"⚠️ Placeholder image detected for {player['slug']}. Skipping upload.")
                del player['image_url']
                continue
            if player['image_url']:
                try:
                    response = requests.get(player['image_url'], stream=True)
                    if response.status_code != 200:
                        print(f"⚠️ Can't download image for {player['slug']}. Most likely player image is missing.")
                    else:
                        file_extension = player['image_url'].split('.')[-1].split('?')[0]
                        file_path = f"{player['slug']}.{file_extension}"

                        if not player.get('image_public_url'):
                            try:
                                self.client.storage.from_("player-images").upload(
                                    path=file_path,
                                    file=response.content,
                                    file_options={"content-type": f"image/{file_extension}"}
                                )
                                print(f"✅ Picture uploaded: {file_path}")
                            except Exception as e:
                                print(f"ℹ️ The file might already exist in storage")

                        public_url = self.client.storage.from_("player-images").get_public_url(file_path)

                        player['image_public_url'] = public_url

                except Exception as e:
                    print(f"❌ Error procesando imagen para {player['slug']}: {e}")
            del player['image_url']
        return players
            
    def save_matches(self, matches):
        if not matches:
            print("⚠️ No data to save.")
            return
        try:
            self.client.table("matches").upsert(matches, on_conflict="tournaments_match_id").execute()
            print("   ✅ Database synchronization complete.")
        except Exception as e:
            print(f"   ❌ Critical Error in DB Upsert: {e}")

    def update_finished_status(self, existing_data):
        """Revisa torneos antiguos y los marca como Finished si la fecha ya pasó."""
        updated_count = 0
        to_update = []
        
        for t in existing_data:
            if t.get('status') != 'Finished':
                end_date_str = t.get('end_date_utc') or t.get('end_date')
                if end_date_str:
                    try:
                        # Limpiar fecha si viene con hora
                        clean_date = end_date_str.split(' ')[0]
                        end_date = datetime.strptime(clean_date, "%Y-%m-%d")
                        if end_date < datetime.now():
                            t['status'] = 'Finished'
                            to_update.append(t)
                            updated_count += 1
                    except:
                        continue
        
        if to_update:
            print(f"   🔄 Auto-closing {updated_count} finished tournaments...")
            self.save_tournaments(to_update)
