"""
HAMMY — FastAPI Parent Backend Application (`services/api/main.py`).
Blueprint Endpoints:
  - Pets, State, Events, Memories
  - Habitat & Object rearrangement
  - Care (feed, water, enrichment)
  - Simulation (pause, resume)
  - System health
  - Real-time WebSocket streaming
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes import care, clips, habitat, notifications, pets, simulation, system, ws

app = FastAPI(
    title="HAMMY Parent API",
    description="Backend API and real-time WebSocket service for HAMMY — Virtual Syrian Hamster Simulation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS configuration for local development and Observatory web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register versioned routers
app.include_router(pets.router, prefix="/api/v1", tags=["Pets"])
app.include_router(clips.router, prefix="/api/v1", tags=["Clips"])
app.include_router(habitat.router, prefix="/api/v1", tags=["Habitat"])
app.include_router(care.router, prefix="/api/v1", tags=["Care"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(simulation.router, prefix="/api/v1", tags=["Simulation"])
app.include_router(system.router, prefix="/api/v1", tags=["System"])
app.include_router(ws.router, prefix="/api/v1", tags=["WebSocket"])


@app.get("/")
def root():
    return {
        "service": "HAMMY Parent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/system/health",
    }

