from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src._core.infrastructure.di.core_container import CoreContainer
from src._core.infrastructure.persistence.rdb.database import Database

router = APIRouter()


@router.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=200)


@router.get("/health/db")
@inject
async def database_health_check(  # Infrastructure health check — bypasses domain service by design
    database: Database = Depends(Provide[CoreContainer.database]),
):
    await database.check_connection()
    return JSONResponse(content={"status": "healthy"}, status_code=200)
