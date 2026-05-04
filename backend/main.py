from fastapi import FastAPI

from routers.products import router as products_router

app = FastAPI(title="Shopping Supporter API")
app.include_router(products_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Shopping Supporter API"}
