from __future__ import annotations

from enum import Enum
from typing import *


class LocationType(Enum):
    """The location type of a geocode."""

    # Represents a precise geocode.
    ROOFTOP = "ROOFTOP"
    # Represents an interpolated geocode.
    RANGE_INTERPOLATED = "RANGE_INTERPOLATED"
    # Represents the geometric center of a result such as a polyline (for example, a street) or polygon (region).
    GEOMETRIC_CENTER = "GEOMETRIC_CENTER"
    # Represents a result that is approximate.
    APPROXIMATE = "APPROXIMATE"


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
    location_type: Literal[
        LocationType.ROOFTOP,
        LocationType.RANGE_INTERPOLATED,
        LocationType.GEOMETRIC_CENTER,
        LocationType.APPROXIMATE,
    ]
    viewport: ViewPort


class GeocodeResult(TypedDict):
    address_components: list[AddressComponents]
    formatted_address: str
    geometry: Geometry
    place_id: str
    types: list[str]
