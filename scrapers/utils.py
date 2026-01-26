import re
from datetime import datetime
from difflib import SequenceMatcher

def clean_money(money_str):
    """Convierte strings de dinero (ej: '470,000') a enteros."""
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

def parse_dates(date_str):
    """Convierte rango de fechas DD/MM/YYYY - DD/MM/YYYY a YYYY-MM-DD."""
    try:
        parts = date_str.replace('\n', '').split('-')
        start = datetime.strptime(parts[0].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        end = datetime.strptime(parts[1].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        return start, end
    except:
        return None, None

def calculate_status(start_date, end_date):
    """Determina si el torneo es Upcoming, Active o Finished."""
    if not start_date or not end_date:
        return "Unknown"
    today = datetime.now().strftime("%Y-%m-%d")
    if today > end_date:
        return "Finished"
    elif today >= start_date and today <= end_date:
        return "Active"
    else:
        return "Upcoming"

def similar_text(a, b):
    """Calcula similitud entre dos textos (0.0 a 1.0)."""
    if a is None or b is None: return 0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def imput_value(target_data, key, reference_list):
    """Intenta rellenar datos faltantes (Venue, Balls) comparando con el histórico."""
    target_country = target_data.get('country')
    target_city = target_data.get('city') 

    if not target_country or not target_city:
        return None

    best_match_value = None
    best_score = 0
    best_city_found = None

    try:
        for candidate in reference_list:
            cand_country = candidate.get('country')
            cand_city = candidate.get('city')
            cand_value = candidate.get(key)

            if not cand_country or not cand_city or not cand_value:
                continue

            if cand_country.lower().strip() != target_country.lower().strip():
                continue

            score = similar_text(target_city, cand_city)
            
            if score > 0.7 and score > best_score:
                best_score = score
                best_match_value = cand_value
                best_city_found = cand_city

        if best_match_value:
            print(f"   ℹ️ Imputed {key}: '{best_match_value}'")
            return best_match_value

    except Exception as e:
        print(f"   ⚠️ Error imputing {key}: {e}")
    
    return None