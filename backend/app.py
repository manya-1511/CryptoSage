
"""
CryptoSage FastAPI application entrypoint.

Development:
    uvicorn app:app --reload

Production:
    Set ENVIRONMENT=production, DEBUG=False, SECRET_KEY, DATABASE_URL,
    and CORS_ORIGINS in the deployment environment before starting.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
