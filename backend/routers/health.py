import subprocess

from fastapi import APIRouter

from models import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


def _check_gpu() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _check_nvenc() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "h264_nvenc" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        gpu_available=_check_gpu(),
        nvenc_available=_check_nvenc(),
    )
