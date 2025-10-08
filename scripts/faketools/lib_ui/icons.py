"""Icon utility."""

from pathlib import Path


def get_path(picture_name: str) -> str:
    """Get the icon path.

    Args:
        picture_name (str): The name of the icon including the extension.

    Returns:
        str: The icon path.
    """
    icon_path = Path(__file__).parent / "images" / f"{picture_name}.png"
    if not icon_path.exists():
        raise FileNotFoundError(f"Icon not found: {icon_path}")

    return icon_path.as_posix()
