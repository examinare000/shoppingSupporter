import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from ..common.database import SessionLocal
from ..common.models import Product, EcSiteProduct, PriceHistory, SiteType
from ..lib.amazon import AmazonAPI
from ..lib.rakuten import RakutenAPI
from ..lib.yahoo import YahooAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def update_site_product(db: Session, site_product: EcSiteProduct):
    """個別のサイト商品の価格を更新する"""
    result = None
    
    if site_product.site_type == SiteType.AMAZON:
        api = AmazonAPI()
        result = await api.fetch_product(site_product.site_product_id)
    elif site_product.site_type == SiteType.RAKUTEN:
        api = RakutenAPI()
        result = await api.fetch_product(site_product.site_product_id)
    elif site_product.site_type == SiteType.YAHOO:
        api = YahooAPI()
        # YahooはJANコードで検索することが多いが、ここでは site_product_id を使用
        result = await api.fetch_product(site_product.site_product_id)

    if result:
        # PriceHistoryの追加
        price_history = PriceHistory(
            ec_site_product_id=site_product.id,
            price=result["price"],
            points=result.get("points", 0),
            recorded_at=datetime.utcnow()
        )
        db.add(price_history)
        
        # 最終更新日時とURL等の情報を更新
        site_product.last_updated = datetime.utcnow()
        if result.get("url"):
            site_product.url = result["url"]
            
        db.commit()
        logger.info(f"Updated {site_product.site_type.value} product: {site_product.site_product_id} - Price: {result['price']}")
    else:
        logger.warning(f"Failed to update {site_product.site_type.value} product: {site_product.site_product_id}")

async def main():
    logger.info("Starting price update cron job.")
    db = SessionLocal()
    try:
        # 更新が必要な商品を全て取得 (簡略化のため全件)
        site_products = db.query(EcSiteProduct).all()
        for sp in site_products:
            await update_site_product(db, sp)
    except Exception as e:
        logger.error(f"Error in cron job: {e}")
    finally:
        db.close()
    logger.info("Cron job finished.")

if __name__ == "__main__":
    asyncio.run(main())
