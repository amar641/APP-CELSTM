# Weather

**Adapter:** `infrastructure.weather.client.OpenMeteoWeatherProvider`
(implements `application.ingestion.ingest_weather.WeatherProvider`)

## Source
Open-Meteo `/v1/forecast` `current` endpoint, sampled at the AOI's
centroid (Open-Meteo has no bbox query — see the class docstring for why
that's an accepted v1 simplification).

## Config
- `WEATHER_PROVIDER` — documents which provider is active (`open-meteo`
  today); swapping providers means adding a new class implementing
  `WeatherProvider` and changing the wiring in `api/dependencies.py`.
- `WEATHER_API_KEY`, `WEATHER_API_BASE_URL`

## Fields consumed
`temperature_2m`, `wind_speed_10m`, `wind_direction_10m`,
`relative_humidity_2m` → `domain.entities.weather_observation.WeatherObservation`.

## Usage
Joined onto a thermal event by nearest-in-space-and-time
(`WeatherRepository.find_nearest_in_time`, `radius_km` default 25) during
feature assembly — wind direction/speed and humidity are meaningful
inputs for distinguishing a spreading wildfire from a fixed industrial
source.
