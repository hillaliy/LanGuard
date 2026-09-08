from urllib.parse import urlparse
from uuid import UUID

import requests


class HomeBoxError(ValueError):
    pass


def normalize_url(value):
    value = str(value or "").strip().rstrip("/")
    try:
        parsed = urlparse(value)
        parsed.port
    except ValueError as exc:
        raise HomeBoxError("Enter a valid HomeBox URL.") from exc
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise HomeBoxError("Enter a HomeBox HTTP or HTTPS base URL without credentials, query or fragment.")
    return value


class HomeBoxClient:
    def __init__(self, url, token):
        self.url = normalize_url(url)
        self.token = str(token or "").strip()
        if not self.token:
            raise HomeBoxError("Enter a HomeBox API key.")

    def get(self, path, params=None):
        try:
            response = requests.get(
                f"{self.url}/api/v1/{path}", params=params, timeout=10,
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise HomeBoxError(f"HomeBox returned HTTP {response.status_code}. Check the URL, API key and permissions.")
            payload = response.json()
            if not isinstance(payload, dict):
                raise HomeBoxError("HomeBox returned an unexpected response.")
            return payload
        except (requests.RequestException, ValueError) as exc:
            if isinstance(exc, HomeBoxError):
                raise
            raise HomeBoxError("Unable to read a response from HomeBox.") from exc

    def search(self, query="", page=1):
        payload = self.get("entities", {"q": query, "page": page, "pageSize": 25})
        items = payload.get("items")
        if not isinstance(items, list):
            raise HomeBoxError("HomeBox returned an unexpected item list.")
        try:
            results = [{"value": str(UUID(item["id"])), "label": str(item["name"])} for item in items]
        except (KeyError, ValueError, TypeError) as exc:
            raise HomeBoxError("HomeBox returned an invalid item.") from exc
        return {"items": results, "page": page, "has_more": len(items) == 25}

    def item(self, item_id):
        item_id = str(UUID(str(item_id)))
        payload = self.get(f"entities/{item_id}")
        if payload.get("id") != item_id or not isinstance(payload.get("name"), str):
            raise HomeBoxError("HomeBox returned an unexpected item.")
        return payload
