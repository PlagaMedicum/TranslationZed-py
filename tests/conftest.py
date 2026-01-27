import os

# Ensure Qt runs headless in CI/CLI environments without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
