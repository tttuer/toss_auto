import json
import os
import sys
from pathlib import Path
from urllib.parse import quote


required = {"CLIENT_ID", "CLIENT_SECRET", "POSTGRES_USER", "POSTGRES_PASSWORD"}
missing = required - os.environ.keys()
if missing:
    raise SystemExit(f"Missing GitHub Secrets: {', '.join(sorted(missing))}")

user, password = os.environ["POSTGRES_USER"], os.environ["POSTGRES_PASSWORD"]
values = {
    "TOSS_CLIENT_ID": os.environ["CLIENT_ID"],
    "TOSS_CLIENT_SECRET": os.environ["CLIENT_SECRET"],
    "TOSS_ACCOUNT_SEQ": os.environ.get("TOSS_ACCOUNT_SEQ", ""),
    "POSTGRES_USER": user,
    "POSTGRES_PASSWORD": password,
    "DATABASE_URL": f"postgresql+psycopg://{quote(user)}:{quote(password)}@postgres:5432/toss_auto",
    "AUTO_RUN_ENABLED": os.environ.get("AUTO_RUN_ENABLED") or "true",
    "LIVE_TRADING": os.environ.get("LIVE_TRADING") or "true",
}

Path(sys.argv[1]).write_text(json.dumps({
    "apiVersion": "v1", "kind": "Secret",
    "metadata": {"name": "toss-auto-secrets", "namespace": "toss-auto"},
    "stringData": values,
}, indent=2), encoding="utf-8")
