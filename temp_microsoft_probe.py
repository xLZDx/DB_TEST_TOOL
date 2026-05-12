import pathlib
import requests

base = "http://127.0.0.1:8002"

lines = []
try:
    status = requests.get(f"{base}/api/microsoft/status", timeout=30)
    lines.append(f"STATUS {status.status_code}")
    lines.append(status.text)
except Exception as exc:
    lines.append(f"STATUS_ERROR {type(exc).__name__}: {exc}")

try:
    start = requests.post(f"{base}/api/microsoft/device/start", timeout=30)
    lines.append(f"START {start.status_code}")
    lines.append(start.text)
except Exception as exc:
    lines.append(f"START_ERROR {type(exc).__name__}: {exc}")

pathlib.Path("temp_microsoft_probe.out").write_text("\n".join(lines), encoding="utf-8")
