#!/usr/bin/env python3
# Run this from the calibre source checkout.

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    sys.path.insert(0, str(src))
    # calibre expects these when running from source checkout (see run-local)
    sys.resources_location = str(repo_root / "resources")
    sys.extensions_location = str(src / "calibre" / "plugins")

    try:
        from calibre.utils.rapydscript import compile_srv  # noqa: E402
    except ModuleNotFoundError as e:
        # In a plain system Python, calibre's compiled extensions (calibre_extensions.*)
        # are usually not available. Auto re-run using the calibre.app bundled runtime.
        calibre_debug = Path("/Applications/calibre.app/Contents/MacOS/calibre-debug")
        if not calibre_debug.exists():
            raise SystemExit(
                "Failed to import calibre and calibre-debug not found at:\n"
                f"  {calibre_debug}\n\n"
                "Either run this script using calibre.app's Python environment or install a dev environment.\n\n"
                f"Original error: {e!r}"
            )
        payload = json.dumps({"repo_root": str(repo_root)}, ensure_ascii=False)
        code = r"""
import importlib.util, json, os, shutil, sys
from pathlib import Path

p = json.loads(sys.argv[-1])
repo_root = Path(p["repo_root"])
src = repo_root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
sys.resources_location = str(repo_root / "resources")
sys.extensions_location = str(src / "calibre" / "plugins")

rapy_path = src / "calibre" / "utils" / "rapydscript.py"
spec = importlib.util.spec_from_file_location("_calibre_src_rapydscript", rapy_path)
if spec is None or spec.loader is None:
    raise SystemExit(f"Failed to load rapydscript from: {rapy_path}")
rapy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rapy)

out = repo_root / "resources" / "content-server" / "index-generated.html"
before = out.stat().st_size if out.exists() else -1
rapy.compile_srv()
if not out.exists():
    raise SystemExit(f"compile_srv() finished but output missing: {out}")
after = out.stat().st_size
print(f"Generated: {out}")
print(f"Size: {after} bytes (before: {before} bytes)")

data = out.read_bytes()
needle = b"--cs-sidebar-width"
if needle not in data:
    raise SystemExit("Sanity check failed: sidebar marker not found in generated output")

app_resources_root = Path("/Applications/calibre.app/Contents/Resources/resources")
if not app_resources_root.exists():
    raise SystemExit(f"Target calibre.app resources directory not found: {app_resources_root}")
target = app_resources_root / "content-server" / "index-generated.html"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(out, target)
print(f"Installed to: {target}")
"""
        env = os.environ.copy()
        # compile_srv() uses the embedded RapydScript compiler which runs inside QtWebEngine.
        # On macOS this can be fragile in headless/non-interactive environments; these flags
        # generally improve stability.
        env.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
        env.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-software-rasterizer --no-sandbox")
        max_attempts = 12
        for attempt in range(1, max_attempts + 1):
            cp = subprocess.run([str(calibre_debug), "-c", code, payload], env=env)
            rc = int(cp.returncode)
            if rc == 0:
                return 0
            # 245 is seen when QtWebEngine subprocess startup fails on macOS.
            if rc == 245 and attempt < max_attempts:
                time.sleep(0.8 * attempt)
                continue
            return rc

    out = repo_root / "resources" / "content-server" / "index-generated.html"
    before = out.stat().st_size if out.exists() else -1

    compile_srv()

    if not out.exists():
        raise SystemExit(f"compile_srv() finished but output missing: {out}")

    after = out.stat().st_size
    print(f"Generated: {out}")
    print(f"Size: {after} bytes (before: {before} bytes)")

    # A tiny sanity check: ensure our sidebar CSS hook exists in output.
    data = out.read_bytes()
    needle = b"--cs-sidebar-width"
    if needle not in data:
        raise SystemExit("Sanity check failed: sidebar marker not found in generated output")

    # Copy into installed calibre.app resources (macOS)
    app_resources_root = Path("/Applications/calibre.app/Contents/Resources/resources")
    if not app_resources_root.exists():
        raise SystemExit(f"Target calibre.app resources directory not found: {app_resources_root}")
    target = app_resources_root / "content-server" / "index-generated.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(out, target)
    except PermissionError as e:
        raise SystemExit(
            "Permission denied while copying into calibre.app. "
            "Re-run with elevated privileges (e.g. prefix with sudo) or adjust permissions.\n\n"
            f"Target: {target}\n"
            f"Error: {e}"
        )
    print(f"Installed to: {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

