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
        $platforms = Join-Path $plugins "platforms"
        if (Test-Path $platforms) {
            $keep = @("qwindows.dll")
            Get-ChildItem -Path $platforms | ForEach-Object {
                if ($keep -notcontains $_.Name) {
                    Remove-Item -Recurse -Force $_.FullName
                }
            }
        }
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

        $imageFormats = Join-Path $plugins "imageformats"
        if (Test-Path $imageFormats) {
            $keep = @("qpng", "qsvg", "qjpeg", "qico")
            Get-ChildItem -Path $imageFormats | ForEach-Object {
                $name = $_.BaseName
                $keepMatch = $false
                foreach ($prefix in $keep) {
                    if ($name.StartsWith($prefix)) {
                        $keepMatch = $true
                        break
                    }
                }
                if (-not $keepMatch) {
                    Remove-Item -Recurse -Force $_.FullName
                }
            }
        }

        $iconEngines = Join-Path $plugins "iconengines"
        if (Test-Path $iconEngines) {
            Get-ChildItem -Path $iconEngines | ForEach-Object {
                if (-not $_.BaseName.StartsWith("qsvgicon")) {
                    Remove-Item -Recurse -Force $_.FullName
                }
            }
        }
    }
}

foreach ($lib in @(
    "Qt63DAnimation",
    "Qt63DCore",
    "Qt63DExtras",
    "Qt63DInput",
    "Qt63DLogic",
    "Qt63DRender",
    "Qt6Charts",
    "Qt6DataVisualization",
    "Qt6Multimedia",
    "Qt6MultimediaWidgets",
    "Qt6NetworkAuth",
    "Qt6Pdf",
    "Qt6PdfWidgets",
    "Qt6Positioning",
    "Qt6Quick",
    "Qt6Quick3D",
    "Qt6QuickControls2",
    "Qt6QuickWidgets",
    "Qt6Qml",
    "Qt6Sensors",
    "Qt6SerialPort",
    "Qt6Sql",
    "Qt6Test",
    "Qt6TextToSpeech",
    "Qt6WebChannel",
    "Qt6WebEngineCore",
    "Qt6WebEngineWidgets",
    "Qt6WebEngine",
    "Qt6WebSockets"
)) {
    Get-ChildItem -Path $qtDir -Recurse -File -Filter "$lib.dll" -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -Force $_.FullName }
}

Get-ChildItem -Path $BundlePath -Recurse -Directory -Include "*.dist-info", "*.egg-info", "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
