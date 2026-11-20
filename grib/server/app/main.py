import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core import executor
from app.core.connector import connector
from app.core.errors import GribError
from app.core.event_bus import bus
from app.core.scheduler import Scheduler
from app.db import SessionLocal, init_db
from app.routers import auth, collectors, dashboards, projects, sources, ws
from app.services import bootstrap, collector_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("grib")

scheduler = Scheduler(collector_service.run_collector)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.secret_key == "dev-secret-change-me-dev-secret-change-me":
        log.warning("GRIB_SECRET_KEY не задан — используется ключ для разработки")
    init_db()
    with SessionLocal() as session:
        bootstrap.seed(session)
    bus.attach_loop(asyncio.get_running_loop())
    if settings.scheduler_enabled:
        scheduler.start()
    yield
    scheduler.stop()
    executor.shutdown()
    connector.dispose_all()


app = FastAPI(title="Гриб", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GribError)
async def grib_error(_request: Request, exc: GribError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, **exc.extra})


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    message = f"{where}: {first.get('msg', 'неверные данные')}" if where else first.get("msg", "Неверные данные")
    return JSONResponse(status_code=422, content={"detail": message, "errors": jsonable_encoder(errors)})


@app.get("/api/health")
def health():
    return {"status": "ok", "websockets": bus.connection_count}


for module in (auth, projects, sources, dashboards, collectors):
    app.include_router(module.router, prefix="/api")
app.include_router(ws.router)

if settings.static_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="client")
