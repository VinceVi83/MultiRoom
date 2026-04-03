import requests
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class WeatherHour:
    """Weather Hour Forecast Dataclass
    
    Role: Represents a single hour of weather forecast data.
    
    Attributes:
        timestamp: The timestamp for this hour.
        condition: Weather condition for this hour.
        temperature: Temperature for this hour.
        humidity: Humidity percentage for this hour.
        wind_speed: Wind speed for this hour.
        precipitation: Precipitation amount for this hour.
    """
    timestamp: datetime
    condition: str
    temperature: float
    humidity: int
    wind_speed: float
    precipitation: float


@dataclass
class WeatherDay:
    """Weather Day Forecast Dataclass
    
    Role: Represents a single day of weather forecast data.
    
    Attributes:
        timestamp: The timestamp for this day.
        condition: Weather condition for this day.
        temp_max: Maximum temperature for this day.
        temp_min: Minimum temperature for this day.
        precipitation_probability: Probability of precipitation for this day.
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


class WeatherHaApi:
    """Weather Home Automation API Plugin
    
    Role: API to interact with Home Assistant for weather data including current status, hourly and daily forecasts.
    
    Methods:
        __init__(self, cfg) : Initializes the API with the entity ID.
        fetch_current_status(self) -> WeatherStatus : Fetches the current weather status.
        fetch_hourly_forecast(self) -> List[WeatherHour] : Fetches the hourly weather forecast.
        fetch_daily_forecast(self) -> List[WeatherDay] : Fetches the daily weather forecast.
        base_url_services(self) -> str : Returns the base URL for the weather services.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.host = f"http://{self.cfg.ha_config.HA_HOSTNAME}:8123/api"
        self.token = self.cfg.ha_config.HA_TOKEN
        self.city = self.cfg.ha_config.HA_WEATHER_LOCATION
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def base_url_services(self):
        return f"{self.host}/services/weather/get_forecasts"

    def _fetch_forecast(self, forecast_type):
        url = f"{self.base_url_services()}?return_response"
        payload = {"city": self.city, "type": forecast_type}
        
        r = requests.post(url, json=payload, headers=self.headers)
        r.raise_for_status()
        raw_list = r.json()["service_response"][self.city]["forecast"]
        
        return raw_list

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
        raw_list = self._fetch_forecast("hourly")
        
        hourly_list = []
        for h in raw_list:
            hourly_list.append(WeatherHour(
                timestamp=datetime.fromisoformat(h['datetime']),
                condition=h['condition'],
                temperature=h['temperature'],
                humidity=h.get('humidity', 0),
                wind_speed=h.get('wind_speed', 0),
                precipitation=h.get('precipitation', 0)
            ))
        
        return hourly_list

    def fetch_daily_forecast(self) -> List[WeatherDay]:
        raw_list = self._fetch_forecast("daily")
        
        daily_list = []
        for j in raw_list:
            daily_list.append(WeatherDay(
                timestamp=datetime.fromisoformat(j['datetime']),
                condition=j['condition'],
                temp_max=j.get('temperature'),
                temp_min=j.get('templow'),
                precipitation_probability=j.get('precipitation_probability')
            ))
        
        return daily_list
