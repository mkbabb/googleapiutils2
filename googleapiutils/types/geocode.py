from __future__ import annotations

from typing import *

LocationType = Literal[
    "ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER", "APPROXIMATE"
]


class AddressComponents(TypedDict):
    long_name: str
    short_name: str
    types: list[str]


class Location(TypedDict):
    lat: float
    lng: float


class ViewPort(TypedDict):
    northeast: Location
    southwest: Location


class Geometry(TypedDict):
    location: Location
    location_type: LocationType
    viewport: ViewPort


class GeocodeResult(TypedDict):
    address_components: list[AddressComponents]
    formatted_address: str
    geometry: Geometry
    place_id: str
    types: list[str]
