import requests
import sys
from datetime import datetime
from trafilatura import fetch_url, extract
from config_loader import cfg
from tools.llm_agent import llm
import logging
logger = logging.getLogger(__name__)

class ScraperService:
    """Web Scraping Service Plugin
    
    Role: Manages web search, content extraction, and weather reporting.
    
    Methods:
        __new__(cls) : Singleton pattern implementation.
        __init__(self, debug=False) : Initialize the service instance.
        get_search_candidates(self, query, count=8, lang=None, time_boost=False) : Search for web candidates with scoring.
        scrape_full_content(self, url) : Extract full content from a URL.
        get_web_summary(self, query, agent_cfg) : Get summarized content from search results.
        get_web_discovery(self, query, time_boost=False) : Get web discovery results.
        get_web_extraction(self, query, selected_candidate, agent_cfg) : Extract content with LLM.
        print_weather_report(self, data) : Print weather report.
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
            logger.info("ScraperService OK" if test else "ScraperService KO")

        self._initialized = True

    def get_search_candidates(self, query, count=8, lang=None, time_boost=False):
        try:
            params = {
                "q": query,
                "format": "json",
                "language": lang,
                "safesearch": 1
            }
            response = requests.get(cfg.sys.config.SEARXNG_URL, params=params, timeout=10)
            response.raise_for_status()
            results = response.json().get('results', [])
        except Exception as e:
            logger.error(f"SEARCH_ERROR: {e}")
            return []

        now = datetime.now()
        candidates = []
        for res in results:
            url = res.get('url', '').lower()
            score = 0

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
        downloaded = fetch_url(url)
        if not downloaded:
            return None
        return extract(downloaded, include_tables=True, include_comments=False)

    def get_web_summary(self, query, agent_cfg):
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
        candidates = self.get_search_candidates(query, count=5, time_boost=time_boost)
        if not candidates:
            return None, "NO_RESULTS_FOUND"

        formatted_list = "SEARCH_RESULTS:\n"
        for i, c in enumerate(candidates, 1):
            formatted_list += f"{i}: {c['title']} ({c['source']})\n"

        return candidates, formatted_list

    def get_web_extraction(self, query, selected_candidate, agent_cfg):
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
            logger.info(data)
            return
        g = data.get('global', {})
        p = data.get('periods', {})

        logger.info(f"\n{'='*45}")
        logger.info(f" 🌦️  WEATHER REPORT : {g.get('summary', 'Unknown')}")
        logger.info(f"{'='*45}")
        logger.info(f" Temperature : {g.get('temp_avg')}°C | Rain : {g.get('rain_risk')}")
        logger.info(f"{'-'*45}")

        for period, details in p.items():
            icon = "🌧️" if details.get('rain') else "🌤️"
            name = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening"}.get(period, period.upper())
            logger.info(f" {icon} {name:<12} | {details.get('temp')}°C | {details.get('desc')}")
        logger.info(f"{'='*45}\n")


if __name__ == "__main__":
    scraper = ScraperService()
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Weather Paris"
    report = scraper.get_web_summary(query, cfg.ALL_PURPOSE.weather_forecast)
    scraper.print_weather_report(report)
