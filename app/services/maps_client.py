"""
Kairos AI — Google Maps Client
Wrapper for Google Distance Matrix API.
"""
import os
import googlemaps
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_maps_client() -> googlemaps.Client:
    """Get the Google Maps client (singleton)."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not set in environment variables.")

    _client = googlemaps.Client(key=api_key)
    return _client


def get_distance_matrix(origins: list, destination: str) -> dict:
    """
    Get drive times from multiple origins to a single destination.
    
    Args:
        origins: List of "lat,lng" strings
        destination: Single "lat,lng" string
        
    Returns:
        dict with drive times in seconds per origin
    """
    client = get_maps_client()

    result = client.distance_matrix(
        origins=origins,
        destinations=[destination],
        mode="driving",
        departure_time="now"
    )

    drive_times = {}
    for i, row in enumerate(result["rows"]):
        element = row["elements"][0]
        if element["status"] == "OK":
            # Prefer duration_in_traffic if available
            if "duration_in_traffic" in element:
                seconds = element["duration_in_traffic"]["value"]
            else:
                seconds = element["duration"]["value"]
            drive_times[i] = {
                "duration_seconds": seconds,
                "duration_text": element.get("duration_in_traffic", element["duration"])["text"],
                "distance_text": element["distance"]["text"],
                "distance_meters": element["distance"]["value"]
            }
        else:
            drive_times[i] = None

    return drive_times


def get_single_eta(origin_lat: float, origin_lng: float,
                   dest_lat: float, dest_lng: float) -> float:
    """
    Get ETA in minutes from a single origin to a single destination.
    """
    result = get_distance_matrix(
        origins=[f"{origin_lat},{origin_lng}"],
        destination=f"{dest_lat},{dest_lng}"
    )

    if result.get(0):
        return round(result[0]["duration_seconds"] / 60, 1)
    return -1.0
