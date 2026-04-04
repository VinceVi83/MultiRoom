import sys, json, os, PyPDF2, re, datetime
from pathlib import Path
from thefuzz import fuzz
import logging
logging.getLogger("PyPDF2").setLevel(logging.ERROR)

from config_loader import cfg 
from tools.llm_agent import llm
from plugins.agenda.my_calendar import CalendarService

TICKETS_DIR = Path(cfg.agenda.DATA_DIR) / "concert_tickets"
INDEX_FILE = TICKETS_DIR / "concerts.json"
BLACKLIST = [w.strip().upper() for w in cfg.agenda.filter.BLACKLIST_NAMES.split(",")]
KEYWORDS = [w.strip().upper() for w in cfg.agenda.filter.ADDR_KEYWORDS.split(",")]

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
            print(f"Warning: ICS template not found at {template_path}")
            return False
        
        with open(template_path, "r", encoding="utf-8") as t:
            template_content = t.read()
        
        ics_path = TICKETS_DIR / f"tmp_{pdf_name.replace('.pdf', '')}.ics"
        with open(ics_path, "w", encoding="utf-8") as f:
            f.write(template_content.format(**params))
        return True
    except Exception as e:
        print(f"Error reading ICS template: {e}")
        return False

def clean_pdf_text(raw_text):
    if not raw_text:
        return ""
    
    price_pattern = re.compile(r"\b\d+([,.]\d{2})?\s*(?:EUR|EURO|€)\b", re.IGNORECASE)
    text_no_price = price_pattern.sub("", raw_text)
    
    filtered = []
    for line in text_no_price.split('\n'):
        strip_line = line.strip()
        if strip_line and "." not in strip_line:
            if not any(name in strip_line.upper() for name in BLACKLIST):
                filtered.append(re.sub(r'\s+', ' ', strip_line).strip())
    return " ".join(filtered)

def extract_ticket_info(text):
    if not text:
        current_time = datetime.now().strftime("%Y%m%dT%H%M%S")
        return {"date": current_time, "location": None}
    
    price_pattern = re.compile(r"\b\d+([,.]\d{2})?\s*(?:EUR|EURO|€)\b", re.IGNORECASE)
    text = price_pattern.sub("", text)
    day, month, year = "01", "01", "2026"
    hour, minute = "19", "00"
    now = datetime.datetime.now()
    valid_matches = []
    
    pattern = r"(\d{1,5}.*?(?:" + "|".join(KEYWORDS) + r").*?\d{5})"
    def is_blacklisted(s):
        return sum(1 for word in BLACKLIST if word in s.upper()) >= 2

    for m in re.finditer(r"\b(\d{2})([/-])(\d{2})\2(\d{2,4})\b", text):
        d, m_val, y = m.group(1), m.group(3), m.group(4)
        if len(y) == 2: y = "20" + y
        valid_matches.append((d, m_val, y, m.start()))

    for m in re.finditer(r"\b(\d{1,2})\s+([a-zéû\.]+?)\s+(\d{2,4})\b", text, re.IGNORECASE):
        d, m_name, y = m.group(1).zfill(2), m.group(2).lower().replace('.', '')[:3], m.group(3)
        if len(y) == 2: y = "20" + y
        if m_name in cfg.agenda.filter.MONTH:
            valid_matches.append((d, cfg.agenda.filter.MONTH[m_name], y, m.start()))

    future_dates = []
    for d, m_val, y, pos in valid_matches:
        try:
            dt_obj = datetime.datetime(int(y), int(m_val), int(d))
            if dt_obj.date() >= now.date():
                future_dates.append((d, m_val, y, pos))
        except ValueError:
            continue

    if future_dates:
        day, month, year, pos = future_dates[0]
        context = text[max(0, pos-50) : min(len(text), pos+100)]
        m_time = re.search(r"\b(\d{1,2})[H:](\d{0,2})\b", context, re.IGNORECASE)
        if m_time:
            hour = m_time.group(1).zfill(2)
            minute = m_time.group(2).zfill(2) if m_time.group(2) else "00"
    else:
        return {"date": "20260101T190000", "location": None}

    addr = None

    for line in text.split('\n'):
        u_line = line.strip().upper()
        for trigger, forced_addr in cfg.agenda.filter.VENUES.items():
            if trigger in u_line:
                addr = forced_addr
                break
        if addr: break
        if is_blacklisted(u_line): continue
        match = re.search(pattern, u_line)
        if match:
            addr = match.group(1).strip()

    if addr is None:
        clean_full_text = " ".join(text.split())
        matches = re.finditer(pattern, clean_full_text, re.IGNORECASE)
        for m in matches:
            potential_addr = m.group(1).strip()
            if not is_blacklisted(potential_addr):
                addr = potential_addr.upper()
                break
    return {"date": f"{year}{month}{day}T{hour}{minute}00", "location": addr}

def sync_tickets_to_calendar(verbose=False):
    calendar = CalendarService()
    index = json.load(open(INDEX_FILE, "r", encoding="utf-8")) if INDEX_FILE.exists() else {}
    events = calendar.fetch_calendar_events(keyword="concert", limit=0)
    result = {
        "added_tickets": [],
        "created_ics": []
    }

    for pdf_path in TICKETS_DIR.glob("*.pdf"):
        if any(pdf_path.name == val for val in index.values()): continue
        
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                raw_text = "".join([p.extract_text() for p in reader.pages[:2]])
                clean_text = clean_pdf_text(raw_text)
        except Exception:
            continue

        res_artist = llm.execute(clean_text, cfg.EXTRACT_ARTIST_AGENT)
        res_venue = llm.execute(clean_text, cfg.EXTRACT_VENUE_AGENT)
        res_date = llm.execute(clean_text, cfg.EXTRACT_DATE_AGENT)

        ticket_artist = str(res_artist.get('artist', 'UNKNOWN') if isinstance(res_artist, dict) else res_artist).strip().upper()
        ai_addr = str(res_venue.get('location', 'UNKNOWN') if isinstance(res_venue, dict) else res_venue).strip()
        ai_date = str(res_date.get('date', 'UNKNOWN') if isinstance(res_date, dict) else res_date).strip()

        infos = extract_ticket_info(raw_text)
        if infos["location"] is None or len(infos["location"]) > 50:
            infos["location"] = ai_addr

        infos["date"] = ai_date
        if verbose:
            print(f"\n--- Processing: {pdf_path.name} ---")
            print(f"  Artist  : {ticket_artist}")
            print(f"  Date     : {infos['date']}")
            print(f"  Location : {infos['location']}")

        best_match, highest_score = None, 0
        for event in events:
            title = event["summary"]
            score = fuzz.token_set_ratio(ticket_artist, title.upper())
            if score > highest_score:
                highest_score, best_match = score, title

        if highest_score >= 80:
            matched_event = next((e for e in events if e["summary"] == best_match), None)
            if matched_event:
                event_key = f"[{matched_event['dt'].strftime('%Y/%m/%d')}] {best_match}"
                index[event_key] = pdf_path.name
                
                result["added_tickets"].append({event_key: pdf_path.name})
        else:
            create_tmp_ics(pdf_path.name, {"artist": ticket_artist, "date": infos["date"], "location": infos["location"]})
            
            result["created_ics"].append(pdf_path.name)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=4, ensure_ascii=False)
    
    return result

if __name__ == "__main__":
    results = sync_tickets_to_calendar(verbose=True)
    
    print("\n--- UPDATE REPORT ---")
    print(f"Added tickets ({len(results['added_tickets'])}):")
    for item in results['added_tickets']:
        print(f"  {item}")
            
    print(f"Created ICS ({len(results['created_ics'])}):")
    for filename in results['created_ics']:
        print(f"  {filename}")
    print("----------------------")
