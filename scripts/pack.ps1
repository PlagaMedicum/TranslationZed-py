param(
    [string]$Name = "TranslationZed-Py"
)

$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller

$upxArgs = @()
$upx = Get-Command upx -ErrorAction SilentlyContinue
if ($upx) {
    $upxArgs = @("--upx-dir", $upx.Source | Split-Path)
}

# Exclude unused Qt modules to keep bundles small; PySide6 hooks pull in required parts.
$excludes = @(
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets"
)

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
