from __future__ import annotations

import time

from app.config import get_settings
from app.db import Base, engine
from app.services.runs import process_next_queued_job


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    print("[s2g-worker] polling run_jobs ...")
    while True:
        run_id = process_next_queued_job()
        if run_id:
            print(f"[s2g-worker] processed {run_id}")
        time.sleep(settings.inline_worker_poll_interval)


if __name__ == "__main__":
    main()
