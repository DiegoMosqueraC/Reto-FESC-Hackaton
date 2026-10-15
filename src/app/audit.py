"""Auditoría: una línea JSON por petición en logs/audit.log, con documentos enmascarados."""

import json
import os
import re
import threading
from datetime import datetime, timezone

AUDIT_LOG = os.environ.get("AUDIT_LOG", "/app/logs/audit.log")
_lock = threading.Lock()
_DIGITS = re.compile(r"\d{5,}")


def mask(text):
    """Deja visibles solo los últimos 4 dígitos de cada número largo (documentos)."""
    return _DIGITS.sub(lambda m: "*" * (len(m.group()) - 4) + m.group()[-4:], text)


def record(consumer, method, path, status, latency_ms):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "consumer": consumer or "anonymous",
        "endpoint": "{0} {1}".format(method, mask(path)),
        "status": status,
        "latency_ms": round(latency_ms, 1),
    }
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
