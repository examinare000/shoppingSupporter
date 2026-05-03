import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Product, EcSiteProduct, PriceHistory, SiteType
from scrapers.engine import AmazonScraper, RakutenScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def save_scrape_result(db: Session, result: dict, jan_code: str = None):
    """スクレイピング結果をDBに保存または更新する"""
    if not result:
        return

    # 1. Productの取得または作成
    # JANコードがある場合はJANで、ない場合は名前で簡易検索（本来はJANが望ましい）
    product = None
    if jan_code:
        product = db.query(Product).filter(Product.jan_code == jan_code).first()
    
    if not product:
        product = Product(
            name=result["title"],
            jan_code=jan_code,
            image_url=result.get("image_url")
        )
        db.add(product)
        db.flush() # ID確定のため

    # 2. EcSiteProductの取得または作成
    site_type = SiteType[result["site"].upper()]
    site_product = db.query(EcSiteProduct).filter(
        EcSiteProduct.product_id == product.id,
        EcSiteProduct.site_type == site_type,
        EcSiteProduct.site_product_id == result["id"]
    ).first()

    if not site_product:
        site_product = EcSiteProduct(
            product_id=product.id,
            site_type=site_type,
            site_product_id=result["id"],
            url=result["url"]
        )
        db.add(site_product)
        db.flush()

    # 3. PriceHistoryの追加
    # ポイント情報のパース (簡易版)
    points = 0
    if isinstance(result.get("points"), str):
        # "100pt" などの文字列から数値を抽出
        import re
        match = re.search(r'(\d+)', result["points"].replace(",", ""))
        if match:
            points = int(match.group(1))
    elif isinstance(result.get("points"), int):
        points = result["points"]

    price_history = PriceHistory(
        ec_site_product_id=site_product.id,
        price=result["price"],
        points=points,
        recorded_at=datetime.utcnow()
    )
    db.add(price_history)
    
    # 最終更新日時を更新
    site_product.last_updated = datetime.utcnow()
    
    db.commit()
    logger.info(f"Saved {result['site']} product: {result['title']} - Price: {result['price']}")

async def main():
    logger.info("Analysis service worker started.")
    amazon = AmazonScraper()
    
    # テスト用のデータ (任天堂スイッチのASIN)
    test_asin = "B098BJLFWV"
    
    while True:
        db = SessionLocal()
        try:
            logger.info(f"Starting scheduled scrape for ASIN: {test_asin}")
            result = await amazon.fetch_product(test_asin)
            if result:
                await save_scrape_result(db, result)
            else:
                logger.warning(f"Failed to fetch data for {test_asin}")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            db.close()
        
        # 1時間ごとに実行
        logger.info("Waiting for next crawl...")
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
