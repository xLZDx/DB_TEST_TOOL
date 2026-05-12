$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$srcDir = Join-Path $root "src"
$entry = Join-Path $srcDir "task_repeat\__main__.py"
$workDir = Join-Path $root "build"
$distDir = Join-Path $root "dist"
$specDir = $root

if ((Get-Item $root).PSDrive.Name -eq "C") {
    throw "Refusing to build on C:\ (D:-drive-only policy). Move the repo to D:."
}

pyinstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name task_repeat `
    --paths $srcDir `
    --workpath $workDir `
    --distpath $distDir `
    --specpath $specDir `
    $entry

Write-Host ""
Write-Host "Build complete. Output:" -ForegroundColor Green
Write-Host (Join-Path $distDir "task_repeat.exe")
