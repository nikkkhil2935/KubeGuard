from shared_app import create_app, start_background_metrics
import hashlib
import time


app = create_app("core-service")
start_background_metrics()


@app.get("/process")
def process(payload: str = "data"):
    result = hashlib.sha256(f"{payload}{time.time()}".encode()).hexdigest()
    time.sleep(0.05)
    return {"processed": True, "hash": result[:16], "service": "core"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
