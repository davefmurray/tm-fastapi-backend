"""
TM FastAPI Backend - Main Application

Tekmetric API proxy and custom dashboard backend.
Provides clean REST API for TM operations with custom metric calculations.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import logging

from app.routers import authorization, dashboard, payments, customers, ro_operations, appointments, parts, vcdb, jobs, inspections, employees, inventory, carfax, shop, reports, advanced, fleet, utility, analytics, history, realtime, advisors, trends, audit, sync
from app.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting TM FastAPI Backend...")
    start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down TM FastAPI Backend...")
    stop_scheduler()


# Initialize FastAPI app
app = FastAPI(
    title="TM API Backend",
    description="Tekmetric API proxy with custom dashboard logic",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (configure for your domains)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(authorization.router, prefix="/api/auth", tags=["Authorization"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(ro_operations.router, prefix="/api/ro", tags=["Repair Orders"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(parts.router, prefix="/api/parts", tags=["Parts & Orders"])
app.include_router(vcdb.router, prefix="/api/vcdb", tags=["VCDB Lookups"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(inspections.router, prefix="/api/inspections", tags=["Inspections"])
app.include_router(employees.router, prefix="/api/employees", tags=["Employees"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])
app.include_router(carfax.router, prefix="/api/carfax", tags=["Carfax"])
app.include_router(shop.router, prefix="/api/shop", tags=["Shop"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(advanced.router, prefix="/api/advanced", tags=["Advanced"])
app.include_router(fleet.router, prefix="/api/fleet", tags=["Fleet & AR"])
app.include_router(utility.router, prefix="/api/utility", tags=["Utility"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics (Tier 3)"])
app.include_router(history.router, prefix="/api/history", tags=["History (Tier 4)"])
app.include_router(realtime.router, prefix="/api/realtime", tags=["Real-time (Tier 5)"])
app.include_router(advisors.router, prefix="/api/advisors", tags=["Advisors (Tier 6)"])
app.include_router(trends.router, prefix="/api/trends", tags=["Trends (Tier 7)"])
app.include_router(audit.router, prefix="/api/audit", tags=["Data Audit"])
app.include_router(sync.router, prefix="/api/sync", tags=["Warehouse Sync"])


@app.get("/")
def read_root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "TM FastAPI Backend",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "tm_base_url": os.getenv("TM_BASE_URL", "https://shop.tekmetric.com"),
        "shop_id": os.getenv("TM_SHOP_ID", "configured"),
        "auth_configured": bool(os.getenv("TM_AUTH_TOKEN"))
    }


@app.get("/dashboard")
def serve_dashboard():
    """Serve live dashboard HTML"""
    return FileResponse("dashboard.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
