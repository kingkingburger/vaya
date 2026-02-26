from fastapi import APIRouter

from config import AppConfig, load_config, save_config

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=AppConfig)
async def get_settings() -> AppConfig:
    return load_config()


@router.put("/settings", response_model=AppConfig)
async def update_settings(new_settings: AppConfig) -> AppConfig:
    save_config(new_settings)
    return new_settings
