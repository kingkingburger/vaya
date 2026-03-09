import subprocess
import tempfile
from pathlib import Path

import numpy as np


def analyze_frame_difference(video_path: str, fps: float = 2.0, size: str = "160x90") -> np.ndarray:
    """Analyze video frame differences using OpenCV.

    Extracts frames at given fps and computes inter-frame difference.
    Returns normalized 0-1 score array, one element per frame pair.
    """
    import cv2

    # Extract frames via ffmpeg to temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps},scale={size}",
            "-q:v", "5",
            f"{tmp_dir}/frame_%06d.jpg",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Frame extraction failed: {result.stderr.decode()}")

        # Load frames in order
        frame_files = sorted(Path(tmp_dir).glob("frame_*.jpg"))
        if len(frame_files) < 2:
            return np.array([])

        frames = []
        for f in frame_files:
            img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                frames.append(img.astype(np.float32))

    if len(frames) < 2:
        return np.array([])

    # Compute frame differences (absolute difference of consecutive frames)
    diffs = []
    for i in range(1, len(frames)):
        diff = np.mean(np.abs(frames[i] - frames[i - 1]))
        diffs.append(diff)

    scores = np.array(diffs)

    # Normalize to 0-1
    if scores.max() > 0:
        scores = scores / scores.max()

    return scores
