import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.storage import init_storage
from app.core.jobs import enqueue_job, JOB_POLL_EMAILS
from app.mcp.server import mcp


async def schedule_email_polling():
    """Background task to enqueue email polling every minute if not already enqueued"""
    from app.core.jobs import is_job_type_queued
    while True:
        try:
            if not await is_job_type_queued(JOB_POLL_EMAILS):
                print("INFO: Enqueuing scheduled email polling job...")
                await enqueue_job(JOB_POLL_EMAILS, {})
            else:
                print("DEBUG: Email polling job already in queue, skipping enqueue.")
        except Exception as e:
            print(f"ERROR: Failed to enqueue email job: {e}")
        await asyncio.sleep(60) # Poll every minute

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

@app.on_event("startup")
async def startup_event():
    init_storage()
    # Start the scheduler in the background
    asyncio.create_task(schedule_email_polling())


# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount MCP SSE transport
app.mount("/mcp", mcp.sse_app())






@app.get("/")
async def root():
    return {"message": "Welcome to Nimbus API"}
