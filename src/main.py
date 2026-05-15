from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import src.db as db
from src.routes import admin, reports, speedtest, venues


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield


app = FastAPI(title="wifibuddy", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/static"), name="static")
app.include_router(venues.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(speedtest.router)
