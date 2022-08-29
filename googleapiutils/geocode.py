from __future__ import annotations

from typing import *

import requests

from .types.geocode import *
from .utils import update_url_params

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        SheetsResource,
        UpdateValuesResponse,
        ValueRange,
    )


class Geocode:
    URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def geocode(self, address: str) -> list[GeocodeResult]:
        url = update_url_params(Geocode.URL, {"address": address, "key": self.api_key})
        r = requests.get(url)
        return r.json()

    def reverse_geocode(self, lat: float, long: float) -> list[GeocodeResult]:
        latlng = f"{lat},{long}"
        url = update_url_params(Geocode.URL, {"latlng": latlng, "key": self.api_key})
        r = requests.get(url)
        return r.json()
