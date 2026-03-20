"""
patch_favicon.py
─────────────────────────────────────────────────────────────────────────────
Run ONCE at startup (imported at the top of app.py) to physically replace
Streamlit's bundled favicon files with the JA.PREMIER logo.

This is the only 100% reliable method because Streamlit's index.html has
hardcoded <link rel="icon"> tags that point to its own static directory, and
its service-worker caches those files — JavaScript injected via st.markdown
always loses that race.

What this script does:
  1. Locates Streamlit's static folder (works on local, Streamlit Cloud,
     Docker, and most PaaS deployments).
  2. Downloads agency_logo.png once and writes it over every favicon variant
     Streamlit ships: favicon.png, favicon.ico, logo.png, logo192.png,
     logo512.png, apple-touch-icon.png, and the manifest icons.
  3. Also patches manifest.json inside the static folder so the PWA
     metadata (name, icons) matches JA.PREMIER.

Import this module before st.set_page_config() in app.py:
    import patch_favicon   # ← add this as the very first import
"""

import os
import json
import shutil
import urllib.request
import streamlit as st

LOGO_URL   = "https://jose101-lab.github.io/ja-premier-portal/agency_logo.png"
APP_NAME   = "JA.PREMIER"
THEME_COLOR = "#001f3f"

# ── Locate Streamlit's static directory ──────────────────────────────────────
def _find_static_dir() -> str | None:
    try:
        import streamlit
        base = os.path.dirname(streamlit.__file__)
        # Streamlit ≥ 1.x
        candidate = os.path.join(base, "static")
        if os.path.isdir(candidate):
            return candidate
        # Streamlit installed as a package in site-packages
        candidate2 = os.path.join(base, "frontend", "build")
        if os.path.isdir(candidate2):
            return candidate2
    except Exception:
        pass
    return None


# ── Download the logo to a temp file ─────────────────────────────────────────
def _fetch_logo(dest_path: str) -> bool:
    try:
        urllib.request.urlretrieve(LOGO_URL, dest_path)
        return os.path.getsize(dest_path) > 0
    except Exception as e:
        print(f"[patch_favicon] Could not download logo: {e}")
        return False


# ── Patch all favicon / icon files ───────────────────────────────────────────
def _patch_icons(static_dir: str, logo_path: str):
    targets = [
        "favicon.png",
        "favicon.ico",
        "logo.png",
        "logo192.png",
        "logo512.png",
        "apple-touch-icon.png",
        "apple-touch-icon-precomposed.png",
    ]
    for name in targets:
        dest = os.path.join(static_dir, name)
        try:
            shutil.copy2(logo_path, dest)
            print(f"[patch_favicon] ✔ replaced {dest}")
        except Exception as e:
            print(f"[patch_favicon] ✘ could not replace {dest}: {e}")

    # Also check inside a nested 'static' subfolder (some builds)
    nested = os.path.join(static_dir, "static")
    if os.path.isdir(nested):
        _patch_icons(nested, logo_path)


# ── Patch manifest.json ───────────────────────────────────────────────────────
def _patch_manifest(static_dir: str):
    manifest_paths = [
        os.path.join(static_dir, "manifest.json"),
        os.path.join(static_dir, "static", "manifest.json"),
    ]
    new_manifest = {
        "short_name": APP_NAME,
        "name": APP_NAME,
        "description": "JA.PREMIER Security Agency Portal",
        "icons": [
            {"src": "favicon.png",  "sizes": "64x64 32x32 24x24 16x16", "type": "image/png"},
            {"src": "logo192.png",  "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "logo512.png",  "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
        "start_url": ".",
        "display": "standalone",
        "theme_color": THEME_COLOR,
        "background_color": THEME_COLOR,
    }
    for path in manifest_paths:
        if os.path.exists(path):
            try:
                with open(path, "w") as f:
                    json.dump(new_manifest, f, indent=2)
                print(f"[patch_favicon] ✔ patched manifest {path}")
            except Exception as e:
                print(f"[patch_favicon] ✘ could not patch manifest {path}: {e}")


# ── Main entry ────────────────────────────────────────────────────────────────
def apply():
    static_dir = _find_static_dir()
    if not static_dir:
        print("[patch_favicon] ✘ Could not locate Streamlit static dir — skipping.")
        return

    # Use a temp path inside the app's own directory
    tmp_logo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_logo.png")
    if not _fetch_logo(tmp_logo):
        return

    _patch_icons(static_dir, tmp_logo)
    _patch_manifest(static_dir)

    # Clean up temp file
    try:
        os.remove(tmp_logo)
    except Exception:
        pass

    print("[patch_favicon] ✔ Done — JA.PREMIER favicon applied.")


# Run automatically on import
apply()
