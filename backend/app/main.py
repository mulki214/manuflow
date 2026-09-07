from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import PurchasingDepartmentMiddleware
from app.routers import (
    analytics,
    auth,
    logistics,
    master_data,
    module_access,
    production,
    purchasing,
    quality,
    receiving,
    sales_orders,
    users,
    warehouse,
)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(PurchasingDepartmentMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(master_data.router, prefix=settings.api_prefix)
app.include_router(module_access.router, prefix=settings.api_prefix)
app.include_router(purchasing.router, prefix=settings.api_prefix)
app.include_router(sales_orders.router, prefix=settings.api_prefix)
app.include_router(receiving.router, prefix=settings.api_prefix)
app.include_router(warehouse.router, prefix=settings.api_prefix)
app.include_router(production.router, prefix=settings.api_prefix)
app.include_router(quality.router, prefix=settings.api_prefix)
app.include_router(logistics.finish_router, prefix=settings.api_prefix)
app.include_router(logistics.delivery_router, prefix=settings.api_prefix)
app.include_router(analytics.dashboard_router, prefix=settings.api_prefix)
app.include_router(analytics.reporting_router, prefix=settings.api_prefix)


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
