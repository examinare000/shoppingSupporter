from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from routers.products import SEARCH_FULL_PATH, router as products_router

app = FastAPI(title="Shopping Supporter API")
app.include_router(products_router)


@app.exception_handler(RequestValidationError)
async def _request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    # order.md: /api/products/search returns 200 + [] on any error, including
    # query parameter validation failures (e.g. limit=abc). We path-guard so
    # other endpoints retain FastAPI's default 422 behavior.
    if request.url.path == SEARCH_FULL_PATH:
        return JSONResponse(status_code=200, content=[])
    return await request_validation_exception_handler(request, exc)


@app.get("/")
def read_root():
    return {"message": "Welcome to Shopping Supporter API"}
