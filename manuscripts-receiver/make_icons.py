#!/usr/bin/env python3
"""
Generate icon.icns (macOS) and icon.ico (Windows) from the app icon design.
Run automatically by build.sh / build_windows.bat before PyInstaller.
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).parent


def make_icon_image(size: int = 1024) -> Image.Image:
    from PIL import ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(size * 0.165)
    try:
        draw.rounded_rectangle([0, 0, size, size], radius=radius, fill="#2a2a2a")
    except AttributeError:
        draw.rectangle([0, 0, size, size], fill="#2a2a2a")

    font_path = SCRIPT_DIR / "JetBrainsMono-Regular.ttf"
    font_size = int(size * 0.5)
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "m."
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill="#e0af68")

    return img


def build_icns(png_path: Path, out_path: Path) -> None:
    """Convert a PNG to .icns using macOS sips + iconutil."""
    iconset = png_path.parent / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    sizes = [16, 32, 128, 256, 512]
    for s in sizes:
        subprocess.run(
            ["sips", "-z", str(s), str(s), str(png_path),
             "--out", str(iconset / f"icon_{s}x{s}.png")],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["sips", "-z", str(s * 2), str(s * 2), str(png_path),
             "--out", str(iconset / f"icon_{s}x{s}@2x.png")],
            check=True, capture_output=True,
        )

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(out_path)],
        check=True, capture_output=True,
    )
    shutil.rmtree(iconset)
    print(f"  icon.icns → {out_path}")


def build_ico(img: Image.Image, out_path: Path) -> None:
    """Save a multi-size .ico file."""
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(str(out_path), format="ICO", sizes=ico_sizes)
    print(f"  icon.ico  → {out_path}")


def main() -> None:
    print("Generating app icons...")
    img = make_icon_image(1024)
    png_path = SCRIPT_DIR / "icon.png"
    img.save(str(png_path))

    if platform.system() == "Darwin":
        build_icns(png_path, SCRIPT_DIR / "icon.icns")

    build_ico(img, SCRIPT_DIR / "icon.ico")
    png_path.unlink()
    print("Done.")


if __name__ == "__main__":
    main()
