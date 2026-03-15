"""
Web scraping and search aggregation module.
Handles multi-engine search results, scoring, and deep content extraction.
"""
import requests
import sys
import json
from datetime import datetime
from pathlib import Path
from trafilatura import fetch_url, extract
from config_loader import cfg
from tools.llm_agent import llm

class ScraperService:
    """
    Web scraping and search aggregation service (Singleton).

    Main methods:
    - get_search_candidates(query, ...): Searches and scores results via SearXNG.
    - scrape_full_content(url): Extracts raw text from a web page (deep analysis).
    - get_web_summary(query, agent_cfg): Quick summary based on snippets.
    - get_web_discovery(query): List of candidates for user selection.
    - get_web_extraction(query, candidate, agent_cfg): Deep analysis of a specific page.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ScraperService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        self.debug = False
        if self._initialized:
            return

        if self.debug:
            test = self.get_search_candidates("ping", count=1)
            print("ScraperService OK" if test else "ScraperService KO")

        self._initialized = True

    def get_search_candidates(self, query, count=8, lang=cfg.LANGUAGE2, time_boost=False):
        """Retrieve and score search results."""
        try:
            params = {
                "q": query,
                "format": "json",
                "language": lang,
                "safesearch": 1
            }
            response = requests.get(cfg.SEARXNG_URL, params=params, timeout=10)
            results = response.json().get('results', [])
        except Exception as e:
            print(f"SEARCH_ERROR: {e}")
            return []

        now = datetime.now()
        candidates = []
        for res in results:
            url = res.get('url', '').lower()
            score = 0

            if any(domain in url for domain in cfg.LIST_PRIORITY_DOMAINS):
                score += 1.5

            date_str = res.get('publishedDate')
            if date_str:
                try:
                    days_old = (now - datetime.strptime(date_str[:10], '%Y-%m-%d')).days
                    if time_boost:
                        score += round(0.8 * (0.85 ** days_old), 3)
                    elif days_old <= 14:
                        score += round(0.1 * (1 - (days_old / 14)), 3)
                except ValueError:
                    pass

            candidates.append({
                "title": res.get('title', 'Untitled'),
                "source": url.split('/')[2].replace('www.', '') if '/' in url else 'Unknown',
                "score": round(score, 3),
                "url": url,
                "snippet": res.get('content', '')
            })
        return sorted(candidates, key=lambda x: x['score'], reverse=True)[:count]

    def scrape_full_content(self, url):
        """Cleanly extract text from a URL."""
        downloaded = fetch_url(url)
        if not downloaded:
            return None
        return extract(downloaded, include_tables=True, include_comments=False)

    def get_web_summary(self, query, agent_cfg):
        """Quick summary via snippets (2k-4k context)."""
        candidates = self.get_search_candidates(query, count=6)
        if not candidates:
            return "NO_RESULTS_FOUND"

        context = "AGGREGATED_SNIPPETS:\n"
        for c in candidates:
            context += f"SOURCE: {c['source']} | SNIPPET: {c['snippet']}\n\n"

        payload = (
            f"USER_QUERY: {query}\n\n"
            f"{context}\n"
            f"INSTRUCTION: Summarize the information based ONLY on the snippets provided."
        )

        return llm.execute(user_input=payload, agent_cfg=agent_cfg)

    def get_web_discovery(self, query, time_boost=False):
        """Interface for interactive selection."""
        candidates = self.get_search_candidates(query, count=5, time_boost=time_boost)
        if not candidates:
            return None, "NO_RESULTS_FOUND"

        formatted_list = "SEARCH_RESULTS:\n"
        for i, c in enumerate(candidates, 1):
            formatted_list += f"{i}: {c['title']} ({c['source']})\n"

        return candidates, formatted_list

    def get_web_extraction(self, query, selected_candidate, agent_cfg):
        """Scraping deep (32k context) of a candidate."""
        content = self.scrape_full_content(selected_candidate['url'])
        if not content:
            return "EXTRACTION_FAILED"

        payload = (
            f"QUERY: {query}\n"
            f"SOURCE_URL: {selected_candidate['url']}\n\n"
            f"FULL_CONTENT:\n{content}"
        )
        return llm.execute(user_input=payload, agent_cfg=agent_cfg)

    def print_weather_report(self, data):
        if not isinstance(data, dict):
            print(data)
            return
        g = data.get('global', {})
        p = data.get('periods', {})

        print(f"\n{'='*45}")
        print(f" 🌦️  WEATHER REPORT : {g.get('summary', 'Unknown')}")
        print(f"{'='*45}")
        print(f" Temperature : {g.get('temp_avg')}°C | Rain : {g.get('rain_risk')}")
        print(f"{'-'*45}")

        for period, details in p.items():
            icon = "🌧️" if details.get('rain') else "🌤️"
            name = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening"}.get(period, period.upper())
            print(f" {icon} {name:<12} | {details.get('temp')}°C | {details.get('desc')}")
        print(f"{'='*45}\n")

if __name__ == "__main__":
    scraper = ScraperService()
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Weather Paris"
    report = scraper.get_web_summary(query, cfg.GlobalLLM.weather_forecast)
    scraper.print_weather_report(report)
