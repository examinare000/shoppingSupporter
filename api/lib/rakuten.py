import httpx
import os
from typing import Optional, Dict

class RakutenAPI:
    def __init__(self):
        self.application_id = os.getenv("RAKUTEN_APP_ID")
        self.base_url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"

    async def fetch_product(self, item_code: str) -> Optional[Dict]:
        if not self.application_id:
            print("Rakuten Application ID not set")
            return None

        params = {
            "applicationId": self.application_id,
            "itemCode": item_code,
            "format": "json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("Items"):
                    item = data["Items"][0]["Item"]
                    return {
                        "site": "rakuten",
                        "id": item_code,
                        "title": item["itemName"],
                        "price": item["itemPrice"],
                        "image_url": item["mediumImageUrls"][0]["imageUrl"] if item.get("mediumImageUrls") else None,
                        "url": item["itemUrl"]
                    }
            except Exception as e:
                print(f"Rakuten API Error: {e}")
        return None
