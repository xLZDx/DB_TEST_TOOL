import pathlib
import requests

base = "http://127.0.0.1:8003"
lines = []

status = requests.get(f"{base}/api/microsoft/status", timeout=30)
lines.append(f"STATUS {status.status_code}")
lines.append(status.text)

probe = requests.post(
    f"{base}/api/source/test",
    json={"sources": ["https://raymondjamesprod.sharepoint.com/sites/CDSProgram"], "timeout_seconds": 20},
    timeout=60,
)
lines.append(f"TEST {probe.status_code}")
lines.append(probe.text)

pathlib.Path("temp_sharepoint_probe.out").write_text("\n".join(lines), encoding="utf-8")
