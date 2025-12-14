from multiprocessing import Process
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.runner import AppRunner

app = FastAPI(title="NST Tool API", version="1.0.0")

# Cho phép frontend (file tĩnh) gọi API qua localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Biến toàn cục giữ tiến trình đang chạy AppRunner
runner_process: Optional[Process] = None


class RunRequest(BaseModel):
    run_minutes: Optional[int] = None
    rest_minutes: Optional[int] = None


def _start_runner(run_minutes: Optional[int] = None, rest_minutes: Optional[int] = None) -> None:
    """Hàm wrapper để chạy vòng lặp AppRunner trong tiến trình riêng."""
    AppRunner(run_minutes=run_minutes, rest_minutes=rest_minutes).run()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/run")
def run_bot(payload: Optional[RunRequest] = Body(None)) -> dict:
    """
    Khởi động AppRunner nếu chưa chạy.
    Chạy trong process riêng để không khóa FastAPI.
    """
    global runner_process

    if runner_process and runner_process.is_alive():
        return {"status": "running", "pid": runner_process.pid}

    run_minutes = payload.run_minutes if payload else None
    rest_minutes = payload.rest_minutes if payload else None

    # Không dùng daemon vì AppRunner tự sinh thêm Process con
    runner_process = Process(
        target=_start_runner,
        args=(run_minutes, rest_minutes),
        daemon=False,
    )
    runner_process.start()

    if not runner_process.is_alive():
        raise HTTPException(status_code=500, detail="Không khởi động được bot")

    return {"status": "started", "pid": runner_process.pid}


@app.post("/stop")
def stop_bot() -> dict:
    """Dừng tiến trình AppRunner nếu đang chạy."""
    global runner_process

    if not runner_process or not runner_process.is_alive():
        return {"status": "not_running"}

    runner_process.terminate()
    runner_process.join(timeout=5)

    was_alive = runner_process.is_alive()
    runner_process = None

    if was_alive:
        raise HTTPException(status_code=500, detail="Không dừng được bot")

    return {"status": "stopped"}


@app.get("/status")
def status() -> dict:
    is_running = bool(runner_process and runner_process.is_alive())
    return {"running": is_running, "pid": runner_process.pid if is_running else None}
