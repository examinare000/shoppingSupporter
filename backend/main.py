from fastapi import FastAPI

app = FastAPI(title="Shopping Supporter API")

@app.get("/")
def read_root():
    return {"message": "Welcome to Shopping Supporter API"}
