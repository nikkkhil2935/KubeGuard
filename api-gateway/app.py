from shared_app import create_app, start_background_metrics
import httpx
import os


CORE_URL = os.environ.get("CORE_SERVICE_URL", "http://core-service:8001")
WORKER_URL = os.environ.get("WORKER_SERVICE_URL", "http://worker-service:8002")

app = create_app("api-gateway")
start_background_metrics()


@app.get("/api/process")
async def process(payload: str = "demo"):
    async with httpx.AsyncClient(timeout=5.0) as client:
        core_res = await client.get(f"{CORE_URL}/process", params={"payload": payload})
        worker_res = await client.get(f"{WORKER_URL}/enqueue", params={"job": payload})
    return {"gateway": "ok", "core": core_res.json(), "worker": worker_res.json()}


@app.get("/api/health-all")
async def health_all():
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in [("core", CORE_URL), ("worker", WORKER_URL)]:
            try:
                r = await client.get(f"{url}/health")
                results[name] = r.json()
            except Exception as e:
                results[name] = {"status": "unreachable", "error": str(e)}
    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
