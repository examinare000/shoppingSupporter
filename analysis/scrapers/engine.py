import asyncio
from playwright.async_api import async_playwright
from typing import Dict, Optional

class AmazonScraper:
    def __init__(self):
        self.base_url = "https://www.amazon.co.jp/dp/"

    async def fetch_product(self, asin: str) -> Optional[Dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # ユーザーエージェントを設定してボット検知を回避
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            })

            url = f"{self.base_url}{asin}"
            try:
                await page.goto(url, wait_until="domcontentloaded")
                
                # タイトルの取得
                title = await page.inner_text("#productTitle")
                
                # 価格の取得 (複数のパターンに対応)
                price_text = ""
                price_selectors = [
                    "span.a-price-whole",
                    "#priceblock_ourprice",
                    "#priceblock_dealprice"
                ]
                for selector in price_selectors:
                    element = await page.query_selector(selector)
                    if element:
                        price_text = await element.inner_text()
                        break
                
                # ポイントの取得
                points_text = "0"
                points_element = await page.query_selector("#loyaltyPoints_feature_div span.a-size-base")
                if points_element:
                    points_text = await points_element.inner_text()

                await browser.close()
                
                return {
                    "site": "amazon",
                    "id": asin,
                    "title": title.strip(),
                    "price": int(price_text.replace(",", "").replace("￥", "").strip()) if price_text else 0,
                    "points": points_text.strip(),
                    "url": url
                }
            except Exception as e:
                print(f"Amazon Scraping Error for {asin}: {e}")
                await browser.close()
                return None

class RakutenScraper:
    def __init__(self):
        self.base_url = "https://item.rakuten.co.jp/"

    async def fetch_product(self, shop_id: str, item_id: str) -> Optional[Dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            url = f"{self.base_url}{shop_id}/{item_id}/"
            try:
                await page.goto(url, wait_until="domcontentloaded")
                
                # タイトルの取得
                title = await page.inner_text("span.item_name")
                
                # 価格の取得
                price_element = await page.query_selector("#priceAmount")
                price_text = await price_element.get_attribute("value") if price_element else "0"
                
                await browser.close()
                
                return {
                    "site": "rakuten",
                    "id": f"{shop_id}:{item_id}",
                    "title": title.strip(),
                    "price": int(price_text),
                    "url": url
                }
            except Exception as e:
                print(f"Rakuten Scraping Error for {shop_id}/{item_id}: {e}")
                await browser.close()
                return None
