import json, os, PyPDF2, re, datetime
from pathlib import Path
from thefuzz import fuzz
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import logging
logger = logging.getLogger(__name__)
logging.getLogger("PyPDF2").setLevel(logging.ERROR)

from config_loader import cfg 
from tools.llm_agent import llm
from plugins.agenda.my_calendar import CalendarService

TICKETS_DIR = Path(cfg.agenda.DATA_DIR) / "concert_tickets"
INDEX_FILE = TICKETS_DIR / "concerts.json"

def clean_text_from_blacklist(text, blacklist):
    if not blacklist:
        return text
    
    sorted_blacklist = sorted(blacklist, key=len, reverse=True)
    pattern = re.compile('|'.join(re.escape(str(word)) for word in sorted_blacklist), re.IGNORECASE)
    
    return pattern.sub("", text)

def clean_text_generic(text):
    clean_lines = []
    segments = re.split(r'\. |\n', text) 
    
    for line in segments:
        line = line.strip()
        if len(line) > 80 or len(line) < 2: 
            continue
            
        if line.endswith(('.', '!', '?')) and len(line.split()) > 3:
            continue

        clean_lines.append(line)
            
    return "\n".join(clean_lines)

def clean_text(text, blacklist):
    cleaned = clean_text_generic(text)
    cleaned = clean_text_from_blacklist(cleaned, blacklist)
    return cleaned

def check_venue(text, current_venue):
    if current_venue: 
        return current_venue, True
    
    venues_dict = vars(cfg.agenda.filter.VENUES)
    for key, value in venues_dict.items():
        if key.lower() in text.lower():
            return value, True
            
    res_v = llm.execute(text, cfg.AGENDA.EXTRACT_VENUE_AGENT)
    blacklist = cfg.agenda.filter.BLACKLIST_NAMES
    prompt_select = f"### BLACKLIST: {blacklist}\n### LOCATIONS FOUND:\n{res_v['locations']}\n Identify main venue."
    selected_venue = llm.execute(prompt_select, cfg.AGENDA.SELECT_MAIN_VENUE_AGENT)
    verification = llm.execute(str(selected_venue), cfg.AGENDA.VERIFIER_LOCATION_AGENT)
    
    selected_location = selected_venue["selected_location"].lower()
    for key in blacklist:
        if key.lower() in selected_location:
            return None, False
    
    if "True" in str(verification) and selected_venue.get("selected_location"):
        return selected_venue["selected_location"], True
    
    return None, False

def check_date(text, current_date):
    if current_date: 
        return current_date, True
    
    res_d = llm.execute(text, cfg.AGENDA.EXTRACT_DATE_AGENT)
    event_date = next((d["value"] for d in res_d.get("dates", []) if d["label"] == "event"), None)
    return event_date, (event_date is not None)

def check_artist(text, current_artist):
    if current_artist: 
        return current_artist, True
    
    blacklist = cfg.agenda.filter.BLACKLIST_NAMES
    prompt_art = f"### BLACKLIST: {blacklist}\n### TEXT:\n{text}\nExtract main ARTIST."
    res_a = llm.execute(prompt_art, cfg.AGENDA.NAME_CLASSIFIER_AGENT)
    res_b = llm.execute(str(res_a), cfg.AGENDA.EXTRACT_ARTIST_AGENT)
    
    for key in blacklist:
        if key.lower() in str(res_b):
            return None, False

    artist = res_b["artists"][0] if res_b.get("artists") else None
    if artist and not any(b.lower() in artist.lower() for b in blacklist):
        return artist, True
        
    return None, False

def get_pdf_raw_text(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
    except Exception as e:
        logger.error(f"❌ Erreur lors de la lecture du texte brut de {pdf_path.name}: {e}")
        return ""

def get_pdf_ocr_text(pdf_path):
    try:
        model = ocr_predictor(pretrained=True)
        doc = DocumentFile.from_pdf(pdf_path)
        ocr_res = model(doc)
        
        blocks = []
        for page in ocr_res.pages:
            for block in page.blocks:
                line_texts = [" ".join([w.value for w in l.words]) for l in block.lines]
                blocks.append("\n".join(line_texts))
        return "\n\n".join(blocks)
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'OCR de {pdf_path.name}: {e}")
        return ""

def extract_ticket_data(pdf_path):
    data = {"artist": None, "venue": None, "date": None}
    flags = {"artist": False, "venue": False, "date": False}

    text_native = get_pdf_raw_text(pdf_path)
    text_clean = clean_text(text_native, cfg.agenda.filter.BLACKLIST_NAMES)
    data["venue"], flags["venue"] = check_venue(text_clean, data["venue"])
    data["date"], flags["date"] = check_date(text_clean, data["date"])
    data["artist"], flags["artist"] = check_artist(text_clean, data["artist"])

    if not all(flags.values()):
        text_ocr = get_pdf_ocr_text(pdf_path)
        text_clean = clean_text(text_ocr, cfg.agenda.filter.BLACKLIST_NAMES)
        data["venue"], flags["venue"] = check_venue(text_clean, data["venue"])
        data["date"], flags["date"] = check_date(text_clean, data["date"])
        data["artist"], flags["artist"] = check_artist(text_clean, data["artist"])

    return data, flags

def create_tmp_ics(pdf_name, info):
    artist = info.get("artist", "Unknown")
    date_raw = info.get("date", "20260101T190000")
    date_day, date_time = date_raw[:8], (date_raw[9:13] if len(date_raw) > 8 else "1900")
    now_str = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
    params = {
        "uid": f"{now_str}-{artist.replace(' ', '')}",
        "now": now_str,
        "artist": artist,
        "dtstart": f"{date_day}T{date_time}00",
        "dtend": f"{date_day}T{int(date_time[:2])+2:02d}{date_time[2:]}00",
        "location": info.get("location", "Unknown Venue")
    }
    current_dir = Path(__file__).resolve().parent
    template_path = current_dir / "template_concert.ics"
    if not template_path.is_absolute():
        ROOT = Path(__file__).resolve().parent
        template_path = ROOT / template_path

    try:
        if not template_path.exists():
            logger.info(f"Warning: ICS template not found at {template_path}")
            return False
        
        with open(template_path, "r", encoding="utf-8") as t:
            template_content = t.read()
        
        ics_path = TICKETS_DIR / f"tmp_{pdf_name.replace('.pdf', '')}.ics"
        with open(ics_path, "w", encoding="utf-8") as f:
            f.write(template_content.format(**params))
        return True
    except Exception as e:
        logger.error(f"reading ICS template: {e}")
        return False

def sync_tickets_to_calendar(verbose=False):
    calendar = CalendarService()
    index = json.load(open(INDEX_FILE, "r", encoding="utf-8")) if INDEX_FILE.exists() else {}
    events = calendar.fetch_calendar_events(cfg.system.calendar, keyword="concert", limit=0)
    result = {"added_tickets": [], "created_ics": []}

    for pdf_path in TICKETS_DIR.glob("*.pdf"):
        pdf_name = pdf_path.name
        if pdf_name in index and index[pdf_name].get("status") == "linked":
            continue

        if pdf_name in index and index[pdf_name].get("status") == "ics_pending":
            data = index[pdf_name]["data"]
        else:
            data, flags = extract_ticket_data(pdf_path)
            if not all(flags.values()):
                continue
            
            clean_artist = re.sub(r'[^a-zA-Z0-9]', '', data['artist'].replace(' ', '_'))
            new_name = f"ticket_{clean_artist}_{data['date']}.pdf"
            new_path = pdf_path.parent / new_name
            
            if pdf_name != new_name:
                os.rename(pdf_path, new_path)
                pdf_path = new_path
                pdf_name = new_name

            index[pdf_name] = {"status": "ics_pending", "data": data}

        best_match, highest_score = None, 0
        for event in events:
            title = event["summary"]
            score = fuzz.token_set_ratio(data['artist'], title.upper())
            if score > highest_score:
                highest_score, best_match = score, title

        if highest_score >= 80:
            matched_event = next((e for e in events if e["summary"] == best_match), None)
            event_key = f"[{matched_event['dt'].strftime('%Y/%m/%d')}] {best_match}"
            index[pdf_name].update({
                "status": "linked",
                "event": event_key
            })
            result["added_tickets"].append({event_key: pdf_name})
        else:
            if create_tmp_ics(pdf_name, {"artist": data['artist'], "date": data["date"], "location": data["venue"]}):
                result["created_ics"].append(pdf_name)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=4, ensure_ascii=False)
    return result

if __name__ == "__main__":
    results = sync_tickets_to_calendar(verbose=True)
    
    logger.info("\n--- UPDATE REPORT ---")
    logger.info(f"Added tickets ({len(results['added_tickets'])}):")
    for item in results['added_tickets']:
        logger.info(f"  {item}")
            
    logger.info(f"Created ICS ({len(results['created_ics'])}):")
    for filename in results['created_ics']:
        logger.info(f"  {filename}")
    logger.info("----------------------")
