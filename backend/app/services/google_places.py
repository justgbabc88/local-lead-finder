"""Google Places API (v1) client.

Handles Text Search (with pagination up to 3 pages) and Place Details.
Returns normalized dicts that the scraper service upserts into Supabase.
"""
from typing import Any, Optional
import httpx

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

TEXT_SEARCH_FIELDMASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.primaryType,places.types,"
    "places.businessStatus,places.nationalPhoneNumber,places.websiteUri,"
    "places.googleMapsUri,nextPageToken"
)

PLACE_DETAILS_FIELDMASK = (
    "id,displayName,formattedAddress,addressComponents,location,"
    "nationalPhoneNumber,internationalPhoneNumber,websiteUri,googleMapsUri,"
    "regularOpeningHours,priceLevel,businessStatus,primaryType,types,"
    "rating,userRatingCount"
)


class GooglePlacesError(Exception):
    pass


class GooglePlacesClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise GooglePlacesError("Missing Google Places API key")
        self.api_key = api_key

    async def text_search(
        self,
        query: str,
        lat: float,
        lng: float,
        radius_meters: int,
        *,
        min_rating: Optional[float] = None,
        max_pages: int = 3,
    ) -> tuple[list[dict[str, Any]], int]:
        """Run a text search around (lat,lng). Returns (places, api_call_count)."""
        results: list[dict[str, Any]] = []
        page_token: Optional[str] = None
        calls = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for _ in range(max_pages):
                body: dict[str, Any] = {
                    "textQuery": query,
                    "locationBias": {
                        "circle": {
                            "center": {"latitude": lat, "longitude": lng},
                            "radius": radius_meters,
                        }
                    },
                    "pageSize": 20,
                }
                if min_rating is not None:
                    body["minRating"] = min_rating
                if page_token:
                    body["pageToken"] = page_token

                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": TEXT_SEARCH_FIELDMASK,
                }

                resp = await client.post(TEXT_SEARCH_URL, json=body, headers=headers)
                calls += 1
                if resp.status_code == 429:
                    raise GooglePlacesError("rate_limited")
                if resp.status_code != 200:
                    raise GooglePlacesError(f"Text search {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                places = data.get("places") or []
                results.extend(places)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        return results, calls

    async def place_details(self, place_id: str) -> tuple[dict[str, Any], int]:
        url = PLACE_DETAILS_URL.format(place_id=place_id)
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": PLACE_DETAILS_FIELDMASK,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 429:
                raise GooglePlacesError("rate_limited")
            if resp.status_code != 200:
                raise GooglePlacesError(f"Place details {resp.status_code}: {resp.text[:200]}")
            return resp.json(), 1


# ---------- Normalizers (Places v1 response shape → our companies columns) ----------

def _addr_component(components: list[dict], type_name: str, short: bool = False) -> Optional[str]:
    for c in components or []:
        if type_name in (c.get("types") or []):
            return c.get("shortText" if short else "longText")
    return None


def normalize_place(place: dict[str, Any]) -> dict[str, Any]:
    """Map a Places v1 place object onto our companies columns.

    Tolerates missing fields since Text Search returns fewer fields than Place Details.
    """
    display_name = (place.get("displayName") or {}).get("text")
    location = place.get("location") or {}
    components = place.get("addressComponents") or []

    return {
        "place_id": place.get("id"),
        "name": display_name,
        "address": place.get("formattedAddress"),
        "city": _addr_component(components, "locality")
                or _addr_component(components, "postal_town"),
        "state": _addr_component(components, "administrative_area_level_1", short=True),
        "zip": _addr_component(components, "postal_code"),
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
        "phone": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "google_maps_url": place.get("googleMapsUri"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "primary_category": place.get("primaryType"),
        "categories": place.get("types"),
        "hours": place.get("regularOpeningHours"),
        "price_level": place.get("priceLevel"),
        "business_status": place.get("businessStatus") or "OPERATIONAL",
    }
