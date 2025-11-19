from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import async_engine, Base
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Product Importer API",
    description="API for importing and managing products from CSV files",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    # Create database tables (in production, use Alembic migrations instead)
    # async with async_engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    pass


@app.on_event("shutdown")
async def shutdown_event():
    await async_engine.dispose()


@app.get("/")
async def root():
    return {"message": "Product Importer API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

