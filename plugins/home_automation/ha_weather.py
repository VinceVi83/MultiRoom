import requests
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from config_loader import cfg


@dataclass
class WeatherHour:
    """Weather Hour Plugin
    
    Role: Represents an hourly weather forecast with timestamp, condition, temperature, humidity, wind speed and precipitation.
    
    Methods:
        __init__(self, timestamp, condition, temperature, humidity, wind_speed, precipitation) : Initialize the hourly weather data.
    """
    timestamp: datetime
    condition: str
    temperature: float
    humidity: int
    wind_speed: float
    precipitation: float


@dataclass
class WeatherDay:
    """Weather Day Plugin
    
    Role: Represents a daily weather forecast with timestamp, condition, max temperature, min temperature and precipitation probability.
    
    Methods:
        __init__(self, timestamp, condition, temp_max, temp_min, precipitation_probability) : Initialize the daily weather data.
    """
    timestamp: datetime
    condition: str
    temp_max: float
    temp_min: float
    precipitation_probability: Optional[int]


@dataclass
class WeatherStatus:
    """Weather Status Plugin
    
    Role: Represents the current weather status with status, temperature, humidity and last update time.
    
    Methods:
        __init__(self, status, temperature, humidity, last_update) : Initialize the current weather status.
        display(self) : Display the weather report as formatted string.
    """
    status: str
    temperature: float
    humidity: int
    last_update: datetime

    def display(self):
        return (
            f"\n--------------\n"
            f"Weather Report\n"
            f"--------------\n"
            f"Status: {self.status}\n"
            f"Temp: {self.temperature}°C\n"
            f"Humidity: {self.humidity}%\n"
            f"Updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"--------------\n"
        )


class MeteoHaApi:
    """Meteo Home Automation API Plugin
    
    Role: API to interact with Home Assistant for weather data including current status, hourly and daily forecasts.
    
    Methods:
        __init__(self, city) : Initializes the API with the entity ID.
        fetch_current_status(self) -> WeatherStatus : Fetches the current weather status.
        fetch_hourly_forecast(self) -> List[WeatherHour] : Fetches the hourly weather forecast.
        fetch_daily_forecast(self) -> List[WeatherDay] : Fetches the daily weather forecast.
        base_url_services(self) -> str : Returns the base URL for the weather services.
    """

    def __init__(self, city=cfg.home_automation.HA_WEATHER_LOCATION):
        self.host = f"http://{cfg.home_automation.HA_HOSTNAME}:8123/api"
        self.token = cfg.home_automation.HA_TOKEN
        self.city = city
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def fetch_current_status(self) -> WeatherStatus:
        r = requests.get(f"{self.host}/states/{self.city}", headers=self.headers)
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
        payload = {"city": self.city, "type": "hourly"}
        
        r = requests.post(url, json=payload, headers=self.headers)
        raw_list = r.json()["service_response"][self.city]["forecast"]
        
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
        payload = {"city": self.city, "type": "daily"}
        
        r = requests.post(url, json=payload, headers=self.headers)
        raw_list = r.json()["service_response"][self.city]["forecast"]
        
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

    print(f"Currently in {cfg.home_automation.HA_WEATHER_LOCATION} : {current.temperature}°C, sky {current.status}")
    
    max_24h = max(h.temperature for h in hours[:24])
    print(f"Max forecasted in the next 24 hours : {max_24h}°C")

    days_rain = [j.timestamp.strftime("%A") for j in days if j.condition == "rainy"]
    print(f"Rainy days forecasted : {', '.join(days_rain)}")
