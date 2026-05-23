#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared build utilities for MySnipaste packaging (PyInstaller & Nuitka).
"""

import os
import sys
import subprocess
import shutil
from collections import deque
from pathlib import Path
from typing import Optional

BUILD_NAME = "MySnipaste"
PYINSTALLER_HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtSvg",
    "PySide6.QtWidgets",
    "pytesseract",
    "PIL._tkinter_finder",
    "pynput",
    "pynput._util.darwin",
    "pynput.keyboard._darwin",
]
PYINSTALLER_EXCLUDES = ["tkinter", "matplotlib"]


def get_project_dir() -> Path:
    return Path(__file__).parent.parent


def print_step(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def clean_build(dist_dir: Path, build_dir: Path, project_dir: Path) -> None:
    print_step("清理旧构建文件")
    for d in [dist_dir, build_dir]:
        if d.exists():
            shutil.rmtree(d)
    for spec in project_dir.glob("*.spec"):
        spec.unlink()
    print("[OK] 清理完成")


def check_source_changed(project_dir: Path) -> bool:
    """Return True if source files changed since last build."""
    cache_file = project_dir / "build" / ".build_cache"
    src_files = list(project_dir.glob("src/**/*.py")) + [project_dir / "main.py"]
    if not src_files:
        return True
    latest_mtime = max(f.stat().st_mtime for f in src_files if f.exists())
    if cache_file.exists():
        try:
            if latest_mtime <= float(cache_file.read_text().strip()):
                return False
        except (ValueError, OSError):
            pass
    cache_file.parent.mkdir(exist_ok=True)
    cache_file.write_text(str(latest_mtime))
    return True


# ─── Tesseract (macOS) ───


def find_tesseract() -> tuple[Optional[str], Optional[str]]:
    """Find Tesseract binary and tessdata directory on macOS."""
    print_step("查找 Tesseract OCR 引擎")
    tesseract_paths = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    tessdata_paths = [
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
    ]

    tesseract_bin = None
    for path in tesseract_paths:
        if Path(path).exists():
            tesseract_bin = path
            print(f"  Tesseract: {tesseract_bin}")
            break
    if not tesseract_bin:
        print("  Tesseract 未安装")
        return None, None

    tessdata_dir = None
    for path in tessdata_paths:
        if Path(path).exists():
            tessdata_dir = path
            print(f"  语言包目录: {tessdata_dir}")
            break
    if not tessdata_dir:
        print("  语言包未找到")
        return tesseract_bin, None

    for lang in ("eng", "chi_sim"):
        f = Path(tessdata_dir) / f"{lang}.traineddata"
        print(f"  {lang}: {'OK' if f.exists() else 'MISSING'}")

    return tesseract_bin, tessdata_dir


def _collect_dylibs(binary_path: str, bundle_dir: Path) -> set:
    """Recursively collect Homebrew dylib dependencies into bundle_dir."""
    processed: set[str] = set()
    queue: deque[str] = deque([binary_path])
    SYSTEM_PREFIXES = ("/usr/", "/System/", "/usr/lib/")

    while queue:
        path = queue.popleft()
        if path in processed:
            continue
        processed.add(path)
        if any(path.startswith(p) for p in SYSTEM_PREFIXES):
            continue

        dest = bundle_dir / os.path.basename(path)
        if not dest.exists() and not any(path.startswith(p) for p in SYSTEM_PREFIXES):
            try:
                shutil.copy2(path, dest)
                os.chmod(dest, 0o755)
                print(f"  + {os.path.basename(path)}")
            except (shutil.SameFileError, OSError):
                pass

        try:
            out = subprocess.check_output(
                ["otool", "-L", path], stderr=subprocess.DEVNULL, text=True
            )
            for line in out.splitlines()[1:]:
                dep_path = line.strip().split()[0]
                if not any(dep_path.startswith(p) for p in SYSTEM_PREFIXES) and dep_path not in processed:
                    queue.append(dep_path)
        except subprocess.CalledProcessError:
            pass

    return processed


def _patch_rpaths(bundle_dir: Path) -> None:
    """Rewrite dylib load paths to @loader_path/ relative."""
    for item in bundle_dir.iterdir():
        if not item.is_file() or item.name == "tesseract":
            continue
        try:
            subprocess.run(
                ["install_name_tool", "-id", f"@loader_path/{item.name}", str(item)],
                capture_output=True, check=False,
            )
        except Exception:
            pass

        try:
            out = subprocess.check_output(
                ["otool", "-L", str(item)], text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[1:]:
                dep_path = line.strip().split()[0]
                dep_name = os.path.basename(dep_path)
                if (bundle_dir / dep_name).exists() and dep_name != item.name:
                    subprocess.run(
                        ["install_name_tool", "-change", dep_path, f"@loader_path/{dep_name}", str(item)],
                        capture_output=True, check=False,
                    )
        except subprocess.CalledProcessError:
            pass

    tess_bin = bundle_dir / "tesseract"
    if tess_bin.exists():
        try:
            out = subprocess.check_output(
                ["otool", "-L", str(tess_bin)], text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[1:]:
                dep_path = line.strip().split()[0]
                dep_name = os.path.basename(dep_path)
                if (bundle_dir / dep_name).exists():
                    subprocess.run(
                        ["install_name_tool", "-change", dep_path, f"@loader_path/{dep_name}", str(tess_bin)],
                        capture_output=True, check=False,
                    )
        except subprocess.CalledProcessError:
            pass


def prepare_tesseract_bundle(
    tesseract_bin: Optional[str],
    tessdata_dir: Optional[str],
    build_dir: Path,
) -> tuple[list[str], list[str]]:
    """Copy Tesseract + dylibs + language data into a redistributable bundle.

    Returns (binary_paths, data_paths) — flat source paths.
    Callers add --add-binary/--add-data with appropriate dest directory.
    """
    if not tesseract_bin or not tessdata_dir:
        print("  跳过 Tesseract 打包")
        return [], []

    print_step("准备 Tesseract 打包")

    temp_tess_dir = build_dir / "tesseract_bundle"
    temp_tess_dir.mkdir(parents=True, exist_ok=True)

    temp_tess_bin = temp_tess_dir / "tesseract"
    shutil.copy2(tesseract_bin, temp_tess_bin)
    os.chmod(temp_tess_bin, 0o755)
    print("  Tesseract 二进制已复制")

    _collect_dylibs(str(temp_tess_bin), temp_tess_dir)
    _patch_rpaths(temp_tess_dir)

    temp_tessdata = temp_tess_dir / "tessdata"
    temp_tessdata.mkdir(exist_ok=True)
    for lang in ("eng", "chi_sim"):
        src = Path(tessdata_dir) / f"{lang}.traineddata"
        if src.exists():
            shutil.copy2(src, temp_tessdata / f"{lang}.traineddata")
            print(f"  {lang}: {src.stat().st_size / (1024 * 1024):.1f} MB")

    binary_paths = [str(temp_tess_dir / "tesseract")]
    for f in temp_tess_dir.iterdir():
        if f.is_file() and f.name != "tesseract" and f.suffix in (".dylib", ""):
            binary_paths.append(str(f))

    data_paths = [str(temp_tessdata)]

    return binary_paths, data_paths


# ─── macOS .app post-processing ───


def patch_info_plist(app_path: Path) -> None:
    """Inject screen recording & input monitoring permission descriptions into Info.plist."""
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.exists():
        print("[WARN] Info.plist not found")
        return
    try:
        import plistlib
        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)
        plist["NSScreenCaptureUsageDescription"] = (
            "MySnipaste needs screen recording permission to capture screenshots."
        )
        plist["NSInputMonitoringUsageDescription"] = (
            "MySnipaste needs input monitoring permission to detect global hotkeys."
        )
        with open(plist_path, "wb") as f:
            plistlib.dump(plist, f)
        print("[OK] Info.plist permissions added")
    except Exception as e:
        print(f"[WARN] Info.plist patch failed: {e}")


def sign_app(app_path: Path) -> None:
    """Ad-hoc sign the .app bundle (helps macOS permission APIs work correctly)."""
    try:
        subprocess.run(
            ["xattr", "-cr", str(app_path)],
            capture_output=True, check=False,
        )
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        print("[OK] 签名完成")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] 签名失败: {e.stderr.strip()}")
    except Exception as e:
        print(f"[WARN] 签名异常: {e}")


# ─── macOS .icns icon ───


def create_icns(project_dir: Path) -> None:
    """Create icon.icns from PNG assets if needed."""
    icns_path = project_dir / "icon.icns"
    png_dir = project_dir / "assets" / "icons"
    png_files = list(png_dir.glob("icon-*.png")) if png_dir.exists() else []

    need_rebuild = not icns_path.exists()
    if not need_rebuild and png_files:
        icns_mtime = icns_path.stat().st_mtime
        need_rebuild = any(p.stat().st_mtime > icns_mtime for p in png_files)

    if not need_rebuild:
        return

    print_step("创建 .icns 图标")

    png_path = project_dir / "assets" / "icons" / "icon-256.png"
    if not png_path.exists():
        print("[WARN] icon-256.png not found, skipping .icns")
        return

    iconset_path = project_dir / "icon.iconset"
    iconset_path.mkdir(exist_ok=True)

    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            actual = size * scale
            suffix = f"@{scale}x" if scale == 2 else ""
            output = iconset_path / f"icon_{size}x{size}{suffix}.png"
            source = project_dir / "assets" / "icons" / f"icon-{actual}.png"
            if not source.exists():
                source = png_path
            subprocess.run(
                ["sips", "-z", str(actual), str(actual), str(source), "--out", str(output)],
                check=True, capture_output=True,
            )

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_path), "-o", str(icns_path)],
        check=True,
    )
    shutil.rmtree(iconset_path)
    print(f"[OK] {icns_path}")
