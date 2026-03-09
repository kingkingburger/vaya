from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from routers import health, settings, upload, video, analyze, subtitle, export

app = FastAPI(title="Vaya", version="0.1.0")

# CORS - allow localhost origins for Electrobun webview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for thumbnail serving
storage_path = Path(__file__).parent / "storage"
storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(storage_path)), name="static")

# Routers
app.include_router(health.router)
app.include_router(settings.router)
app.include_router(upload.router)
app.include_router(video.router)
app.include_router(analyze.router)
app.include_router(subtitle.router)
app.include_router(export.router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
