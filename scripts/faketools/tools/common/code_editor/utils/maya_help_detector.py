"""
Maya command help URL detector.
Detects Maya commands and generates appropriate documentation URLs.
"""

import re
from typing import Optional
import webbrowser


class MayaHelpDetector:
    """Detector for Maya commands to generate help URLs."""

    # Maya module aliases and their actual module names
    MAYA_ALIASES = {
        "cmds": "maya.cmds",
        "mc": "maya.cmds",
        "pm": "pymel.core",
        "pmc": "pymel.core",
        "pymel": "pymel.core",
        "om": "maya.api.OpenMaya",
        "OpenMaya": "maya.api.OpenMaya",
        "omu": "maya.api.OpenMayaUI",
        "OpenMayaUI": "maya.api.OpenMayaUI",
        "oma": "maya.api.OpenMayaAnim",
        "OpenMayaAnim": "maya.api.OpenMayaAnim",
        "omr": "maya.api.OpenMayaRender",
        "OpenMayaRender": "maya.api.OpenMayaRender",
    }

    # Supported Maya documentation languages
    SUPPORTED_LANGUAGES = {
        "ENU": "ENU",  # English
        "JPN": "JPN",  # Japanese
        "CHS": "CHS",  # Chinese Simplified
        "CHT": "CHT",  # Chinese Traditional
        "KOR": "KOR",  # Korean
        "DEU": "DEU",  # German
        "FRA": "FRA",  # French
        "ITA": "ITA",  # Italian
        "SPA": "SPA",  # Spanish
        "PTB": "PTB",  # Portuguese (Brazil)
    }

    def __init__(self, settings_manager=None):
        """Initialize the Maya help detector."""
        self.settings_manager = settings_manager
        self._maya_version = None
        self._language = None

    def detect_maya_command_at_cursor(self, text: str, cursor_position: int) -> Optional[tuple[str, str, str]]:
        """
        Detect Maya command at cursor position.

        Args:
            text: Full text content
            cursor_position: Cursor position in text

        Returns:
            Tuple of (alias, command, full_match) if found, None otherwise
        """
        if not text or cursor_position < 0 or cursor_position > len(text):
            return None

        # Find the current line
        lines = text[:cursor_position].split("\n")
        current_line = lines[-1] if lines else ""

        # Get full current line (including part after cursor)
        remaining_text = text[cursor_position:]
        next_newline = remaining_text.find("\n")
        if next_newline != -1:
            full_line = current_line + remaining_text[:next_newline]
        else:
            full_line = current_line + remaining_text

        # Position within the current line
        cursor_in_line = len(current_line)

        # Pattern to match module.command format
        # Matches: alias.command where alias is known Maya module
        pattern = r"\b(" + "|".join(self.MAYA_ALIASES.keys()) + r")\.([a-zA-Z_][a-zA-Z0-9_]*)\b"

        for match in re.finditer(pattern, full_line):
            start_pos = match.start()
            end_pos = match.end()

            # Check if cursor is within this match
            if start_pos <= cursor_in_line <= end_pos:
                alias = match.group(1)
                command = match.group(2)
                full_match = match.group(0)

                return (alias, command, full_match)

        return None

    def get_maya_version(self) -> str:
        """Get Maya version from currently running Maya instance."""
        if self._maya_version is not None:
            return self._maya_version

        try:
            # Try to get version from Maya
            import maya.cmds as cmds  # type: ignore

            version_string = cmds.about(version=True)

            # Extract year from version string (e.g., "2025.3" -> "2025")
            if version_string:
                # Handle formats like "2025.3", "2025", "Maya 2025", etc.
                import re

                version_match = re.search(r"(\d{4})", version_string)
                if version_match:
                    self._maya_version = version_match.group(1)
                    return self._maya_version

        except ImportError:
            pass
        except Exception:
            pass

        # Auto-detection disabled or failed - use default
        self._maya_version = "2025"  # Default version
        return self._maya_version

    def get_language(self) -> str:
        """Get language setting from general interface language or use default."""
        if self._language is not None:
            return self._language

        # Get language from general interface settings
        if self.settings_manager:
            language = self.settings_manager.get_interface_language()
        else:
            language = "JPN"  # Default to Japanese

        # Validate language and fallback to Japanese if invalid
        if language not in self.SUPPORTED_LANGUAGES:
            language = "JPN"

        self._language = language
        return self._language

    def generate_help_url(self, alias: str, command: str) -> Optional[str]:
        """
        Generate help URL for Maya command.

        Args:
            alias: Module alias (e.g., 'cmds', 'mc', 'pm')
            command: Command name (e.g., 'polyCube', 'ls')

        Returns:
            Help URL string if available, None otherwise
        """
        module = self.MAYA_ALIASES.get(alias)
        if not module:
            return None

        # Get version and language settings
        version = self.get_maya_version()
        language = self.get_language()

        if module == "maya.cmds":
            # Maya Commands Reference - use user's language setting
            base_url = f"https://help.autodesk.com/cloudhelp/{version}/{language}/Maya-Tech-Docs"
            return f"{base_url}/CommandsPython/{command}.html"

        if module == "pymel.core":
            # PyMel Documentation - comprehensive API reference only available until 2023
            # For 2024+, fall back to general PyMel search since detailed API docs are not available
            if int(version) <= 2023:
                base_url = f"https://help.autodesk.com/cloudhelp/{version}/ENU/Maya-Tech-Docs"
                return f"{base_url}/PyMel/generated/functions/pymel.core.general/pymel.core.general.{command}.html"
            # For 2024+, direct to PyMel installation/usage guide or search
            return f"https://help.autodesk.com/view/MAYAUL/{version}/ENU/?guid=GUID-2AA5EFCE-53B1-46A0-8E43-4CD0B2C72FB4"

        if module.startswith("maya.api.OpenMaya") or module.startswith("maya.OpenMaya"):
            # Maya API Documentation - try to link directly to specific class
            class_url = self._generate_openmp_class_url(command, version)
            if class_url:
                return class_url
            # Fallback to main API reference
            return f"https://help.autodesk.com/view/MAYADEV/{version}/ENU/?guid=MAYA_API_REF_py_ref_index_html"

        return None

    def _generate_openmp_class_url(self, class_name: str, version: str) -> Optional[str]:
        """Generate direct URL for OpenMaya API class documentation."""
        # Use language setting for OpenMaya docs (some languages may be available)
        language = self.get_language()

        # Detect module based on class name patterns
        module = self._detect_openmaya_module(class_name)

        # Convert class name to URL format using algorithmic approach
        url_class_name = self._convert_class_name_to_url_format_algorithmic(class_name)
        if not url_class_name:
            return None

        # Convert module name to URL format
        url_module = self._convert_module_name_to_url_format(module)

        # Use cloudhelp format for better reliability
        base_url = f"https://help.autodesk.com/cloudhelp/{version}/{language}/MAYA-API-REF/py_ref/"
        return f"{base_url}class_{url_module}_1_1_{url_class_name}.html"

    def _detect_openmaya_module(self, class_name: str) -> str:
        """Detect OpenMaya module based on class name patterns."""
        # Animation-related classes
        if any(pattern in class_name for pattern in ["Anim", "Keyframe", "Motion"]):
            return "OpenMayaAnim"

        # UI-related classes
        if any(pattern in class_name for pattern in ["UI", "View", "3dView", "Select"]):
            return "OpenMayaUI"

        # Rendering-related classes
        if any(pattern in class_name for pattern in ["Render", "Shader", "Material", "Light", "Camera"]):
            return "OpenMayaRender"

        # Default to OpenMaya for core classes
        return "OpenMaya"

    def _convert_module_name_to_url_format(self, module_name: str) -> str:
        """Convert module name to URL format."""
        if module_name == "OpenMayaUI":
            return "open_maya_u_i"
        # OpenMaya -> open_maya, OpenMayaAnim -> open_maya_anim, etc.
        import re

        return re.sub(r"(?<!^)(?=[A-Z])", "_", module_name).lower()

    def _convert_class_name_to_url_format_algorithmic(self, class_name: str) -> Optional[str]:
        """Convert Maya class name to URL format using algorithmic approach."""
        if not class_name or not class_name.startswith("M"):
            return None

        # Use regex to convert CamelCase to snake_case
        import re

        # MColor -> m_color, MFnMesh -> m_fn_mesh, MDagPath -> m_dag_path
        return re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()

    def _convert_class_name_to_url_format(self, class_name: str) -> Optional[str]:
        """
        Convert Maya class name to URL format (legacy method for backward compatibility).
        Now delegates to the algorithmic approach.
        """
        return self._convert_class_name_to_url_format_algorithmic(class_name)

    def get_fallback_search_url(self, alias: str, command: str) -> str:
        """
        Generate fallback search URL if specific documentation is not found.

        Args:
            alias: Module alias
            command: Command name

        Returns:
            Search URL for Maya documentation
        """
        # Get version and language settings
        version = self.get_maya_version()
        language = self.get_language()

        search_term = f"maya {alias} {command}"
        return f"https://help.autodesk.com/view/MAYAUL/{version}/{language}/?query={search_term}"

    def open_help_url(self, alias: str, command: str) -> bool:
        """
        Open help URL in default browser with fallback to English.

        Args:
            alias: Module alias
            command: Command name

        Returns:
            True if URL was opened successfully, False otherwise
        """
        try:
            url = self.generate_help_url(alias, command)
            if url:
                success = self._try_open_url_with_fallback(url, alias, command)
                if success:
                    return True

            # Try fallback search if direct URL fails
            fallback_url = self.get_fallback_search_url(alias, command)
            webbrowser.open(fallback_url)
            return True

        except Exception as e:
            print(f"Error opening Maya help URL: {e}")
            # Last resort: try English documentation
            try:
                english_url = self._generate_english_fallback_url(alias, command)
                if english_url:
                    webbrowser.open(english_url)
                    return True
            except Exception:
                pass
            return False

    def _try_open_url_with_fallback(self, url: str, alias: str, command: str) -> bool:
        """Try to open URL, fallback to English if the language page doesn't exist."""
        try:
            # Try to open the URL
            webbrowser.open(url)
            return True
        except Exception:
            # If URL fails and we're not already using English, try English
            current_language = self.get_language()
            if current_language != "ENU":
                try:
                    english_url = self._generate_english_fallback_url(alias, command)
                    if english_url:
                        webbrowser.open(english_url)
                        print(f"Maya Help: Fallback to English documentation for {alias}.{command}")
                        return True
                except Exception:
                    pass
            return False

    def _generate_english_fallback_url(self, alias: str, command: str) -> Optional[str]:
        """Generate English fallback URL."""
        module = self.MAYA_ALIASES.get(alias)
        if not module:
            return None

        version = self.get_maya_version()

        if module == "maya.cmds":
            base_url = f"https://help.autodesk.com/cloudhelp/{version}/ENU/Maya-Tech-Docs"
            return f"{base_url}/CommandsPython/{command}.html"
        if module == "pymel.core":
            if int(version) <= 2023:
                base_url = f"https://help.autodesk.com/cloudhelp/{version}/ENU/Maya-Tech-Docs"
                return f"{base_url}/PyMel/generated/functions/pymel.core.general/pymel.core.general.{command}.html"
            return f"https://help.autodesk.com/view/MAYAUL/{version}/ENU/?guid=GUID-2AA5EFCE-53B1-46A0-8E43-4CD0B2C72FB4"
        if module.startswith("maya.api.OpenMaya") or module.startswith("maya.OpenMaya"):
            # Try direct class URL first, fallback to main API reference
            class_url = self._generate_openmp_class_url(command, version)
            if class_url:
                return class_url
            return f"https://help.autodesk.com/view/MAYADEV/{version}/ENU/?guid=MAYA_API_REF_py_ref_index_html"

        return None

    def get_help_menu_text(self, alias: str, command: str) -> str:
        """
        Get context menu text for Maya help.

        Args:
            alias: Module alias
            command: Command name

        Returns:
            Menu text string
        """
        module = self.MAYA_ALIASES.get(alias, alias)

        if module == "maya.cmds":
            return f"Maya Help: {command}()"
        if module == "pymel.core":
            return f"PyMel Help: {command}()"
        if "OpenMaya" in module:
            return f"Maya API Help: {command}"
        return f"Maya Help: {alias}.{command}"
