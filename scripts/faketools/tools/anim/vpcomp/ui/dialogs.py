"""Add-layer dialogs extracted from ui.py."""

from __future__ import annotations

from .....lib_ui.qt_compat import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    Qt,
    QVBoxLayout,
)
from ..core.model import FitMode
from ..core.scene_queries import list_user_cameras
from ..core.sequence_detect import detect_sequence
from .resource_utils import load_qss


def _apply_qss(widget) -> None:
    """Load and apply the shared dark-theme QSS to *widget*."""
    widget.setStyleSheet(load_qss())


_FIT_MODE_LABELS: dict[FitMode, str] = {
    FitMode.VIEWPORT_HEIGHT: "Viewport Height",
    FitMode.VIEWPORT_WIDTH: "Viewport Width",
    FitMode.FILMGATE_HEIGHT: "FilmGate Height",
    FitMode.FILMGATE_WIDTH: "FilmGate Width",
}

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg);;PNG (*.png);;JPEG (*.jpg *.jpeg)"


class AddCameraDialog(QDialog):
    """Dialog to select a camera for a new CameraLayer."""

    def __init__(self, cameras_in_use: set[str], parent=None):
        super().__init__(parent)
        _apply_qss(self)
        self.setWindowTitle("Add Camera Layer")
        self.setMinimumWidth(280)

        self.selected_camera: str | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Camera:"))
        self._combo = QComboBox()
        all_cams = list_user_cameras()
        available = [c for c in all_cams if c not in cameras_in_use]
        if not available:
            self._combo.addItem("(no cameras available)")
            self._combo.setEnabled(False)
        else:
            for cam in available:
                self._combo.addItem(cam)
        layout.addWidget(self._combo)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _accept(self):
        if self._combo.isEnabled():
            self.selected_camera = self._combo.currentText()
            self.accept()


class AddImageDialog(QDialog):
    """Dialog to select an image file and FitMode for a new ImageLayer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_qss(self)
        self.setWindowTitle("Add Image Layer")
        self.setMinimumWidth(400)

        self.selected_path: str | None = None
        self.selected_fit: FitMode = FitMode.VIEWPORT_HEIGHT

        layout = QVBoxLayout(self)

        # Grid for File / Fit Mode rows
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)

        file_label = QLabel("File:")
        file_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(file_label, 0, 0)

        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("(none)")
        grid.addWidget(self._path_edit, 0, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        grid.addWidget(browse_btn, 0, 2)

        fit_label = QLabel("Fit Mode:")
        fit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(fit_label, 1, 0)

        self._fit_combo = QComboBox()
        for fm in FitMode:
            self._fit_combo.addItem(_FIT_MODE_LABELS[fm], fm)
        grid.addWidget(self._fit_combo, 1, 1, 1, 2)

        layout.addLayout(grid)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancel")
        self._ok_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", IMAGE_FILTER)
        if path:
            self._path_edit.setText(path)
            self.selected_path = path
            self._ok_btn.setEnabled(True)

    def _accept(self):
        if self.selected_path:
            self.selected_fit = self._fit_combo.currentData()
            self.accept()


class AddSequenceDialog(QDialog):
    """Dialog to select a sequence sample file and FitMode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_qss(self)
        self.setWindowTitle("Add Sequence Layer")
        self.setMinimumWidth(400)

        self.seq_info = None  # SequenceInfo | None
        self.selected_fit: FitMode = FitMode.VIEWPORT_HEIGHT

        layout = QVBoxLayout(self)

        # Grid for File / Fit Mode rows
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)

        file_label = QLabel("File:")
        file_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(file_label, 0, 0)

        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("(none)")
        grid.addWidget(self._path_edit, 0, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        grid.addWidget(browse_btn, 0, 2)

        fit_label = QLabel("Fit Mode:")
        fit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(fit_label, 1, 0)

        self._fit_combo = QComboBox()
        for fm in FitMode:
            self._fit_combo.addItem(_FIT_MODE_LABELS[fm], fm)
        grid.addWidget(self._fit_combo, 1, 1, 1, 2)

        layout.addLayout(grid)

        # Info label (hidden until sequence detected)
        self._info_label = QLabel("")
        self._info_label.hide()
        layout.addWidget(self._info_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancel")
        self._ok_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Sequence File", "", IMAGE_FILTER)
        if not path:
            return
        self._path_edit.setText(path)
        info = detect_sequence(path)
        if info is None:
            self._info_label.setText("No sequence pattern detected.")
            self._info_label.show()
            self._ok_btn.setEnabled(False)
            self.seq_info = None
            return
        self.seq_info = info
        self._info_label.show()
        self._info_label.setText(f"Pattern: {info.file_pattern}  Frames: {info.frame_start}-{info.frame_end} ({info.frame_count})")
        self._ok_btn.setEnabled(True)

    def _accept(self):
        if self.seq_info:
            self.selected_fit = self._fit_combo.currentData()
            self.accept()
