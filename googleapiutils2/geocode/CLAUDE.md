# geocode/

Google Maps Geocoding API wrapper: address ↔ coordinates conversion.

## File Tree

```
geocode/
├── __init__.py          # Exports Geocode
├── geocode.py           # Geocode class (geocoding operations)
└── misc.py              # TypedDicts, LocationType enum
```

## Key Classes

### Geocode (geocode.py)
**Does NOT inherit DriveBase** - standalone implementation.

**Methods:**
- `__init__(api_key)` - Initialize with API key
- `geocode(address)` - Address → coordinates
- `reverse_geocode(lat, long)` - Coordinates → address
- `_decode_json(response)` - Parse response

**Features:**
- Direct REST API via `requests`
- API key authentication (not OAuth2)
- No caching, throttling, or retry (unlike other modules)
- TypedDict responses

### LocationType (misc.py)
Enum for geocode precision levels.

**Values:**
- `ROOFTOP` - Precise geocode
- `RANGE_INTERPOLATED` - Interpolated from range
- `GEOMETRIC_CENTER` - Center of polyline/polygon
- `APPROXIMATE` - Approximate result

## TypedDicts (misc.py)

### GeocodeResult
Top-level response structure.

**Fields:**
- `formatted_address: str` - Human-readable address
- `address_components: list[AddressComponents]` - Parsed address parts
- `geometry: Geometry` - Location data
- `place_id: str` - Unique identifier
- `types: list[str]` - Result types

### Geometry
Location and viewport data.

**Fields:**
- `location: Location` - Coordinates
- `location_type: str` - Precision level
- `viewport: ViewPort` - Bounding box

### Location
Coordinates.

**Fields:**
- `lat: float` - Latitude
- `lng: float` - Longitude

### ViewPort
Bounding box.

**Fields:**
- `northeast: Location`
- `southwest: Location`

### AddressComponents
Parsed address parts.

**Fields:**
- `long_name: str` - Full name
- `short_name: str` - Abbreviated name
- `types: list[str]` - Component types

## Constants

### API
- `URL = "https://maps.googleapis.com/maps/api/geocode/json"` - Geocoding endpoint

## Usage Examples

### Forward Geocoding
```python
from googleapiutils2 import Geocode

geocoder = Geocode(api_key="YOUR_API_KEY")

# Address to coordinates
results = geocoder.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
result = results[0]

print(result['formatted_address'])
# "Google Building 40, 1600 Amphitheatre Pkwy, Mountain View, CA 94043, USA"

location = result['geometry']['location']
print(f"Lat: {location['lat']}, Lng: {location['lng']}")
# Lat: 37.4224764, Lng: -122.0842499

print(result['geometry']['location_type'])
# "ROOFTOP"

print(result['place_id'])
# "ChIJ2eUgeAK6j4ARbn5u_wAGqWA"
```

### Reverse Geocoding
```python
# Coordinates to address
results = geocoder.reverse_geocode(lat=37.4224764, long=-122.0842499)
result = results[0]

print(result['formatted_address'])
# "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA"
```

### Address Components
```python
results = geocoder.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
components = results[0]['address_components']

for comp in components:
    if 'postal_code' in comp['types']:
        print(f"ZIP: {comp['long_name']}")  # ZIP: 94043
    if 'locality' in comp['types']:
        print(f"City: {comp['long_name']}")  # City: Mountain View
```

### Error Handling
```python
from googleapiutils2 import GoogleAPIException

try:
    results = geocoder.geocode("invalid address that doesn't exist")
except GoogleAPIException as e:
    print(f"Geocoding failed: {e}")
```

## Patterns

### API Key Authentication
```python
# No OAuth2, just API key
geocoder = Geocode(api_key="YOUR_API_KEY")
```

**Get API key:** https://console.cloud.google.com/apis/credentials

### Direct HTTP Requests
```python
# Uses requests library, not googleapiclient
import requests
response = requests.get(url, params={...})
```

### Response Structure
```python
# API returns list of results (best match first)
results = geocoder.geocode(address)
best_match = results[0]

# Multiple results possible
for result in results:
    print(result['formatted_address'])
```

## Dependencies

**External:**
- `requests` - HTTP client

**Internal:**
- `googleapiutils2.utils.raise_for_status` - Error handling
- `googleapiutils2.utils.update_url_params` - URL construction

**Standard library:**
- `enum.Enum` - LocationType
- `typing.TypedDict` - Response types

## Public API

**Exported from `__init__.py`:**
- `Geocode`

## Notes

### Architectural Differences
Unlike other modules:
- **Does NOT inherit DriveBase**
- No caching
- No throttling
- No retry logic
- Uses `requests` not `googleapiclient`
- API key auth not OAuth2

### Response Format
Google Maps Geocoding API returns JSON:
```json
{
  "results": [
    {
      "formatted_address": "...",
      "address_components": [...],
      "geometry": {
        "location": {"lat": 37.422, "lng": -122.084},
        "location_type": "ROOFTOP",
        "viewport": {...}
      },
      "place_id": "...",
      "types": ["street_address"]
    }
  ],
  "status": "OK"
}
```

### Status Codes
- `OK` - Success
- `ZERO_RESULTS` - No results found
- `OVER_QUERY_LIMIT` - Quota exceeded
- `REQUEST_DENIED` - Invalid API key
- `INVALID_REQUEST` - Missing parameters
- `UNKNOWN_ERROR` - Server error

### Quotas
Free tier: 40,000 requests/month
See: https://developers.google.com/maps/documentation/geocoding/usage-and-billing

### Component Types
Common address component types:
- `street_number`, `route`, `locality`, `administrative_area_level_1`, `country`, `postal_code`

### Location Types
Precision from highest to lowest:
1. `ROOFTOP` - Exact location
2. `RANGE_INTERPOLATED` - Approximate (interpolated)
3. `GEOMETRIC_CENTER` - Center of area
4. `APPROXIMATE` - Approximate location

### Testing
Integration test: `test/geocode/test_geocode.py`
```python
result = geocoder.geocode(address)[0]
assert result["geometry"]["location_type"] == "ROOFTOP"
```
