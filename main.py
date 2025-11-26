"""
TM FastAPI Backend - Main Application

Tekmetric API proxy and custom dashboard backend.
Provides clean REST API for TM operations with custom metric calculations.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routers import authorization, dashboard, payments, customers, ro_operations, appointments, parts, vcdb, jobs, inspections, employees, inventory

# Initialize FastAPI app
app = FastAPI(
    title="TM API Backend",
    description="Tekmetric API proxy with custom dashboard logic",
    version="1.0.0"
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
