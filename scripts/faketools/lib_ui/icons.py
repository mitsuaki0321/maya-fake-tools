"""Icon utility."""

from __future__ import annotations

from pathlib import Path

_DEFAULT_IMAGES_DIR = Path(__file__).parent / "images"
_EXTENSIONS = (".svg", ".png")


def get_path(picture_name: str, base_dir: Path | str | None = None) -> str:
    """Get the icon path.

    Searches for SVG first, then PNG. An optional *base_dir* overrides the
    default ``lib_ui/images/`` directory, allowing each tool to ship its own
    icons.

    Args:
        picture_name (str): The name of the icon (without extension).
        base_dir (Path | str | None): Directory to search in.
            ``None`` falls back to the default ``lib_ui/images/`` directory.

    Returns:
        str: The icon path (posix-style forward slashes).
    """
    images_dir = Path(base_dir) if base_dir is not None else _DEFAULT_IMAGES_DIR
    for ext in _EXTENSIONS:
        icon_path = images_dir / f"{picture_name}{ext}"
        if icon_path.exists():
            return icon_path.as_posix()

    checked = [str(images_dir / f"{picture_name}{ext}") for ext in _EXTENSIONS]
    raise FileNotFoundError(f"Icon not found. Checked: {', '.join(checked)}")
