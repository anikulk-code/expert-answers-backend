from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import threading

from app.routers import answers, tags

load_dotenv()


def _warm_tags_cache():
    try:
        tags.warm_tags_cache()
        print("Tags cache warmed")
    except Exception as e:
        print(f"Tags cache warm failed (Explore will fill it on first request): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_tags_cache, daemon=True).start()
    yield


app = FastAPI(
    title="Expert Answers API",
    description="API for retrieving expert answers from YouTube video segments",
    version="0.1.1",  # Updated for Azure deployment
    lifespan=lifespan,
)

# CORS middleware
# Allow origins from environment variable or default to all for development
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(answers.router, prefix="/api", tags=["answers"])
app.include_router(tags.router, prefix="/api", tags=["tags"])

@app.get("/")
async def root():
    return {
        "message": "Expert Answers API",
        "version": "0.1.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

