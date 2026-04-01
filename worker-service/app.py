from shared_app import create_app, start_background_metrics
import queue
import threading
import time


app = create_app("worker-service")
start_background_metrics()

job_queue = queue.Queue()


def worker_loop():
    while True:
        _job = job_queue.get()
        time.sleep(0.1)
        job_queue.task_done()


threading.Thread(target=worker_loop, daemon=True).start()


@app.get("/enqueue")
def enqueue(job: str = "default"):
    job_queue.put(job)
    return {"queued": True, "queue_size": job_queue.qsize(), "service": "worker"}


@app.get("/queue-depth")
def queue_depth():
    return {"depth": job_queue.qsize(), "service": "worker"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
