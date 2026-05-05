from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .common.database import get_db, engine
from .common.models import Base, Product, EcSiteProduct
from .cron.update_prices import update_site_product
from .routers.auth import router as auth_router
from .routers.cards import router as cards_router
from .routers.products import router as products_router
from .routers.profile import router as profile_router
import os

# Create tables if they don't exist
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="pricehack API")
# 検索系エンドポイント (/api/products/search) は router に分離。
# /api/products（全件返却）はレガシー互換のため main.py 直下に残置。
app.include_router(products_router)
app.include_router(auth_router)
app.include_router(cards_router)
app.include_router(profile_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products

@app.get("/api/cron/update-prices")
async def trigger_update_prices(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # Simple security check for Vercel Cron
    # In production, check CRON_SECRET or similar
    # if authorization != f"Bearer {os.getenv('CRON_SECRET')}":
    #    raise HTTPException(status_code=401, detail="Unauthorized")

    site_products = db.query(EcSiteProduct).all()
    for sp in site_products:
        await update_site_product(db, sp)

    return {"status": "success", "updated_count": len(site_products)}
