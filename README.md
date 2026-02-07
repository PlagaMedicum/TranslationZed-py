### Support me!

👋🤠 Hey, fellow wanderer! I have done a lot of work here, so you can show your apreciation for it and motivate me for further improvements by making some donation (any amount will be apreciated)!
↓ There are different donation options, so click the button below to learn more!

<noscript><a href="https://liberapay.com/buljion"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a></noscript>

# TranslationZed-Py

TranslationZed-Py is a Python Open-source re-implementation of [TranslationZed](https://pzwiki.net/wiki/TranslationZed) for platform-independent translation of Project Zomboid. It is built as a fast, lossless CAT tool for translators, by translators. [Discussion on the PZ forum](https://theindiestone.com/forums/index.php?/topic/91297-translationzed-py-%E2%80%93-a-new-project-zomboid-translation-tool/).

This project is currently WIP and not fully ready for production use.

This code was written at free time with a broad AI usage.

# Releases
Prebuilt app folders are published as **[releases](https://github.com/PlagaMedicum/TranslationZed-py/releases)** on GitHub (Linux/Windows/macOS).
Download the ZIP for your OS, extract it, and run the executable inside the folder:
- Linux/macOS: `TranslationZed-Py`
- Windows: `TranslationZed-Py.exe`

## Build & Run (from source)

Prerequisites:
- Python 3.10+
- `make` (Linux/macOS)

Linux/macOS:
```bash
make venv
make run ARGS="path/to/ProjectZomboidTranslations"
```

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m translationzed_py "path\\to\\ProjectZomboidTranslations"
```

Run tests:
```bash
make test
```

Notes:
- A local config is stored in `.tzp-config/settings.env`.
- Use `make run` without ARGS to open the default root (set on the first startup).

## Packaging (executables)
We build executables **on each target OS** (no cross‑compilation).

Linux/macOS:
```bash
make pack
```

Windows (PowerShell):
```powershell
python -m pip install -e ".[dev,packaging]"
python -m PyInstaller --clean --noconsole --name TranslationZed-Py ^
  --add-data "LICENSE;LICENSE" --add-data "README.md;README.md" ^
  --collect-all PySide6 translationzed_py\\__main__.py
```

Artifacts are written to `dist/TranslationZed-Py/` (PyInstaller default).

Releases:
- Tagged pushes (`vX.Y.Z`) trigger multi‑OS builds in GitHub Actions.
- Each release contains zipped app folders for Linux, Windows, and macOS.

## Contributing
This codebase is largely written by AI (you are welcomed to help verify and improve it!). If you want to contribute, please read the `/docs`
and try to follow the architecture and standards described there. It was made for LLM to store context and my vision of the project.
For document ownership and anti-duplication rules, follow `docs/docs_structure.md`.

## License
This project is Open-source, licensed under GPLv3. Distributions must include source code and the license text.

Developed with assistance from Codex in VSCodium (GPT‑Plus). Contributors should ensure their usage complies with OpenAI terms/policies and review any generated code for third‑party license obligations before inclusion.
