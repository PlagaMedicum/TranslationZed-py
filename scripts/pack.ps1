param(
    [string]$Name = "TranslationZed-Py"
)

$ErrorActionPreference = "Stop"
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RootDir

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is required; install the project with the "packaging" extra first.'
}

$upxArgs = @()
$upx = Get-Command upx -ErrorAction SilentlyContinue
if ($upx) {
    $upxArgs = @("--upx-dir", $upx.Source | Split-Path)
}

$excludes = Get-Content (Join-Path $RootDir "packaging\pyinstaller_excludes.txt") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

$excludeArgs = @()
foreach ($module in $excludes) {
    $excludeArgs += @("--exclude-module", $module)
}

python -m PyInstaller `
    --clean `
    --noconsole `
    --name $Name `
    --add-data "LICENSE;." `
    --add-data "README.md;." `
    @upxArgs `
    @excludeArgs `
    translationzed_py\__main__.py

powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\prune_bundle.ps1" -BundlePath "dist\$Name"
