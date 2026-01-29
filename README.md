### Support me!

👋🤠 Hey, fellow wanderer! I have done a lot of work here, so you can show your apreciation for it and motivate me for further improvements by making some donation (any amount will be apreciated)!
↓ There are different donation options, so click the button below to learn more!

<noscript><a href="https://liberapay.com/buljion"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a></noscript>

# TranslationZed-Py

TranslationZed-Py is a Python Open-source re-implementation of [TranslationZed](https://pzwiki.net/wiki/TranslationZed) for platform-independent translation of Project Zomboid. It is built as a fast, lossless CAT tool for translators, by translators.

This project is currently WIP and not fully ready for production use.

This code was written at free time with a broad AI usage.

## Build & Run

Prerequisites:
- Python 3.11+
- `make`

Setup:
```bash
make venv
```

Run:
```bash
make run ARGS="path/to/ProjectZomboidTranslations"
```

Run tests:
```bash
make test
```

Notes:
- A local config is stored in `.tzp-config/settings.env`.
- Use `make run` without ARGS to open the default root (set on the first startup).

## Contributing
This codebase is largely written by AI (you are welcomed to help verify and improve it!). If you want to contribute, please read the `/docs`
and try to follow the architecture and standards described there. It was made for LLM to store context and my vision of the project.

## License
This project is Open-source, licensed under GPLv3. Distributions must include source code and the license text.
