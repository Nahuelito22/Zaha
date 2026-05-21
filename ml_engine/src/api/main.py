from fastapi import FastAPI

app = FastAPI(title="Zaha ML Engine API")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Zaha ML Engine is running"}
