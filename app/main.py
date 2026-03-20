"""
app/main.py

ByteWallet AI — FastAPI application entry point.
Configures CORS so the wallet frontend can call from any origin.
Pre-loads the ML model on startup.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.services.ml_service import preload_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load ML model into memory."""
    log.info(" ByteWallet AI  —  starting up ")
    preload_model()
    log.info("Server ready ")
    yield
    log.info(" ByteWallet AI  —  shutting down ")


app = FastAPI(
    title="ByteWallet AI",
    description=(
        "AI-powered financial burn-rate prediction for ASEAN youth.\n"
        "Custom ML Classifier + deterministic on-device reporting."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

#  CORS — allow wallet frontend (all origins) 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "ByteWallet AI", "version": "1.0.0"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}
