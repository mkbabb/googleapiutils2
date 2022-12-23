from __future__ import annotations

from typing import *

import requests
from requests.exceptions import JSONDecodeError

from ._types.geocode import *
from .utils import update_url_params


class Geocode:
    URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def _return_if_200(r: requests.Response) -> list[GeocodeResult] | None:
        if r.status_code == 200:
            try:
                return r.json()
            except JSONDecodeError:
                return None
        else:
            return None

    def geocode(self, address: str):
        url = update_url_params(Geocode.URL, {"address": address, "key": self.api_key})
        r = requests.get(url)
        return self._return_if_200(r)

    def reverse_geocode(self, lat: float, long: float):
        latlng = f"{lat},{long}"
        url = update_url_params(Geocode.URL, {"latlng": latlng, "key": self.api_key})
        r = requests.get(url)
        return self._return_if_200(r)
