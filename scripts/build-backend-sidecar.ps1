param(
    [string]$TargetTriple
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $repoRoot "backend"
$binariesDir = Join-Path $repoRoot "src-tauri\binaries"
$buildDir = Join-Path $repoRoot "build\backend-sidecar"
$distDir = Join-Path $buildDir "dist"
$workDir = Join-Path $buildDir "work"

if (-not $TargetTriple) {
    $TargetTriple = (& rustc --print host-tuple).Trim()
}

if (-not $TargetTriple) {
    throw "Failed to determine Rust target triple."
}

New-Item -ItemType Directory -Force -Path $binariesDir, $distDir, $workDir | Out-Null

Push-Location $backendDir
try {
    uv run --with pyinstaller pyinstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name vaya-backend `
        --distpath $distDir `
        --workpath $workDir `
        --specpath $buildDir `
        main.py
}
finally {
    Pop-Location
}

$sourceExe = Join-Path $distDir "vaya-backend.exe"
if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw "PyInstaller did not create $sourceExe."
}

$targetExe = Join-Path $binariesDir "vaya-backend-$TargetTriple.exe"
Copy-Item -LiteralPath $sourceExe -Destination $targetExe -Force
Write-Host "Created Tauri sidecar: $targetExe"
