import requests
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from config_loader import cfg


@dataclass
class WeatherHour:
    """Represents an hourly weather forecast."""
    timestamp: datetime
    condition: str
    temperature: float
    humidity: int
    wind_speed: float
    precipitation: float

@dataclass
class WeatherDay:
    """Represents a daily weather forecast."""
    timestamp: datetime
    condition: str
    temp_max: float
    temp_min: float
    precipitation_probability: Optional[int]

@dataclass
class WeatherStatus:
    """Represents the current weather status."""
    status: str
    temperature: float
    humidity: int
    last_update: datetime


class MeteoHaApi:
    """API to interact with Home Assistant for weather data.

    Methods:
        __init__(entity_id) : Initializes the API with the entity ID.
        fetch_current_status() -> WeatherStatus : Fetches the current weather status.
        fetch_hourly_forecast() -> List[WeatherHour] : Fetches the hourly weather forecast.
        fetch_daily_forecast() -> List[WeatherDay] : Fetches the daily weather forecast.
        base_url_services() -> str : Returns the base URL for the weather services.
    """

    def __init__(self, entity_id=cfg.HA_WEATHER_LOCATION):
        self.host = f"http://{cfg.HA_HOSTNAME}:8123/api"
        self.token = cfg.HA_TOKEN
        self.entity_id = entity_id
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def fetch_current_status(self) -> WeatherStatus:
        r = requests.get(f"{self.host}/states/{self.entity_id}", headers=self.headers)
        r.raise_for_status()
        data = r.json()
        attr = data['attributes']
        
        return WeatherStatus(
            status=data['state'],
            temperature=attr.get('temperature'),
            humidity=attr.get('humidity'),
            last_update=datetime.fromisoformat(data['last_updated'])
        )

    def fetch_hourly_forecast(self) -> List[WeatherHour]:
        url = f"{self.base_url_services()}?return_response"
        payload = {"entity_id": self.entity_id, "type": "hourly"}
        
        r = requests.post(url, json=payload, headers=self.headers)
        raw_list = r.json()["service_response"][self.entity_id]["forecast"]
        
        return [
            WeatherHour(
                timestamp=datetime.fromisoformat(h['datetime']),
                condition=h['condition'],
                temperature=h['temperature'],
                humidity=h.get('humidity', 0),
                wind_speed=h.get('wind_speed', 0),
                precipitation=h.get('precipitation', 0)
            ) for h in raw_list
        ]

    def fetch_daily_forecast(self) -> List[WeatherDay]:
        url = f"{self.base_url_services()}?return_response"
        payload = {"entity_id": self.entity_id, "type": "daily"}
        
        r = requests.post(url, json=payload, headers=self.headers)
        raw_list = r.json()["service_response"][self.entity_id]["forecast"]
        
        return [
            WeatherDay(
                timestamp=datetime.fromisoformat(j['datetime']),
                condition=j['condition'],
                temp_max=j.get('temperature'),
                temp_min=j.get('templow'),
                precipitation_probability=j.get('precipitation_probability')
            ) for j in raw_list
        ]

    def base_url_services(self):
        return f"{self.host}/services/weather/get_forecasts"


if __name__ == "__main__":
    meteo = MeteoHaApi()
    current = meteo.fetch_current_status()
    hours = meteo.fetch_hourly_forecast()
    days = meteo.fetch_daily_forecast()

    print(f"Currently in {cfg.HA_WEATHER_LOCATION} : {current.temperature}°C, sky {current.status}")
    
    max_24h = max(h.temperature for h in hours[:24])
    print(f"Max forecasted in the next 24 hours : {max_24h}°C")

    days_rain = [j.timestamp.strftime("%A") for j in days if j.condition == "rainy"]
    print(f"Rainy days forecasted : {', '.join(days_rain)}")
