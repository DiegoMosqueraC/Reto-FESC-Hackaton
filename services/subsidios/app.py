"""subsidios-app — registra retiros de afiliados (SÍ se puede modificar).

Camino nuevo: si el dominio Afiliaciones está en DUAL o MODERN, el retiro se registra
por el gateway con SUBSIDIOS_TOKEN (queda auditado y es idempotente).
Camino legacy: si Afiliaciones está en LEGACY (tras ./rollback.sh affiliations) o el
gateway no responde, se llama directamente a sp_registrar_retiro, como siempre.

POST /retiros  {"documento": "...", "fecha": "YYYY-MM-DD", "motivo": "..."}  (puerto 8091)
"""

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

import psycopg2

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8082").rstrip("/")
TOKEN = os.environ.get("SUBSIDIOS_TOKEN", "")


class GatewayDown(Exception):
    """El gateway no respondió."""


def connect():
    return psycopg2.connect(
        host=os.environ.get("LEGACY_DB_HOST", "legacy-db"),
        port=int(os.environ.get("LEGACY_DB_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "legacy"),
        user=os.environ.get("POSTGRES_USER", "legacy"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        connect_timeout=2,
    )


def registrar_retiro_legacy(documento, fecha, motivo):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sp_registrar_retiro(%s, %s, %s, %s)", (documento, fecha, motivo, "SUBSIDIOS"))
            movimiento = cur.fetchone()[0]
        conn.commit()
        return movimiento
    finally:
        conn.close()


def gateway(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        GATEWAY_URL + path,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except ValueError:
            return exc.code, {}
    except (urllib.error.URLError, OSError) as exc:
        raise GatewayDown() from exc


def modo():
    """'gateway' si Afiliaciones está en DUAL o MODERN; 'legacy' en otro caso."""
    try:
        status, body = gateway("GET", "/api/v1/migration/status")
    except GatewayDown:
        return "legacy"
    if status == 200 and (body.get("domains") or {}).get("affiliations") in ("DUAL", "MODERN"):
        return "gateway"
    return "legacy"


def request_id(documento, fecha, motivo):
    # El mismo retiro reintentado genera el mismo requestId: el gateway no lo duplica
    # (incidente 2021-07 de docs/incidentes-historicos.md).
    huella = hashlib.sha256("{0}|{1}|{2}".format(documento, fecha, motivo).encode("utf-8")).hexdigest()
    return "subsidios-" + huella[:32]


def registrar_retiro_gateway(documento, fecha, motivo):
    body = {"requestId": request_id(documento, fecha, motivo), "date": fecha, "reason": motivo}
    path = "/api/v1/members/{0}/retirements".format(quote(documento, safe=""))
    status, payload = gateway("POST", path, body)
    if status in (200, 201):
        return 201, {"movimiento": payload.get("movementId")}
    if status == 202:
        return 202, {"movimiento": None, "estado": "PENDIENTE"}
    return status, {"error": payload.get("message", "error en el gateway")}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "UP", "modo": modo()})
        return self._send(404, {"error": "ruta no encontrada"})

    def do_POST(self):
        if self.path != "/retiros":
            return self._send(404, {"error": "ruta no encontrada"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0:
                raise ValueError
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "cuerpo JSON inválido"})
        if not isinstance(data, dict):
            return self._send(400, {"error": "el cuerpo debe ser un objeto JSON"})
        documento, fecha = data.get("documento"), data.get("fecha")
        motivo = data.get("motivo", "RETIRO")
        if not isinstance(documento, str) or not documento.strip():
            return self._send(400, {"error": "documento es obligatorio"})
        if not isinstance(fecha, str):
            return self._send(400, {"error": "fecha debe tener formato YYYY-MM-DD"})
        try:
            if datetime.strptime(fecha, "%Y-%m-%d").strftime("%Y-%m-%d") != fecha:
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "fecha debe tener formato YYYY-MM-DD"})
        if not isinstance(motivo, str) or not motivo.strip():
            return self._send(400, {"error": "motivo debe ser un texto no vacío"})
        if modo() == "gateway":
            try:
                return self._send(*registrar_retiro_gateway(documento, fecha, motivo))
            except GatewayDown:
                return self._send(503, {"error": "gateway no disponible, reintente"})
        try:
            movimiento = registrar_retiro_legacy(documento, fecha, motivo)
        except psycopg2.Error as exc:
            return self._send(500, {"error": str(exc).strip()})
        return self._send(201, {"movimiento": movimiento})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8091), Handler).serve_forever()
