import httpx
import os
from typing import Optional, Dict

class YahooAPI:
    def __init__(self):
        self.client_id = os.getenv("YAHOO_CLIENT_ID")
        self.base_url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemLookup"

    async def fetch_product(self, jan_code: str) -> Optional[Dict]:
        if not self.client_id:
            print("Yahoo Client ID not set")
            return None

        headers = {
            "User-Agent": f"Yahoo AppID: {self.client_id}"
        }
        params = {
            "jan_code": jan_code,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.base_url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if data.get("hits"):
                    item = data["hits"][0]
                    return {
                        "site": "yahoo",
                        "id": item["code"],
                        "title": item["name"],
                        "price": item["price"],
                        "image_url": item["image"]["medium"] if item.get("image") else None,
                        "url": item["url"]
                    }
            except Exception as e:
                print(f"Yahoo API Error: {e}")
        return None
