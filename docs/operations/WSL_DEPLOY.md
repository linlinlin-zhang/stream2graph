# WSL Deployment

This repository can run directly inside WSL without Node or Docker.

## 1. Bootstrap

```bash
cd /mnt/e/Desktop/stream2graph
bash tools/ops/wsl_bootstrap.sh
```

## 2. Start the realtime UI

```bash
cd /mnt/e/Desktop/stream2graph
bash tools/ops/wsl_start_realtime_ui.sh 127.0.0.1 8088
```

Health check:

```bash
curl http://127.0.0.1:8088/api/health
```

## 3. Stop the service

```bash
cd /mnt/e/Desktop/stream2graph
bash tools/ops/wsl_stop_realtime_ui.sh 8088
```

## Notes

- The main runnable app is `tools/realtime_frontend_server.py`.
- The browser UI is served from `frontend/realtime_ui/`.
- Runtime logs and pid files are written to `reports/runtime/`.
- Python dependencies for this path are defined in `requirements/wsl.txt`.
- Dataset and algorithm scripts remain in `versions/` and `tools/`.
