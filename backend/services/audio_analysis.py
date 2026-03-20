import subprocess
import tempfile
from pathlib import Path

import numpy as np


def extract_audio(video_path: str, output_path: str, sr: int = 22050) -> str:
    """Extract mono audio from video as WAV using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", str(sr),
        "-f", "wav",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr.decode('utf-8', errors='replace')}")
    return output_path


def analyze_audio_energy(video_path: str, sr: int = 22050) -> np.ndarray:
    """Analyze audio RMS energy, returns normalized 0-1 score array.

    Each element represents ~0.5 seconds of audio (hop_length=sr//2).
    """
    import librosa

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        extract_audio(video_path, tmp_path, sr=sr)
        y, _ = librosa.load(tmp_path, sr=sr, mono=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if len(y) == 0:
        return np.array([])

    # RMS energy with ~0.5s frames
    hop_length = sr // 2
    frame_length = sr  # 1 second window
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    # Normalize to 0-1
    if rms.max() > 0:
        rms = rms / rms.max()

    return rms
