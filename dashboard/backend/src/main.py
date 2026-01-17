"""
FastAPI application entry point for Hospital Dashboard.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api import auth, analytics, units, devices, live

# Create FastAPI app
app = FastAPI(
    title="Hospital Dashboard API",
    description="Analytics dashboard for handwashing compliance monitoring",
    version="0.1.0",
)

# Configure CORS - Allow all origins for hackathon demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for demo
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1/analytics")
app.include_router(units.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1/devices")
app.include_router(live.router, prefix="/api/v1/live")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hospital Dashboard API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("Hospital Dashboard API starting...")
    print(f"CORS enabled for: {settings.cors_origins_list}")
    print(f"JWT token expiration: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("Hospital Dashboard API shutting down...")
