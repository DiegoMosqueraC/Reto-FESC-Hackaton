"""Gateway Legacy Escape: API v1 sobre la base legacy (puerto 8082).

Los consumidores solo ven el modelo canónico; el acceso a la base pasa por el adapter.
"""

import uuid

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from adapter import legacy_repository as legacy
from app.models import BeneficiaryList, Company, Member

app = FastAPI(title="Gateway Legacy Escape", version="1.0.0")


def error(status, message, **extra):
    body = {"message": message, "error_id": str(uuid.uuid4())}
    body.update(extra)
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(legacy.LegacyUnavailable)
async def legacy_unavailable(request, exc):
    return error(503, "La base legacy no está disponible, intente más tarde", code="LEGACY_UNAVAILABLE")


@app.exception_handler(legacy.NotFound)
async def not_found(request, exc):
    return error(404, "Recurso no encontrado")


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    message = exc.detail if isinstance(exc.detail, str) else "Error en la solicitud"
    return error(exc.status_code, message)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error(400, "Solicitud inválida: revise los campos enviados")


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return error(500, "Error interno del gateway")


@app.get("/health")
def health():
    return {"status": "UP", "legacy": "UP" if legacy.ping() else "DOWN"}


@app.get("/api/v1/members/{document}", response_model=Member)
def get_member(document: str):
    return legacy.get_member(document)


@app.get("/api/v1/members/{document}/beneficiaries", response_model=BeneficiaryList)
def get_beneficiaries(document: str):
    return legacy.get_beneficiaries(document)


@app.get("/api/v1/companies/{company_id}", response_model=Company)
def get_company(company_id: str):
    return legacy.get_company(company_id)
