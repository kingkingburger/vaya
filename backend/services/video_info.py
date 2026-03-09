import json
import subprocess
from pathlib import Path


SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi"}


def validate_video_file(file_path: str) -> Path:
    """Validate that the file exists and is a supported video format."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported format: {path.suffix}")
    return path


def extract_metadata(file_path: str) -> dict:
    """Extract video metadata using FFprobe."""
    path = validate_video_file(file_path)

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")

    probe = json.loads(result.stdout)

    # Find video stream
    video_stream = None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise ValueError("No video stream found in file")

    # Extract FPS from r_frame_rate (e.g., "60/1" or "30000/1001")
    fps_parts = video_stream.get("r_frame_rate", "0/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) != 0 else 0.0

    return {
        "duration": float(probe["format"].get("duration", 0)),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": round(fps, 2),
        "codec": video_stream.get("codec_name", "unknown"),
        "file_size": int(probe["format"].get("size", 0)),
    }
