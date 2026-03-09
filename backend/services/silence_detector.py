import subprocess
import tempfile
from pathlib import Path

import numpy as np


def detect_silence(
    video_path: str,
    threshold_db: int = -40,
    min_duration: float = 1.5,
    padding: float = 0.3,
    sr: int = 22050,
) -> list[dict]:
    """Detect silence segments in audio.

    Returns list of {start, end} dicts for silence segments.
    """
    import librosa

    # Extract audio
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", str(sr),
        "-f", "wav", tmp_path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=120)

    try:
        y, _ = librosa.load(tmp_path, sr=sr, mono=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if len(y) == 0:
        return []

    # Convert threshold from dB to amplitude
    threshold_amp = librosa.db_to_amplitude(threshold_db)

    # Compute RMS with small frames (~50ms)
    hop_length = sr // 20  # 50ms hops
    frame_length = sr // 10  # 100ms frames
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    # Find silent frames
    silent = rms < threshold_amp
    time_per_frame = hop_length / sr

    segments = []
    in_silence = False
    start = 0.0

    for i, is_silent in enumerate(silent):
        t = i * time_per_frame
        if is_silent and not in_silence:
            start = t
            in_silence = True
        elif not is_silent and in_silence:
            end = t
            duration = end - start
            if duration >= min_duration:
                segments.append({
                    "start": max(0, start + padding),
                    "end": max(0, end - padding),
                })
            in_silence = False

    # Handle trailing silence
    if in_silence:
        end = len(silent) * time_per_frame
        duration = end - start
        if duration >= min_duration:
            segments.append({
                "start": max(0, start + padding),
                "end": max(0, end - padding),
            })

    return segments
