"""Registro de retiros: idempotente por requestId y tolerante a la caída del legacy.

- requestId nuevo y legacy arriba  -> se aplica en el legacy  -> 201
- requestId ya aplicado            -> mismo resultado, sin duplicar -> 200
- legacy caído                     -> queda en cola (PENDING) -> 202
Un worker aplica la cola cuando el legacy vuelve, una sola vez por requestId.
"""

import threading
import time

from adapter import legacy_repository as legacy
from app import store

_lock = threading.Lock()  # serializa la secuencia consultar -> aplicar -> marcar
RETRY_SECONDS = 2


class Conflict(Exception):
    """El requestId ya se usó para otro afiliado."""


def _body(row):
    return {
        "requestId": row["request_id"],
        "document": row["document"],
        "date": row["date"],
        "status": row["state"],
        "movementId": row.get("movement_id"),
    }


def _apply(row):
    """Aplica un retiro PENDING en el legacy. Devuelve la fila actualizada."""
    movement_id = legacy.register_retirement(row["document"], row["date"], row["reason"], row["consumer"])
    store.mark(row["request_id"], store.APPLIED, movement_id)
    return store.get(row["request_id"])


def register(document, request, consumer):
    """Devuelve (status_code, body). Lanza legacy.NotFound o Conflict."""
    with _lock:
        existing = store.get(request.requestId)
        if existing:
            if existing["document"] != document:
                raise Conflict()
            if existing["state"] == store.FAILED:
                raise legacy.NotFound()
            code = 200 if existing["state"] == store.APPLIED else 202
            return code, _body(existing)

        store.add_pending(request.requestId, document, request.date.isoformat(), request.reason, consumer)
        row = store.get(request.requestId)
        try:
            return 201, _body(_apply(row))
        except legacy.LegacyUnavailable:
            return 202, _body(row)
        except legacy.NotFound:
            store.delete(request.requestId)
            raise


def process_pending():
    """Aplica los retiros en cola. Se detiene en cuanto el legacy sigue caído."""
    rows = store.pending()
    # Sin el lock: así una caída no hace esperar a las peticiones que repiten un requestId.
    if not rows or not legacy.ping():
        return
    for row in rows:
        with _lock:
            current = store.get(row["request_id"])
            if not current or current["state"] != store.PENDING:
                continue
            try:
                _apply(current)
            except legacy.LegacyUnavailable:
                return
            except legacy.NotFound:
                store.mark(current["request_id"], store.FAILED)


def _worker():
    while True:
        try:
            process_pending()
        except Exception:
            pass  # el worker nunca debe morir; se reintenta en el siguiente ciclo
        time.sleep(RETRY_SECONDS)


def start_worker():
    threading.Thread(target=_worker, name="retirements-worker", daemon=True).start()
