#!/bin/bash
set -e

echo "=== Vaya Backend Setup ==="

# Check uv
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Install it from https://docs.astral.sh/uv/"
    exit 1
fi
echo "uv: $(uv --version)"

# Check Python
python_version=$(uv run python --version 2>/dev/null || echo "not found")
echo "Python: $python_version"

# Sync dependencies
echo ""
echo "=== Installing dependencies ==="
cd "$(dirname "$0")/../backend"
uv sync
echo "Dependencies installed."

# Check CUDA
echo ""
echo "=== Checking CUDA ==="
uv run python -c "
import torch
if torch.cuda.is_available():
    print(f'CUDA available: {torch.cuda.get_device_name(0)}')
    print(f'CUDA version: {torch.version.cuda}')
else:
    print('WARNING: CUDA not available. Whisper will use CPU (slower).')
" 2>/dev/null || echo "WARNING: PyTorch not installed or CUDA check failed."

# Check FFmpeg
echo ""
echo "=== Checking FFmpeg ==="
if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version 2>&1 | head -1)
    echo "FFmpeg: $ffmpeg_version"

    # Check NVENC
    if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
        echo "NVENC: available"
    else
        echo "WARNING: NVENC not available. Export will use software encoding (slower)."
    fi
else
    echo "ERROR: FFmpeg not found. Install FFmpeg and add to PATH."
    exit 1
fi

echo ""
echo "=== Setup complete ==="
