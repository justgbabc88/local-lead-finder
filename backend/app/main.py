"""FastAPI entrypoint."""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    companies, domain_health, email_bison, enrichment, phase6, scrape,
    settings as settings_api, validation, workspaces, zips,
)
from app.api.envelope import err
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="LocalLeadEngine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=err("http_error", str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=err("validation_error", "Invalid request", {"errors": exc.errors()}),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("app").exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content=err("internal_error", f"{type(exc).__name__}: {exc}"),
    )


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None, "meta": None}


app.include_router(workspaces.router)
app.include_router(scrape.router)
app.include_router(companies.router)
app.include_router(settings_api.router)
app.include_router(zips.router)
app.include_router(enrichment.router)
app.include_router(validation.router)
app.include_router(email_bison.router)
app.include_router(phase6.router)
app.include_router(domain_health.router)
