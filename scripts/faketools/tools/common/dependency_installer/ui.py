"""Dependency Installer UI.

Supports both Maya-embedded and standalone (mayapy) launch modes.
"""

from __future__ import annotations

from logging import getLogger
import sys

from . import command

logger = getLogger(__name__)

_instance = None
_is_standalone = False


def _detect_standalone():
    """Detect if running in standalone mode (outside Maya)."""
    try:
        import maya.cmds  # noqa: F401

        return False
    except ImportError:
        return True


def _create_maya_window():
    """Create and return a Maya-embedded MainWindow."""
    from ....lib_ui.base_window import BaseMainWindow
    from ....lib_ui.maya_decorator import error_handler
    from ....lib_ui.maya_qt import get_maya_main_window
    from ....lib_ui.qt_compat import (
        QApplication,
        QComboBox,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QRadioButton,
        Qt,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
    )
    from ....lib_ui.ui_utils import get_relative_size

    class MainWindow(BaseMainWindow):
        """Dependency Installer Main Window (Maya mode)."""

        def __init__(self, parent=None):
            super().__init__(
                parent=parent,
                object_name="DependencyInstallerMainWindow",
                window_title="Dependency Installer",
                central_layout="vertical",
            )
            self._setup_ui()
            self._refresh_packages()

        def _setup_ui(self):
            """Build the UI layout."""
            # --- Maya Version ---
            version_layout = QHBoxLayout()
            version_layout.addWidget(QLabel("Maya Version:"))
            self._version_combo = QComboBox()
            versions = command.discover_maya_versions()
            self._version_combo.addItems(versions)
            current = command.get_current_maya_version()
            if current and current in versions:
                self._version_combo.setCurrentText(current)
            version_layout.addWidget(self._version_combo, stretch=1)
            self.central_layout.addLayout(version_layout)

            # --- Install Location ---
            location_group = QGroupBox("Install Location")
            location_layout = QVBoxLayout()

            self._radio_standard = QRadioButton("Standard (Maya site-packages)")
            self._radio_standard.setChecked(True)
            location_layout.addWidget(self._radio_standard)

            self._radio_custom = QRadioButton("Custom path")
            location_layout.addWidget(self._radio_custom)

            custom_path_layout = QHBoxLayout()
            self._custom_path_edit = QLineEdit()
            self._custom_path_edit.setPlaceholderText("Select custom install directory...")
            self._custom_path_edit.setEnabled(False)
            custom_path_layout.addWidget(self._custom_path_edit, stretch=1)
            self._browse_button = QPushButton("Browse...")
            self._browse_button.setEnabled(False)
            self._browse_button.clicked.connect(self._browse_custom_path)
            custom_path_layout.addWidget(self._browse_button)
            location_layout.addLayout(custom_path_layout)

            self._resolved_path_label = QLabel("")
            self._resolved_path_label.setStyleSheet("color: gray;")
            location_layout.addWidget(self._resolved_path_label)

            location_group.setLayout(location_layout)
            self.central_layout.addWidget(location_group)

            self._radio_custom.toggled.connect(self._on_location_toggled)
            self._custom_path_edit.textChanged.connect(self._update_resolved_path)
            self._version_combo.currentTextChanged.connect(self._update_resolved_path)

            # --- Proxy (collapsible) ---
            self._proxy_group = QGroupBox("Proxy Settings")
            self._proxy_group.setCheckable(True)
            self._proxy_group.setChecked(False)
            proxy_layout = QVBoxLayout()

            http_layout = QHBoxLayout()
            http_layout.addWidget(QLabel("HTTP_PROXY:"))
            self._http_proxy_edit = QLineEdit()
            self._http_proxy_edit.setPlaceholderText("http://user:pass@proxy:3128")
            http_layout.addWidget(self._http_proxy_edit, stretch=1)
            proxy_layout.addLayout(http_layout)

            https_layout = QHBoxLayout()
            https_layout.addWidget(QLabel("HTTPS_PROXY:"))
            self._https_proxy_edit = QLineEdit()
            self._https_proxy_edit.setPlaceholderText("http://user:pass@proxy:3128")
            https_layout.addWidget(self._https_proxy_edit, stretch=1)
            proxy_layout.addLayout(https_layout)

            self._proxy_group.setLayout(proxy_layout)
            self.central_layout.addWidget(self._proxy_group)

            # --- Package Table ---
            self._tree = QTreeWidget()
            self._tree.setHeaderLabels(["Package", "Status", "Version", "Required By", "Location"])
            self._tree.setRootIsDecorated(False)
            header = self._tree.header()
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.Stretch)
            self.central_layout.addWidget(self._tree, stretch=1)

            # --- Buttons ---
            button_layout = QHBoxLayout()
            self._select_all_button = QPushButton("Select All Missing")
            self._select_all_button.clicked.connect(self._select_all_missing)
            button_layout.addWidget(self._select_all_button)

            self._install_button = QPushButton("Install Selected")
            self._install_button.clicked.connect(self._on_install)
            button_layout.addWidget(self._install_button)

            self._refresh_button = QPushButton("Refresh")
            self._refresh_button.clicked.connect(self._refresh_packages)
            button_layout.addWidget(self._refresh_button)
            self.central_layout.addLayout(button_layout)

            # --- Status ---
            self._status_label = QLabel("Ready.")
            self.central_layout.addWidget(self._status_label)

            # --- Window size ---
            width, height = get_relative_size(self, width_ratio=3.0, height_ratio=2.0)
            self.resize(width, height)

        def _on_location_toggled(self, checked):
            """Enable/disable custom path widgets."""
            self._custom_path_edit.setEnabled(checked)
            self._browse_button.setEnabled(checked)
            self._update_resolved_path()

        def _browse_custom_path(self):
            """Open a directory browser for the custom path."""
            path = QFileDialog.getExistingDirectory(self, "Select Install Directory", self._custom_path_edit.text())
            if path:
                self._custom_path_edit.setText(path)

        def _update_resolved_path(self):
            """Update the resolved target path label."""
            if self._radio_custom.isChecked() and self._custom_path_edit.text():
                version = self._version_combo.currentText()
                resolved = f"{self._custom_path_edit.text()}/{version}/site-packages"
                self._resolved_path_label.setText(f"Target: {resolved}")
            else:
                self._resolved_path_label.setText("")

        def _get_mayapy_path(self) -> str | None:
            """Resolve the mayapy path for the currently selected Maya version."""
            version = self._version_combo.currentText()
            if not version:
                return None
            return command.get_mayapy_path(version)

        def _is_current_maya_selected(self) -> bool:
            """Check if the selected Maya version matches the running Maya."""
            current = command.get_current_maya_version()
            return current is not None and current == self._version_combo.currentText()

        def _refresh_packages(self):
            """Refresh the package status table.

            If the selected version matches the running Maya, checks
            in-process so that paths added by userSetup.py are respected.
            Otherwise, checks via subprocess with the target mayapy.
            """
            self._tree.clear()
            maya_version = self._version_combo.currentText() or None
            if self._is_current_maya_selected():
                mayapy_path = None
            else:
                mayapy_path = self._get_mayapy_path()
            statuses = command.get_all_package_statuses(mayapy_path=mayapy_path, maya_version=maya_version)
            for pkg in statuses:
                item = QTreeWidgetItem()
                pip_spec = command.get_pip_spec(pkg)
                item.setText(0, pkg["pip_name"])
                item.setData(0, Qt.UserRole, pip_spec)

                if pkg["installed"]:
                    item.setText(1, "Installed")
                    item.setText(2, pkg["version"] or "")
                    item.setForeground(1, Qt.green)
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                    item.setText(4, pkg.get("location") or "")
                else:
                    item.setText(1, "Missing")
                    item.setText(2, "")
                    if pkg["optional"]:
                        item.setForeground(1, Qt.darkYellow)
                    else:
                        item.setForeground(1, Qt.red)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)

                item.setText(3, ", ".join(pkg["required_by"]))
                self._tree.addTopLevelItem(item)

            self._status_label.setText("Package status refreshed.")

        def _select_all_missing(self):
            """Select all missing (unchecked) packages."""
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item.text(1) == "Missing":
                    item.setCheckState(0, Qt.Checked)

        def _get_selected_packages(self) -> list[str]:
            """Get list of checked pip install specifiers."""
            selected = []
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item.checkState(0) == Qt.Checked:
                    selected.append(item.data(0, Qt.UserRole))
            return selected

        def _get_target_path(self) -> str | None:
            """Get the resolved target install path, or None for standard."""
            if self._radio_custom.isChecked() and self._custom_path_edit.text():
                version = self._version_combo.currentText()
                return f"{self._custom_path_edit.text()}/{version}/site-packages"
            return None

        def _get_proxy(self) -> dict | None:
            """Get proxy settings, or None if disabled."""
            if not self._proxy_group.isChecked():
                return None
            http_val = self._http_proxy_edit.text().strip()
            https_val = self._https_proxy_edit.text().strip()
            if not http_val and not https_val:
                return None
            proxy = {}
            if http_val:
                proxy["http"] = http_val
            if https_val:
                proxy["https"] = https_val
            return proxy

        @error_handler
        def _on_install(self):
            """Run pip install for selected packages."""
            packages = self._get_selected_packages()
            if not packages:
                self._status_label.setText("No packages selected.")
                return

            mayapy_path = self._get_mayapy_path()
            if not mayapy_path:
                self._status_label.setText("No Maya version selected or mayapy not found.")
                return

            if not command.ensure_pip_available(mayapy_path):
                version = self._version_combo.currentText()
                self._status_label.setText(f"pip not available for Maya {version}. Run: mayapy -m ensurepip")
                return

            target_path = self._get_target_path()
            proxy = self._get_proxy()

            self._status_label.setStyleSheet("")
            self._status_label.setText(f"Installing {len(packages)} package(s)...")
            self._install_button.setEnabled(False)
            QApplication.processEvents()

            result = command.install_packages(packages, mayapy_path, target_path=target_path, proxy=proxy, show_terminal=True)

            self._install_button.setEnabled(True)
            if result["success"]:
                self._status_label.setStyleSheet("")
                self._status_label.setText(f"Successfully installed: {', '.join(result['installed'])}")
            else:
                failed_names = [f["name"] for f in result["failed"]]
                self._status_label.setStyleSheet("color: red;")
                self._status_label.setText(f"Install failed for: {', '.join(failed_names)}")
                if result["stderr"]:
                    logger.error("pip stderr:\n%s", result["stderr"])

            self._refresh_packages()

    parent = get_maya_main_window()
    return MainWindow(parent)


def _create_standalone_window():
    """Create and return a standalone MainWindow (no Maya dependency)."""
    # Import directly from PySide bundled with mayapy
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPushButton,
            QRadioButton,
            QTreeWidget,
            QTreeWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        from PySide2.QtCore import Qt
        from PySide2.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPushButton,
            QRadioButton,
            QTreeWidget,
            QTreeWidgetItem,
            QVBoxLayout,
            QWidget,
        )

    class StandaloneWindow(QMainWindow):
        """Dependency Installer Window (standalone mode)."""

        def __init__(self):
            super().__init__()
            self.setWindowTitle("FakeTools Dependency Installer")
            self.setAttribute(Qt.WA_DeleteOnClose)

            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            self.central_layout = QVBoxLayout()
            self.central_widget.setLayout(self.central_layout)

            self._setup_ui()
            self._refresh_packages()

        def _setup_ui(self):
            """Build the UI layout."""
            # --- Maya Version ---
            version_layout = QHBoxLayout()
            version_layout.addWidget(QLabel("Maya Version:"))
            self._version_combo = QComboBox()
            versions = command.discover_maya_versions()
            self._version_combo.addItems(versions)
            if versions:
                self._version_combo.setCurrentIndex(len(versions) - 1)
            version_layout.addWidget(self._version_combo, stretch=1)
            self.central_layout.addLayout(version_layout)

            # --- Install Location ---
            location_group = QGroupBox("Install Location")
            location_layout = QVBoxLayout()

            self._radio_standard = QRadioButton("Standard (Maya site-packages)")
            self._radio_standard.setChecked(True)
            location_layout.addWidget(self._radio_standard)

            self._radio_custom = QRadioButton("Custom path")
            location_layout.addWidget(self._radio_custom)

            custom_path_layout = QHBoxLayout()
            self._custom_path_edit = QLineEdit()
            self._custom_path_edit.setPlaceholderText("Select custom install directory...")
            self._custom_path_edit.setEnabled(False)
            custom_path_layout.addWidget(self._custom_path_edit, stretch=1)
            self._browse_button = QPushButton("Browse...")
            self._browse_button.setEnabled(False)
            self._browse_button.clicked.connect(self._browse_custom_path)
            custom_path_layout.addWidget(self._browse_button)
            location_layout.addLayout(custom_path_layout)

            self._resolved_path_label = QLabel("")
            self._resolved_path_label.setStyleSheet("color: gray;")
            location_layout.addWidget(self._resolved_path_label)

            location_group.setLayout(location_layout)
            self.central_layout.addWidget(location_group)

            self._radio_custom.toggled.connect(self._on_location_toggled)
            self._custom_path_edit.textChanged.connect(self._update_resolved_path)
            self._version_combo.currentTextChanged.connect(self._update_resolved_path)

            # --- Proxy (collapsible) ---
            self._proxy_group = QGroupBox("Proxy Settings")
            self._proxy_group.setCheckable(True)
            self._proxy_group.setChecked(False)
            proxy_layout = QVBoxLayout()

            http_layout = QHBoxLayout()
            http_layout.addWidget(QLabel("HTTP_PROXY:"))
            self._http_proxy_edit = QLineEdit()
            self._http_proxy_edit.setPlaceholderText("http://user:pass@proxy:3128")
            http_layout.addWidget(self._http_proxy_edit, stretch=1)
            proxy_layout.addLayout(http_layout)

            https_layout = QHBoxLayout()
            https_layout.addWidget(QLabel("HTTPS_PROXY:"))
            self._https_proxy_edit = QLineEdit()
            self._https_proxy_edit.setPlaceholderText("http://user:pass@proxy:3128")
            https_layout.addWidget(self._https_proxy_edit, stretch=1)
            proxy_layout.addLayout(https_layout)

            self._proxy_group.setLayout(proxy_layout)
            self.central_layout.addWidget(self._proxy_group)

            # --- Package Table ---
            self._tree = QTreeWidget()
            self._tree.setHeaderLabels(["Package", "Status", "Version", "Required By", "Location"])
            self._tree.setRootIsDecorated(False)
            header = self._tree.header()
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.Stretch)
            self.central_layout.addWidget(self._tree, stretch=1)

            # --- Buttons ---
            button_layout = QHBoxLayout()
            self._select_all_button = QPushButton("Select All Missing")
            self._select_all_button.clicked.connect(self._select_all_missing)
            button_layout.addWidget(self._select_all_button)

            self._install_button = QPushButton("Install Selected")
            self._install_button.clicked.connect(self._on_install)
            button_layout.addWidget(self._install_button)

            self._refresh_button = QPushButton("Refresh")
            self._refresh_button.clicked.connect(self._refresh_packages)
            button_layout.addWidget(self._refresh_button)
            self.central_layout.addLayout(button_layout)

            # --- Status ---
            self._status_label = QLabel("Ready.")
            self.central_layout.addWidget(self._status_label)

            self.resize(900, 500)

        def _on_location_toggled(self, checked):
            """Enable/disable custom path widgets."""
            self._custom_path_edit.setEnabled(checked)
            self._browse_button.setEnabled(checked)
            self._update_resolved_path()

        def _browse_custom_path(self):
            """Open a directory browser for the custom path."""
            path = QFileDialog.getExistingDirectory(self, "Select Install Directory", self._custom_path_edit.text())
            if path:
                self._custom_path_edit.setText(path)

        def _update_resolved_path(self):
            """Update the resolved target path label."""
            if self._radio_custom.isChecked() and self._custom_path_edit.text():
                version = self._version_combo.currentText()
                resolved = f"{self._custom_path_edit.text()}/{version}/site-packages"
                self._resolved_path_label.setText(f"Target: {resolved}")
            else:
                self._resolved_path_label.setText("")

        def _get_mayapy_path(self) -> str | None:
            """Resolve the mayapy path for the currently selected Maya version."""
            version = self._version_combo.currentText()
            if not version:
                return None
            return command.get_mayapy_path(version)

        def _refresh_packages(self):
            """Refresh the package status table via the selected Maya's mayapy."""
            self._tree.clear()
            maya_version = self._version_combo.currentText() or None
            mayapy_path = self._get_mayapy_path()
            statuses = command.get_all_package_statuses(mayapy_path=mayapy_path, maya_version=maya_version)
            for pkg in statuses:
                item = QTreeWidgetItem()
                pip_spec = command.get_pip_spec(pkg)
                item.setText(0, pkg["pip_name"])
                item.setData(0, Qt.UserRole, pip_spec)

                if pkg["installed"]:
                    item.setText(1, "Installed")
                    item.setText(2, pkg["version"] or "")
                    item.setForeground(1, Qt.green)
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                    item.setText(4, pkg.get("location") or "")
                else:
                    item.setText(1, "Missing")
                    item.setText(2, "")
                    if pkg["optional"]:
                        item.setForeground(1, Qt.darkYellow)
                    else:
                        item.setForeground(1, Qt.red)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)

                item.setText(3, ", ".join(pkg["required_by"]))
                self._tree.addTopLevelItem(item)

            self._status_label.setText("Package status refreshed.")

        def _select_all_missing(self):
            """Select all missing (unchecked) packages."""
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item.text(1) == "Missing":
                    item.setCheckState(0, Qt.Checked)

        def _get_selected_packages(self) -> list[str]:
            """Get list of checked pip install specifiers."""
            selected = []
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item.checkState(0) == Qt.Checked:
                    selected.append(item.data(0, Qt.UserRole))
            return selected

        def _get_target_path(self) -> str | None:
            """Get the resolved target install path, or None for standard."""
            if self._radio_custom.isChecked() and self._custom_path_edit.text():
                version = self._version_combo.currentText()
                return f"{self._custom_path_edit.text()}/{version}/site-packages"
            return None

        def _get_proxy(self) -> dict | None:
            """Get proxy settings, or None if disabled."""
            if not self._proxy_group.isChecked():
                return None
            http_val = self._http_proxy_edit.text().strip()
            https_val = self._https_proxy_edit.text().strip()
            if not http_val and not https_val:
                return None
            proxy = {}
            if http_val:
                proxy["http"] = http_val
            if https_val:
                proxy["https"] = https_val
            return proxy

        def _on_install(self):
            """Run pip install for selected packages."""
            packages = self._get_selected_packages()
            if not packages:
                self._status_label.setText("No packages selected.")
                return

            mayapy_path = self._get_mayapy_path()
            if not mayapy_path:
                self._status_label.setText("No Maya version selected or mayapy not found.")
                return

            if not command.ensure_pip_available(mayapy_path):
                version = self._version_combo.currentText()
                self._status_label.setText(f"pip not available for Maya {version}. Run: mayapy -m ensurepip")
                return

            target_path = self._get_target_path()
            proxy = self._get_proxy()

            self._status_label.setStyleSheet("")
            self._status_label.setText(f"Installing {len(packages)} package(s)...")
            self._install_button.setEnabled(False)
            QApplication.processEvents()

            result = command.install_packages(packages, mayapy_path, target_path=target_path, proxy=proxy, show_terminal=True)

            self._install_button.setEnabled(True)
            if result["success"]:
                self._status_label.setStyleSheet("")
                self._status_label.setText(f"Successfully installed: {', '.join(result['installed'])}")
            else:
                failed_names = [f["name"] for f in result["failed"]]
                self._status_label.setStyleSheet("color: red;")
                self._status_label.setText(f"Install failed for: {', '.join(failed_names)}")
                if result["stderr"]:
                    logger.error("pip stderr:\n%s", result["stderr"])

            self._refresh_packages()

    return StandaloneWindow()


def show_ui():
    """Show the Dependency Installer UI.

    Creates or raises the main window. Works both inside Maya
    and in standalone mode (via mayapy).

    Returns:
        The main window instance.
    """
    global _instance, _is_standalone

    if _instance is not None:
        try:
            _instance.close()
            _instance.deleteLater()
        except RuntimeError:
            pass

    _is_standalone = _detect_standalone()

    if _is_standalone:
        _instance = _create_standalone_window()
    else:
        _instance = _create_maya_window()

    _instance.show()
    return _instance


def main():
    """Entry point for standalone execution."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        from PySide2.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = _create_standalone_window()
    window.show()
    sys.exit(app.exec() if hasattr(app, "exec") else app.exec_())


if __name__ == "__main__":
    main()


__all__ = ["show_ui", "main"]
