"""Default application handler using OS file associations."""

from .....lib_ui.qt_compat import QDesktopServices, QUrl
from .base import ExternalAppHandler


class DefaultAppHandler(ExternalAppHandler):
    """Handler that opens images using the OS default application.

    Uses QDesktopServices to open the image file, which launches
    the default application associated with the file type.
    """

    @property
    def menu_name(self) -> str:
        """Return the menu display name.

        Returns:
            Display name for context menu.
        """
        return "Edit in External App"

    @property
    def supported_platforms(self) -> list[str]:
        """Return supported platforms.

        Currently only supports Windows.

        Returns:
            List containing "win32".
        """
        return ["win32"]

    def open_image(self, image_path: str) -> bool:
        """Open an image file using the OS default application.

        Args:
            image_path: Absolute path to the image file.

        Returns:
            True if the application was launched successfully.
        """
        return QDesktopServices.openUrl(QUrl.fromLocalFile(image_path))
