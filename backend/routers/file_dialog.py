import asyncio
import subprocess
from fastapi import APIRouter, HTTPException

router = APIRouter()


def _open_dialog() -> str | None:
    """Windows 네이티브 파일 대화상자 (Topmost)."""
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            'Add-Type -AssemblyName System.Windows.Forms; '
            '$f = New-Object System.Windows.Forms.OpenFileDialog; '
            '$f.Filter = "Video files|*.mp4;*.mkv;*.mov;*.webm;*.avi|All files|*.*"; '
            '$f.Title = "영상 파일 선택"; '
            # Topmost 핸들로 대화상자를 최상위에 표시
            '$owner = New-Object System.Windows.Forms.Form; '
            '$owner.TopMost = $true; '
            'if ($f.ShowDialog($owner) -eq "OK") { $f.FileName } '
            '$owner.Dispose()'
        ],
        capture_output=True, text=True, timeout=120,
    )
    path = result.stdout.strip()
    return path if path else None


@router.post("/api/file-dialog")
async def open_file_dialog() -> dict:
    """Windows 네이티브 파일 대화상자를 열어 선택된 파일 경로를 반환."""
    try:
        file_path = await asyncio.to_thread(_open_dialog)
        return {"file_path": file_path}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="File dialog timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
