import tempfile
from pathlib import Path

from services.audio_analysis import extract_audio


# Cache loaded model to avoid reloading
_cached_model = None
_cached_model_name = None


def _get_model(model_name: str = "medium"):
    """Load Whisper model with caching."""
    global _cached_model, _cached_model_name

    if _cached_model is not None and _cached_model_name == model_name:
        return _cached_model

    import whisper

    _cached_model = whisper.load_model(model_name)
    _cached_model_name = model_name
    return _cached_model


def generate_subtitles(
    video_path: str,
    output_dir: Path,
    model_name: str = "medium",
    language: str = "ko",
) -> list[dict]:
    """Generate subtitles using Whisper STT.

    Returns list of {start, end, text} dicts.
    Also writes SRT file to output_dir/subtitles.srt.
    """
    import torch

    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract audio to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        extract_audio(video_path, tmp_path, sr=16000)

        # Load model (uses GPU if available)
        model = _get_model(model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Transcribe
        result = model.transcribe(
            tmp_path,
            language=language,
            fp16=(device == "cuda"),
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Extract segments
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })

    # Write SRT file
    srt_path = output_dir / "subtitles.srt"
    _write_srt(segments, srt_path)

    return segments


def _write_srt(segments: list[dict], path: Path):
    """Write segments to SRT format."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = round((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
