param(
    [string]$Name = "TranslationZed-Py"
)

$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller

python -m PyInstaller `
    --clean `
    --noconsole `
    --name $Name `
    --add-data "LICENSE;LICENSE" `
    --add-data "README.md;README.md" `
    --collect-all PySide6 `
    translationzed_py\__main__.py
