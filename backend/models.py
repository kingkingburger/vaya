from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    gpu_available: bool = False
    nvenc_available: bool = False


class VideoInfo(BaseModel):
    id: str
    file_path: str
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    file_size: int


class UploadRequest(BaseModel):
    file_path: str


class UploadResponse(BaseModel):
    id: str
    info: VideoInfo
    thumbnail_count: int = 0


class HighlightSegment(BaseModel):
    start: float
    end: float
    score: float = 0.0


class SubtitleSegment(BaseModel):
    start: float
    end: float
    text: str


class ExportRequest(BaseModel):
    youtube: bool = True
    shorts: bool = False
    subtitles: bool = True
    crop_offset: int = 0


class ProgressMessage(BaseModel):
    stage: str
    percent: float
    message: str
