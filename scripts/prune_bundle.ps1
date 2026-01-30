param(
    [Parameter(Mandatory = $true)]
    [string]$BundlePath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BundlePath)) {
    if (Test-Path "$BundlePath.app") {
        $BundlePath = "$BundlePath.app"
    } else {
        throw "Bundle not found: $BundlePath"
    }
}

$pySideDir = Get-ChildItem -Path $BundlePath -Recurse -Directory -Filter PySide6 -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $pySideDir) {
    Write-Host "PySide6 not found under $BundlePath; skipping prune."
    return
}

$qtDir = Join-Path $pySideDir.FullName "Qt"
if (Test-Path $qtDir) {
    foreach ($dir in @("qml", "translations")) {
        $target = Join-Path $qtDir $dir
        if (Test-Path $target) {
            Remove-Item -Recurse -Force $target
        }
    }

    $plugins = Join-Path $qtDir "plugins"
    if (Test-Path $plugins) {
        $removePlugins = @(
            "assetimporters",
            "bearer",
            "egldeviceintegrations",
            "gamepads",
            "geometryloaders",
            "geoservices",
            "mediaservice",
            "multimedia",
            "networkinformation",
            "position",
            "renderers",
            "renderplugins",
            "sceneparsers",
            "sensorgestures",
            "sensors",
            "sqldrivers",
            "texttospeech",
            "tls",
            "webview",
            "windowdecorations",
            "designer",
            "qmltooling"
        )
        foreach ($name in $removePlugins) {
            $target = Join-Path $plugins $name
            if (Test-Path $target) {
                Remove-Item -Recurse -Force $target
            }
        }
    }
}

Get-ChildItem -Path $BundlePath -Recurse -Directory -Include "*.dist-info", "*.egg-info", "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
