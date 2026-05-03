from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .common.database import get_db, engine
from .common.models import Base, Product, EcSiteProduct
from .cron.update_prices import update_site_product
import os

# Create tables if they don't exist
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shopping Supporter API")

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
