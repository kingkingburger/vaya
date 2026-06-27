from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from paths import config_path


class HighlightConfig(BaseModel):
    audio_weight: float = 0.6
    video_weight: float = 0.4
    top_percent: int = 30
    min_clip_duration: int = 3
    max_clip_duration: int = 60
    merge_gap: int = 2


class SilenceConfig(BaseModel):
    threshold_db: int = -40
    min_silence_duration: float = 1.5
    padding: float = 0.3


class SubtitleConfig(BaseModel):
    model: str = "medium"
    language: str = "ko"
    font_size: int = 24
    font_color: str = "white"
    outline_color: str = "black"
    position: str = "bottom"


class AppConfig(BaseModel):
    highlight: HighlightConfig = HighlightConfig()
    silence: SilenceConfig = SilenceConfig()
    subtitle: SubtitleConfig = SubtitleConfig()


def load_config(path: Optional[Path] = None) -> AppConfig:
    resolved_path = path or config_path()
    if resolved_path.exists():
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return AppConfig(**data)
    return AppConfig()


def save_config(config: AppConfig, path: Optional[Path] = None) -> None:
    resolved_path = path or config_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with open(resolved_path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
