import subprocess
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/api/file-dialog")
async def open_file_dialog() -> dict:
    """Windows 네이티브 파일 대화상자를 열어 선택된 파일 경로를 반환."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                'Add-Type -AssemblyName System.Windows.Forms; '
                '$f = New-Object System.Windows.Forms.OpenFileDialog; '
                '$f.Filter = "Video files|*.mp4;*.mkv;*.mov;*.webm;*.avi|All files|*.*"; '
                '$f.Title = "영상 파일 선택"; '
                'if ($f.ShowDialog() -eq "OK") { $f.FileName }'
            ],
            capture_output=True, text=True, timeout=120,
        )
        file_path = result.stdout.strip()
        if not file_path:
            return {"file_path": None}
        return {"file_path": file_path}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="File dialog timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
