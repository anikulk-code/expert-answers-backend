from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from app.routers import answers

load_dotenv()

app = FastAPI(
    title="Expert Answers API",
    description="API for retrieving expert answers from YouTube video segments",
    version="0.1.0"
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

