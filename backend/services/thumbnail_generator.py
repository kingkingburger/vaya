import subprocess
from pathlib import Path


def generate_thumbnails(
    video_path: str,
    output_dir: Path,
    interval: float = 5.0,
    size: str = "320x180",
) -> list[str]:
    """Extract thumbnails from video at regular intervals.

    Returns list of thumbnail filenames (relative to output_dir).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration via ffprobe
    duration_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")

    duration = float(result.stdout.strip())
    filenames: list[str] = []

    # Extract thumbnails at each interval
    t = 0.0
    while t < duration:
        filename = f"thumb_{int(t):06d}.jpg"
        out_path = output_dir / filename

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(t),
            "-i", str(video_path),
            "-vframes", "1",
            "-s", size,
            "-q:v", "5",
            str(out_path),
        ]

        subprocess.run(cmd, capture_output=True, timeout=30)

        if out_path.exists():
            filenames.append(filename)

        t += interval

    return filenames
