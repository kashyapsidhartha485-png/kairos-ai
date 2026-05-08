"""
Kairos AI — FastAPI Application Entry Point
Emergency Response System Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import HealthResponse

# Import routers
from app.routers import register, emergency, driver, hospital, ambulance

app = FastAPI(
    title="Kairos AI",
    description="Emergency Response System — Multi-Agent AI Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — allow all origins for development/demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(register.router)
app.include_router(emergency.router)
app.include_router(driver.router)
app.include_router(hospital.router)
app.include_router(ambulance.router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with system info."""
    return {
        "system": "Kairos AI",
        "version": "1.0.0",
        "description": "Emergency Response System — Multi-Agent AI Backend",
        "health": "/health",
        "docs": "/docs"
    }
