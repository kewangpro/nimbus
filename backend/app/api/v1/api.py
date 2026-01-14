from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, issues, ws, ai, uploads

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(ws.router, tags=["websockets"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])