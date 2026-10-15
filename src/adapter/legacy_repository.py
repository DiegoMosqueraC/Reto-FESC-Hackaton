"""Adapter de la base legacy.

Es el único módulo que conoce tablas, columnas, códigos y procedimientos heredados.
Traduce el esquema legacy al modelo canónico (diccionarios con nombres del contrato).
Soporta el esquema original (afi_mae / nro_doc / est_afi) y el posterior al cambio del
DBA (person_master / document_number / status_code): lo detecta en cada conexión.
"""

import os
import socket
import threading

import psycopg2

STATUS = {"A": "ACTIVE", "R": "RETIRED", "S": "SUSPENDED"}
RELATIONSHIP = {"C": "SPOUSE", "H": "CHILD", "P": "FATHER", "M": "MOTHER"}

SCHEMA_ORIGINAL = {"table": "afi_mae", "document": "nro_doc", "status": "est_afi"}
SCHEMA_RENAMED = {"table": "person_master", "document": "document_number", "status": "status_code"}


class LegacyUnavailable(Exception):
    """La base legacy no responde."""


class NotFound(Exception):
    """El recurso no existe en la base legacy."""


def _settings():
    return {
        "host": os.environ.get("LEGACY_DB_HOST", "legacy-db"),
        "port": int(os.environ.get("LEGACY_DB_PORT", "5432")),
        "dbname": os.environ.get("POSTGRES_DB", "legacy"),
        "user": os.environ.get("POSTGRES_USER", "legacy"),
        "password": os.environ.get("POSTGRES_PASSWORD", ""),
    }


def _resolve(host, port, timeout=0.7):
    """Resuelve el nombre con tiempo límite: con el contenedor detenido el DNS tarda ~4 s."""
    result = {}

    def lookup():
        try:
            result["ip"] = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        except OSError:
            pass

    worker = threading.Thread(target=lookup, daemon=True)
    worker.start()
    worker.join(timeout)
    return result.get("ip")


def _reachable(ip, port, timeout=0.7):
    # libpq no acepta connect_timeout menor a 2 s; este chequeo previo falla rápido.
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _connect():
    cfg = _settings()
    ip = _resolve(cfg["host"], cfg["port"])
    if ip is None or not _reachable(ip, cfg["port"]):
        raise LegacyUnavailable()
    try:
        conn = psycopg2.connect(hostaddr=ip, connect_timeout=2, options="-c statement_timeout=2000", **cfg)
    except psycopg2.Error as exc:
        raise LegacyUnavailable() from exc
    return conn


def _schema(cur):
    cur.execute("SELECT to_regclass('public.person_master') IS NOT NULL")
    return SCHEMA_RENAMED if cur.fetchone()[0] else SCHEMA_ORIGINAL


def _full_name(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())


def _run(work):
    """Abre una conexión, ejecuta work(cur, schema) y traduce los errores de la base."""
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                return work(cur, _schema(cur))
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
        raise LegacyUnavailable() from exc
    finally:
        conn.close()


def ping():
    try:
        _run(lambda cur, schema: cur.execute("SELECT 1"))
        return True
    except LegacyUnavailable:
        return False


def get_member(document):
    def work(cur, s):
        cur.execute(
            "SELECT a.{document}, a.nom1, a.nom2, a.ape1, a.ape2, a.{status}, e.cod_emp, e.nom_emp "
            "FROM {table} a LEFT JOIN empresa e ON e.cod_emp = a.cod_emp "
            "WHERE a.{document} = %s".format(**s),
            (document,),
        )
        row = cur.fetchone()
        if row is None:
            raise NotFound()
        company = {"id": row[6], "name": row[7]} if row[6] else None
        return {
            "document": row[0],
            "fullName": _full_name(*row[1:5]),
            "status": STATUS.get(row[5], row[5]),
            "company": company,
        }

    return _run(work)


def get_beneficiaries(document):
    def work(cur, s):
        cur.execute("SELECT 1 FROM {table} WHERE {document} = %s".format(**s), (document,))
        if cur.fetchone() is None:
            raise NotFound()
        cur.execute(
            "SELECT nro_doc_ben, nom1, nom2, ape1, ape2, cod_par FROM afi_ben "
            "WHERE nro_doc = %s ORDER BY nro_doc_ben",
            (document,),
        )
        return [
            {"document": r[0], "fullName": _full_name(*r[1:5]), "relationship": RELATIONSHIP.get(r[5], r[5])}
            for r in cur.fetchall()
        ]

    return _run(work)


def get_company(company_id):
    def work(cur, s):
        cur.execute("SELECT cod_emp, nom_emp FROM empresa WHERE cod_emp = %s", (company_id,))
        row = cur.fetchone()
        if row is None:
            raise NotFound()
        cur.execute(
            "SELECT count(*) FROM {table} WHERE cod_emp = %s AND {status} = 'A'".format(**s),
            (company_id,),
        )
        return {"id": row[0], "name": row[1], "activeMembers": int(cur.fetchone()[0])}

    return _run(work)


def register_retirement(document, date, reason, consumer):
    """Registra el retiro con el procedimiento legacy y devuelve el id del movimiento."""

    def work(cur, s):
        cur.execute("SELECT 1 FROM {table} WHERE {document} = %s".format(**s), (document,))
        if cur.fetchone() is None:
            raise NotFound()
        cur.execute("SELECT sp_registrar_retiro(%s, %s, %s, %s)", (document, date, reason, consumer.upper()))
        return cur.fetchone()[0]

    return _run(work)
