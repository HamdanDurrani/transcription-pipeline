from fastapi import APIRouter

from app.api.routes import router as transcribe_router

api_router = APIRouter()
api_router.include_router(transcribe_router)
