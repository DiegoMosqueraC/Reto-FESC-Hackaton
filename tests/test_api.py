"""Pruebas de la API del gateway en funcionamiento.

No modifican datos de afiliados reales: los retiros se prueban con un documento
inexistente y con el permiso de solo lectura de mobile.
"""

import json
import os
import re

import pytest
import requests

GATEWAY = os.environ.get("GATEWAY_URL", "http://gateway:8082").rstrip("/")
MEMBER = os.environ.get("TEST_MEMBER", "1019282447")
COMPANY = os.environ.get("TEST_COMPANY", "2014")
MISSING = "0000000001"
AUDIT_LOG = "/logs/audit.log"
LEGACY_WORDS = re.compile(r"nro_doc|est_afi|afi_mae|afi_ben|cod_emp|nom_emp|person_master|select |traceback", re.I)


def headers(variable):
    return {"Authorization": "Bearer " + os.environ[variable]}


def get(path, variable="PORTAL_TOKEN"):
    return requests.get(GATEWAY + path, headers=headers(variable) if variable else {}, timeout=5)


def post_retirement(document, variable, body=None):
    body = body if body is not None else {"requestId": "tests-" + document, "date": "2026-10-05", "reason": "prueba"}
    return requests.post(GATEWAY + "/api/v1/members/{0}/retirements".format(document), json=body, headers=headers(variable), timeout=5)


def test_health_reporta_gateway_y_legacy():
    resp = get("/health", None)
    assert resp.status_code == 200
    assert resp.json() == {"status": "UP", "legacy": "UP"}


def test_sin_token_responde_401():
    assert get("/api/v1/members/" + MEMBER, None).status_code == 401


def test_token_invalido_responde_401():
    resp = requests.get(GATEWAY + "/api/v1/members/" + MEMBER, headers={"Authorization": "Bearer no-existe"}, timeout=5)
    assert resp.status_code == 401


def test_afiliado_usa_modelo_canonico():
    resp = get("/api/v1/members/" + MEMBER)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"document", "fullName", "status", "company"}
    assert body["document"] == MEMBER
    assert body["status"] in ("ACTIVE", "RETIRED", "SUSPENDED")
    assert set(body["company"]) == {"id", "name"}


def test_afiliado_no_expone_nombres_legacy():
    assert not LEGACY_WORDS.search(get("/api/v1/members/" + MEMBER).text)


def test_afiliado_inexistente_404_con_formato_de_error():
    resp = get("/api/v1/members/" + MISSING)
    assert resp.status_code == 404
    body = resp.json()
    assert body["message"] and body["error_id"]
    assert not LEGACY_WORDS.search(resp.text)


def test_beneficiarios_es_lista_canonica():
    resp = get("/api/v1/members/{0}/beneficiaries".format(MEMBER))
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    for item in items:
        assert set(item) == {"document", "fullName", "relationship"}
        assert item["relationship"] in ("SPOUSE", "CHILD", "FATHER", "MOTHER")


def test_beneficiarios_de_inexistente_404():
    assert get("/api/v1/members/{0}/beneficiaries".format(MISSING)).status_code == 404


def test_empresa_con_afiliados_activos():
    resp = get("/api/v1/companies/" + COMPANY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == COMPANY and body["name"]
    assert isinstance(body["activeMembers"], int) and body["activeMembers"] >= 0


def test_empresa_inexistente_404():
    assert get("/api/v1/companies/NO-EXISTE").status_code == 404


def test_mobile_puede_leer():
    assert get("/api/v1/members/" + MEMBER, "MOBILE_TOKEN").status_code == 200


def test_mobile_no_puede_escribir():
    assert post_retirement(MISSING, "MOBILE_TOKEN").status_code == 403


def test_retiro_de_inexistente_404():
    assert post_retirement(MISSING, "PORTAL_TOKEN").status_code == 404


def test_retiro_con_cuerpo_invalido_400():
    resp = post_retirement(MISSING, "PORTAL_TOKEN", {"requestId": "", "date": "no-es-fecha"})
    assert resp.status_code == 400
    assert resp.json()["error_id"]


def test_estado_de_migracion():
    resp = get("/api/v1/migration/status")
    assert resp.status_code == 200
    domains = resp.json()["domains"]
    assert "affiliations" in domains
    assert all(state in ("LEGACY", "DUAL", "MODERN") for state in domains.values())


def test_auditoria_enmascara_documentos():
    get("/api/v1/members/" + MEMBER)
    if not os.path.exists(AUDIT_LOG):
        pytest.skip("logs/ no está montado en el contenedor de pruebas")
    lines = [l for l in open(AUDIT_LOG, encoding="utf-8").read().splitlines() if l.strip()][-50:]
    assert lines
    for line in lines:
        entry = json.loads(line)
        assert {"timestamp", "consumer", "endpoint", "status", "latency_ms"} <= set(entry)
        assert MEMBER not in line
