from __future__ import annotations

from typing import *

import requests

from ..utils import update_url_params
from .misc import GeocodeResult


class GeocodeError(Exception):
    pass


class GeocodeInvalidRequestError(GeocodeError):
    pass


class GeocodeOverQueryLimitError(GeocodeError):
    pass


class GeocodeRequestDeniedError(GeocodeError):
    pass


class GeocodeNotFoundError(GeocodeError):
    pass


class GeocodeUnknownError(GeocodeError):
    pass


class Geocode:
    URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _raise_error(self, status: str):
        if status == "INVALID_REQUEST":
            raise GeocodeInvalidRequestError("The request was invalid.")
        elif status == "OVER_QUERY_LIMIT":
            raise GeocodeOverQueryLimitError("You are over your query limit.")
        elif status == "REQUEST_DENIED":
            raise GeocodeRequestDeniedError("Your request was denied.")
        elif status == "NOT_FOUND":
            raise GeocodeNotFoundError("The requested resource was not found.")
        elif status == "UNKNOWN_ERROR":
            raise GeocodeUnknownError("An unknown error occurred.")
        else:
            raise GeocodeError("An unexpected error occurred.")

    def _decode_json(self, r: requests.Response) -> list[GeocodeResult]:
        data = r.json()
        status = data.get("status")

        if status != "OK":
            self._raise_error(status)

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
