#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
METEO RADAR SANSE
Motor independiente de consulta meteorológica.
Ubicación: San Sebastián de los Reyes (Madrid).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


# --------------------------------------------------
# CONFIGURACIÓN DE SAN SEBASTIÁN DE LOS REYES
# --------------------------------------------------

LOCATION = {
    "name": "San Sebastián de los Reyes",
    "latitude": 40.5479,
    "longitude": -3.6262,
    "elevation": 670,
    "timezone": "Europe/Madrid",
}

API_URL = "https://api.open-meteo.com/v1/forecast"
OUTPUT_FILE = Path("data/radar.json")

MODELS = {
    "ecmwf": "ecmwf_ifs025",
    "gfs": "gfs_seamless",
    "arome": "meteofrance_arome_france_hd",
}

HOURLY_VARIABLES = [
    "temperature_2m", "apparent_temperature", "precipitation_probability",
    "precipitation", "rain", "snowfall", "weather_code", "wind_speed_10m",
    "wind_gusts_10m", "wind_direction_10m", "relative_humidity_2m",
    "cloud_cover", "freezing_level_height",
]

DAILY_VARIABLES = [
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "precipitation_probability_max",
    "wind_speed_10m_max", "wind_gusts_10m_max", "sunrise", "sunset",
]


# --------------------------------------------------
# CONSULTA A OPEN-METEO
# --------------------------------------------------

def get_model_forecast(model_name: str) -> dict:
    """Obtiene la previsión de un modelo meteorológico."""

    params = {
        "latitude": LOCATION["latitude"],
        "longitude": LOCATION["longitude"],
        "elevation": LOCATION["elevation"],
        "timezone": LOCATION["timezone"],
        "forecast_days": 7,
        "past_days": 1,
        "hourly": ",".join(HOURLY_VARIABLES),
        "daily": ",".join(DAILY_VARIABLES),
        "models": model_name,
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius",
    }

    last_error = None

    for attempt in range(1, 4):
        try:
            response = requests.get(API_URL, params=params, timeout=60)
            response.raise_for_status()
            result = response.json()

            if "hourly" not in result or "daily" not in result:
                raise ValueError("La respuesta no contiene datos horarios y diarios.")
            if not isinstance(result["hourly"].get("time"), list) or not result["hourly"]["time"]:
                raise ValueError("La respuesta no contiene horas válidas.")
            if not isinstance(result["daily"].get("time"), list) or not result["daily"]["time"]:
                raise ValueError("La respuesta no contiene días válidos.")

            return {
                "status": "ok",
                "model": model_name,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
                "elevation": result.get("elevation"),
                "hourly": result["hourly"],
                "daily": result["daily"],
            }

        except (requests.RequestException, ValueError) as error:
            last_error = str(error)
            print(
                f"  Intento {attempt}/3 fallido para "
                f"{model_name}: {last_error}"
            )
            if attempt < 3:
                time.sleep(5 * attempt)

    return {
        "status": "error",
        "model": model_name,
        "error": last_error,
    }


# --------------------------------------------------
# GENERACIÓN DEL ARCHIVO DE DATOS
# --------------------------------------------------

def generate_radar_data() -> dict:
    """Consulta los modelos y prepara los datos para la interfaz."""

    print("METEO RADAR SANSE")
    print("=" * 45)
    print(f"Ubicación: {LOCATION['name']}")
    print("Consultando modelos meteorológicos...\n")

    # Leemos la última publicación válida antes de consultar los modelos.
    previous_data = {}
    try:
        if OUTPUT_FILE.exists():
            previous_data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"  AVISO: no se ha podido leer la previsión anterior: {error}")

    forecasts = {}

    for short_name, model_name in MODELS.items():
        print(f"Consultando {short_name.upper()} ({model_name})...")
        forecasts[short_name] = get_model_forecast(model_name)

        if forecasts[short_name]["status"] == "ok":
            print(f"  OK: {short_name.upper()} recibido correctamente.")
        else:
            print(f"  AVISO: no se han podido obtener datos de {short_name.upper()}.")

    # Si falla un modelo, conserva su último pronóstico válido.
    previous_models = previous_data.get("models", {})
    for name, forecast in list(forecasts.items()):
        if forecast.get("status") != "error":
            continue

        previous = previous_models.get(name, {})
        previous_hourly = previous.get("hourly")
        previous_daily = previous.get("daily")

        if (
            previous.get("status") in ("ok", "stale")
            and isinstance(previous_hourly, dict)
            and isinstance(previous_hourly.get("time"), list)
            and previous_hourly["time"]
            and isinstance(previous_daily, dict)
            and isinstance(previous_daily.get("time"), list)
            and previous_daily["time"]
        ):
            forecasts[name] = {
                **previous,
                "status": "stale",
                "error": forecast.get("error"),
                "last_successful_at": (
                    previous.get("retrieved_at")
                    or previous.get("last_successful_at")
                    or previous_data.get("generated_at")
                ),
            }
            print(f"  Se conserva el último pronóstico válido de {name.upper()}.")

    available_models = [
        name for name, forecast in forecasts.items()
        if forecast.get("status") in ("ok", "stale")
        and isinstance(forecast.get("hourly"), dict)
        and isinstance(forecast["hourly"].get("time"), list)
        and bool(forecast["hourly"]["time"])
        and isinstance(forecast.get("daily"), dict)
        and isinstance(forecast["daily"].get("time"), list)
        and bool(forecast["daily"]["time"])
    ]
    fresh_models = [
        name for name, forecast in forecasts.items()
        if forecast.get("status") == "ok"
    ]
    stale_models = [
        name for name, forecast in forecasts.items()
        if forecast.get("status") == "stale"
    ]

    return {
        "project": "Meteo Radar Sanse",
        "version": "1.1",
        "location": LOCATION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": forecasts,
        "summary": {
            "models_requested": len(MODELS),
            "models_available": len(available_models),
            "available_models": available_models,
            "models_fresh": len(fresh_models),
            "models_stale": len(stale_models),
            "stale_models": stale_models,
        },
    }


# --------------------------------------------------
# EJECUCIÓN PRINCIPAL
# --------------------------------------------------

def main() -> None:
    data = generate_radar_data()

    # Si no hay ningún modelo nuevo ni datos anteriores utilizables,
    # no se toca el radar.json que está publicado.
    if data["summary"]["models_available"] == 0:
        raise RuntimeError(
            "No hay datos nuevos ni pronósticos anteriores válidos. "
            "Se conserva intacto el radar.json publicado."
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())

        # Sustitución atómica: el archivo final nunca queda escrito a medias.
        os.replace(temporary_file, OUTPUT_FILE)
    finally:
        if temporary_file.exists():
            temporary_file.unlink()

    print("\n" + "=" * 45)
    print(f"Archivo generado: {OUTPUT_FILE}")
    print(
        f"Modelos utilizables: {data['summary']['models_available']}/"
        f"{data['summary']['models_requested']}"
    )
    print(
        f"Modelos actualizados: {data['summary']['models_fresh']} · "
        f"datos anteriores conservados: {data['summary']['models_stale']}"
    )
    print("Meteo Radar Sanse: proceso terminado.")


if __name__ == "__main__":
    main()
