import asyncio
import re
import subprocess
from datetime import datetime
from pathlib import Path

from config import AppConfig
from models import HighlightSegment


STORAGE_DIR = Path(__file__).parent.parent / "storage"
OUTPUT_DIR = STORAGE_DIR / "output"


def _detect_encoder() -> str:
    """Detect available H.264 encoder: prefer NVENC, fallback to libx264."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, timeout=10,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        if "h264_nvenc" in stdout:
            # Test if NVENC actually works
            test = subprocess.run(
                ["ffmpeg", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
                 "-c:v", "h264_nvenc", "-f", "null", "-"],
                capture_output=True, timeout=10,
            )
            if test.returncode == 0:
                return "h264_nvenc"
    except Exception:
        pass
    return "libx264"


def _unique_path(path: Path) -> Path:
    """If path exists, append _1, _2, etc."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 1
    while True:
        new_path = parent / f"{stem}_{i}{suffix}"
        if not new_path.exists():
            return new_path
        i += 1


def _format_output_name(original_name: str, fmt: str) -> str:
    """Generate output filename: {original}_{date}_{format}.mp4"""
    stem = Path(original_name).stem
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{stem}_{date_str}_{fmt}.mp4"


def _build_filter_complex(
    highlights: list[HighlightSegment],
    silence_segments: list[dict],
    subtitles_path: str | None,
    subtitle_config: dict,
    is_shorts: bool = False,
    crop_offset: int = 0,
) -> str:
    """Build FFmpeg filter_complex string for segment concatenation."""
    filters = []

    # For each highlight, trim and optionally remove silence
    segment_labels = []
    for i, h in enumerate(highlights):
        # Trim segment
        filters.append(f"[0:v]trim=start={h.start}:end={h.end},setpts=PTS-STARTPTS[v{i}]")
        filters.append(f"[0:a]atrim=start={h.start}:end={h.end},asetpts=PTS-STARTPTS[a{i}]")
        segment_labels.append(f"[v{i}][a{i}]")

    # Concatenate all segments
    n = len(highlights)
    if n == 0:
        return ""

    concat_input = "".join(segment_labels)
    filters.append(f"{concat_input}concat=n={n}:v=1:a=1[vcat][acat]")

    # Apply Shorts crop if needed
    if is_shorts:
        # Center crop 608x1080 then scale to 1080x1920
        filters.append(f"[vcat]crop=608:1080:{crop_offset}:0,scale=1080:1920[vout]")
    else:
        filters.append("[vcat]copy[vout]")

    # Add subtitle burn-in if available
    if subtitles_path and Path(subtitles_path).exists():
        safe_path = subtitles_path.replace("\\", "/").replace(":", "\\\\:")
        font_color = subtitle_config.get("font_color", "white")
        outline_color = subtitle_config.get("outline_color", "black")
        font_size = subtitle_config.get("font_size", 24)
        filters[-1] = filters[-1].replace("[vout]", "[vpre]")
        filters.append(
            f"[vpre]subtitles='{safe_path}':force_style='FontSize={font_size},"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
            f"Outline=2'[vout]"
        )

    filters.append("[acat]anull[aout]")

    return ";".join(filters)


async def export_video(
    video_id: str,
    file_path: str,
    highlights: list[HighlightSegment],
    silence_segments: list[dict],
    subtitles_path: str | None,
    config: AppConfig,
    youtube: bool = True,
    shorts: bool = False,
    subtitles: bool = True,
    crop_offset: int = 0,
    progress_callback=None,
) -> list[dict]:
    """Export video with highlights, optional subtitles, in YouTube and/or Shorts format.

    Returns list of {format, path, size} for each output file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    encoder = _detect_encoder()
    original_name = Path(file_path).name
    results = []

    sub_path = subtitles_path if subtitles else None
    sub_config = config.subtitle.model_dump() if subtitles else {}

    # YouTube export
    if youtube:
        if progress_callback:
            await progress_callback("export", 5, "1/2 · YouTube용 인코딩 중...")

        out_name = _format_output_name(original_name, "youtube")
        out_path = _unique_path(OUTPUT_DIR / out_name)

        filter_str = _build_filter_complex(
            highlights, silence_segments, sub_path, sub_config,
            is_shorts=False,
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(file_path),
            "-filter_complex", filter_str,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", encoder,
            "-b:v", "8M",
            "-r", "60",
            "-s", "1920x1080",
            "-c:a", "aac", "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            "-async", "1",
            str(out_path),
        ]

        await _run_ffmpeg(cmd, progress_callback, "export", 5, 50)
        results.append({
            "format": "youtube",
            "path": str(out_path),
            "size": out_path.stat().st_size if out_path.exists() else 0,
        })

    # Shorts export (sequential after YouTube)
    if shorts:
        if progress_callback:
            await progress_callback("export", 55, "2/2 · Shorts용 인코딩 중...")

        out_name = _format_output_name(original_name, "shorts")
        out_path = _unique_path(OUTPUT_DIR / out_name)

        filter_str = _build_filter_complex(
            highlights, silence_segments, sub_path, sub_config,
            is_shorts=True, crop_offset=crop_offset,
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(file_path),
            "-filter_complex", filter_str,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", encoder,
            "-b:v", "6M",
            "-r", "60",
            "-c:a", "aac", "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            "-async", "1",
            str(out_path),
        ]

        await _run_ffmpeg(cmd, progress_callback, "export", 55, 95)
        results.append({
            "format": "shorts",
            "path": str(out_path),
            "size": out_path.stat().st_size if out_path.exists() else 0,
        })

    if progress_callback:
        await progress_callback("complete", 100, "내보내기 완료")

    return results


async def _run_ffmpeg(cmd: list[str], progress_callback, stage: str, start_pct: float, end_pct: float):
    """Run FFmpeg process and parse stderr for progress."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )

    duration_re = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)")
    time_re = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")
    total_duration = 0.0

    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="ignore")

        # Parse total duration
        dm = duration_re.search(text)
        if dm:
            total_duration = (
                int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 +
                int(dm.group(3)) + int(dm.group(4)) / 100
            )

        # Parse current time
        tm = time_re.search(text)
        if tm and total_duration > 0 and progress_callback:
            current = (
                int(tm.group(1)) * 3600 + int(tm.group(2)) * 60 +
                int(tm.group(3)) + int(tm.group(4)) / 100
            )
            pct = start_pct + (current / total_duration) * (end_pct - start_pct)
            await progress_callback(stage, min(pct, end_pct), "인코딩 중...")

    await proc.wait()
    if proc.returncode != 0:
        # 남은 stderr 읽기
        remaining = await proc.stderr.read() if proc.stderr else b""
        err_text = remaining.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"FFmpeg export failed (exit code {proc.returncode}): {err_text}")
