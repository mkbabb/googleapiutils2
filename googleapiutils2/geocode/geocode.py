from __future__ import annotations

import requests

from googleapiutils2.geocode.misc import GeocodeResult
from googleapiutils2.utils import raise_for_status, update_url_params


class Geocode:
    URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _decode_json(self, r: requests.Response) -> list[GeocodeResult]:
        data = r.json()

        status = data.get("status")

        raise_for_status(status)

        return data.get("results", None)

    def geocode(self, address: str) -> list[GeocodeResult]:
        url = update_url_params(Geocode.URL, {"address": address, "key": self.api_key})
        r = requests.get(url)

        return self._decode_json(r)

    def reverse_geocode(self, lat: float, long: float) -> list[GeocodeResult]:
        latlng = f"{lat},{long}"
        url = update_url_params(Geocode.URL, {"latlng": latlng, "key": self.api_key})
        r = requests.get(url)

        return self._decode_json(r)
