import os
import sys
from datetime import datetime
from supabase import create_client, Client

# Importar configuración desde el directorio padre
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, SUPABASE_KEY

class TournamentsDB:
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

    def save_tournaments(self, tournaments_list):
        if not tournaments_list:
            print("⚠️ No data to save.")
            return

        allowed_columns = [
            "tournaments_id", "event_code", "full_name", "city", "country",
            "country_code", "prize_money", "start_date", "end_date", "club",
            "slug", "status", "year", "fip_source_url", "tournament_level",
            "venue", "balls_used", "venue_type", "altitude", "avg_temperature",
            "avg_humidity", "court_speed_index"
        ]

    # Limpiamos cada diccionario para que no lleve 'currency' ni nada extra
        cleaned_data = []
        for entry in tournaments_list:
            clean_entry = {k: v for k, v in entry.items() if k in allowed_columns}
            cleaned_data.append(clean_entry)

        try:
            # Upsert maneja Insert o Update basado en la Primary Key (tournaments_id)
            self.client.table("tournaments").upsert(cleaned_data).execute()
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