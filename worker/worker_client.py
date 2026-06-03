#!/usr/bin/env python3
"""Domestic worker client that pulls tasks from the public Singapore API.

The worker never accepts inbound public traffic and never connects to MySQL. It
polls HTTPS endpoints with X-Worker-Token, executes the local automation hook,
and reports a sanitized result back to the API server.
"""
from __future__ import annotations

import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "worker.log"

logger = logging.getLogger("koko_worker")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)


def _mask(value: Any, keep: int = 4) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return f"***{text[-keep:]}"


def _config() -> dict[str, Any]:
    base_url = os.getenv("PUBLIC_API_BASE_URL", "").rstrip("/")
    token = os.getenv("WORKER_API_TOKEN", "")
    worker_id = os.getenv("WORKER_ID", "worker-cn-01")
    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", "3"))
    if not base_url:
        raise RuntimeError("PUBLIC_API_BASE_URL is required")
    if not token:
        raise RuntimeError("WORKER_API_TOKEN is required")
    return {
        "base_url": base_url,
        "token": token,
        "worker_id": worker_id,
        "poll_interval": poll_interval,
    }


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Worker-Token": cfg["token"],
        "X-Worker-Id": cfg["worker_id"],
    }


def fetch_task(session: requests.Session, cfg: dict[str, Any]) -> dict[str, Any] | None:
    response = session.post(
        f"{cfg['base_url']}/api/worker/fetch",
        headers=_headers(cfg),
        json={"worker_id": cfg["worker_id"]},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("message") or "fetch failed")
    return payload.get("task")


def report_task(session: requests.Session, cfg: dict[str, Any], payload: dict[str, Any]) -> None:
    safe_payload = dict(payload)
    safe_payload["worker_id"] = cfg["worker_id"]
    response = session.post(
        f"{cfg['base_url']}/api/worker/report",
        headers=_headers(cfg),
        json=safe_payload,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("success"):
        raise RuntimeError(result.get("message") or "report failed")


def execute_task(task: dict[str, Any]) -> dict[str, Any]:
    """Hook for Selenium/Chrome recharge automation on the domestic worker.

    Replace the TODO section with the existing recharge flow. Keep secrets in
    environment variables and avoid logging full phone numbers or redeem codes.
    The returned dict is sent to /api/worker/report.
    """
    task_id = task.get("task_id") or task.get("record_id")
    logger.info(
        "received task_id=%s phone_tail=%s redeem_tail=%s",
        task_id,
        _mask(task.get("phone")),
        _mask(task.get("redeem_code") or task.get("order_id"), keep=6),
    )

    # TODO: Call the existing Selenium/Chrome recharge implementation here.
    # The hook should return success/failed/running plus optional r_status,
    # c_status, details, userid, tel_data_id, and screenshot/image URL.
    return {
        "task_id": task_id,
        "status": "failed",
        "r_status": "failed",
        "c_status": "failed",
        "error_message": "worker automation hook is not implemented yet",
    }


def run_forever() -> None:
    cfg = _config()
    logger.info(
        "worker starting worker_id=%s api=%s interval=%s",
        cfg["worker_id"],
        cfg["base_url"],
        cfg["poll_interval"],
    )
    session = requests.Session()
    while True:
        try:
            task = fetch_task(session, cfg)
            if not task:
                time.sleep(cfg["poll_interval"])
                continue
            task_id = task.get("task_id") or task.get("record_id")
            try:
                result = execute_task(task)
            except Exception as exc:
                logger.exception("task failed before report task_id=%s", task_id)
                result = {
                    "task_id": task_id,
                    "status": "failed",
                    "r_status": "failed",
                    "c_status": "failed",
                    "error_message": str(exc)[:500],
                }
            report_task(session, cfg, result)
            logger.info("reported task_id=%s status=%s", task_id, result.get("status"))
        except Exception as exc:
            logger.warning("poll loop error: %s", str(exc)[:300])
            time.sleep(cfg["poll_interval"])


if __name__ == "__main__":
    run_forever()
