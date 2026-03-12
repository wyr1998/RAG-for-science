"""
Entry point for the PyInstaller-built backend executable.

When frozen:
- Prepends sys._MEIPASS to sys.path so backend modules (api_server, step1_grobid, ...) are found.
- Sets BUNDLED_JRE_DIR to <exe_dir>/backend/jdk-17.0.18+8-jre if that directory exists,
  so PDFFigures2 uses the bundled JRE without users setting it.

When not frozen (development), just runs uvicorn; run from project root with:
  python backend/run_backend_frozen.py
"""
import os
import sys
from pathlib import Path

# Force UTF-8 for all stdio in this process. This helps avoid
# UnicodeEncodeError on Windows environments with a non-UTF-8
# default code page when the app logs or prints Unicode.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if getattr(sys, "frozen", False):
    bundle_dir = Path(sys._MEIPASS)
    sys.path.insert(0, str(bundle_dir))
    exe_dir = Path(sys.executable).resolve().parent
    jre_dir = exe_dir / "backend" / "jdk-17.0.18+8-jre"
    java_exe = jre_dir / "bin" / ("java.exe" if sys.platform.startswith("win") else "java")
    if java_exe.is_file():
        os.environ["BUNDLED_JRE_DIR"] = str(jre_dir)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
