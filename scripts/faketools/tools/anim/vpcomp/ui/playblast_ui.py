"""Playblast composite settings window.

Provides a dialog for configuring and executing layer-based playblast
compositing with Pillow.
"""

from __future__ import annotations

from logging import getLogger
import os

import maya.cmds as cmds  # type: ignore

from .....lib_ui.base_window import get_margins, get_spacing
from .....lib_ui.qt_compat import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QEvent,
    QFileDialog,
    QFont,
    QFontMetrics,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPainter,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSize,
    QSpinBox,
    QStyledItemDelegate,
    Qt,
    QVBoxLayout,
    QWidget,
)
from .....lib_ui.tool_settings import ToolSettingsManager
from .....lib_ui.ui_utils import get_relative_size
from ..core.ffmpeg import get_scene_fps
from ..core.model import LayerStack
from ..core.playblast import (
    DeliveryMode,
    LayerRenderConfig,
    OutputMode,
    PlayblastSettings,
    run_playblast_composite,
)
from ..core.players import get_available_players
from .colors import LAYER_TYPE_COLORS, LAYER_TYPE_FALLBACK
from .resource_utils import load_qss, make_separator

logger = getLogger(__name__)

_UI_DIR = os.path.dirname(__file__)

# Badge data roles
_BADGE_ROLE = Qt.UserRole + 1
_BADGE_COLOR_ROLE = Qt.UserRole + 2


# ------------------------------------------------------------------
# Helper widgets
# ------------------------------------------------------------------


def _make_section_header(text: str) -> QLabel:
    """Uppercase section header label."""
    lbl = QLabel(text.upper())
    lbl.setObjectName("pbSectionHeader")
    return lbl


def _form_label(text: str) -> QLabel:
    """Right-aligned fixed-width form label."""
    lbl = QLabel(text)
    lbl.setObjectName("pbFormLabel")
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    lbl.setFixedWidth(68)
    return lbl


# ------------------------------------------------------------------
# Layer delegate — type badge overlay
# ------------------------------------------------------------------


class _PlayblastLayerDelegate(QStyledItemDelegate):
    """Draws a type badge (CAM / IMG / SEQ) at the right side of each item.

    Also handles click-anywhere-to-toggle-checkbox via editorEvent.
    """

    def paint(self, painter: QPainter, option, index) -> None:
        # Log state flags for debugging hover movement
        logger.debug(
            "PB delegate paint row=%d state=%s rect=(%d,%d,%d,%d)",
            index.row(),
            option.state,
            option.rect.x(),
            option.rect.y(),
            option.rect.width(),
            option.rect.height(),
        )
        super().paint(painter, option, index)

        badge_text = index.data(_BADGE_ROLE)
        if not badge_text:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        font = painter.font()
        font.setPixelSize(9)
        font.setWeight(QFont.Medium)
        painter.setFont(font)

        fm = QFontMetrics(font)
        pad_h = 4
        pad_v = 2
        max_text_w = max(fm.horizontalAdvance(t) for t in ("CAM", "IMG", "SEQ"))
        badge_w = max_text_w + pad_h * 2  # fixed width
        badge_h = fm.height() + pad_v

        rect = option.rect
        x = rect.right() - badge_w - 8
        y = rect.center().y() - badge_h // 2

        # Use per-type color
        color_hex = index.data(_BADGE_COLOR_ROLE) or LAYER_TYPE_FALLBACK
        color = QColor(color_hex)

        # Background (12% opacity)
        bg = QColor(color)
        bg.setAlpha(30)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(x, y, badge_w, badge_h, 2, 2)

        # Text
        painter.setPen(color)
        painter.drawText(x + pad_h, y, badge_w - pad_h * 2, badge_h, Qt.AlignCenter, badge_text)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(0, 28)

    def editorEvent(self, event, model, option, index):
        """Toggle checkbox on any click within the row."""
        etype = event.type()
        if etype == QEvent.MouseButtonRelease:
            # data() returns int in PySide6, not Qt.CheckState enum
            current = index.data(Qt.CheckStateRole)
            is_checked = current == 2 or current == Qt.Checked
            new_state = Qt.Unchecked if is_checked else Qt.Checked
            model.setData(index, new_state, Qt.CheckStateRole)
            return True
        return etype == QEvent.MouseButtonPress


# ------------------------------------------------------------------
# PlayblastWindow
# ------------------------------------------------------------------


class PlayblastWindow(QDialog):
    """Playblast composite settings dialog."""

    _RENDERER_OVERRIDE_IGNORE = frozenset({"stereoOverrideVP2"})

    def __init__(
        self,
        stack: LayerStack,
        panel: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Playblast Composite")
        w, h = get_relative_size(self, width_ratio=1.4, height_ratio=1.7)
        self.setMinimumWidth(int(w * 0.95))
        self.resize(w, h)

        self._stack = stack
        self._panel = panel
        self._cancelled = False
        self._running = False
        self._settings = ToolSettingsManager(tool_name="vpcomp", category="anim")

        # Load QSS (top-level window) + combo arrow with absolute path
        css = load_qss()
        arrow = os.path.join(_UI_DIR, "icons", "combo_arrow.svg").replace("\\", "/")
        css += f'\nQComboBox::down-arrow {{ image: url("{arrow}"); width: 8px; height: 5px; }}'
        self.setStyleSheet(css)

        self._build_ui()
        self._populate_layers()
        self._update_resolution_mode()
        self._update_frame_mode()
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        m = get_margins(self)
        self._margins = (m[0], m[1] // 2, m[2], m[3] // 2)
        self._spacing = get_spacing(self, "horizontal")
        self._compact_margins = (self._margins[0], int(self._margins[1] * 0.6), self._margins[2], self._margins[3])

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_panel_section())
        root.addWidget(make_separator())
        root.addWidget(_make_section_header("Layers"))
        root.addWidget(self._build_layers_section(), 1)
        root.addWidget(make_separator())
        root.addWidget(_make_section_header("Output"))
        root.addWidget(self._build_output_section())
        root.addWidget(make_separator())
        root.addWidget(_make_section_header("Resolution"))
        root.addWidget(self._build_resolution_section())
        root.addWidget(make_separator())
        root.addWidget(_make_section_header("Frame Range"))
        root.addWidget(self._build_frame_range_section())
        root.addWidget(make_separator())
        root.addWidget(self._build_play_section())
        root.addWidget(make_separator())
        root.addWidget(self._build_progress_section())

        # Playblast button
        btn_body = QWidget()
        btn_lay = QHBoxLayout(btn_body)
        btn_lay.setContentsMargins(self._margins[0], self._margins[1], self._margins[2], self._margins[0])
        self._run_btn = QPushButton("Playblast")
        self._run_btn.setObjectName("applyBtn")
        self._run_btn.clicked.connect(self._on_run_clicked)
        btn_lay.addWidget(self._run_btn)
        root.addWidget(btn_body)

        # Connections for radio buttons
        self._res_group.buttonClicked.connect(lambda: self._update_resolution_mode())
        self._frame_group.buttonClicked.connect(lambda: self._update_frame_mode())

    def _build_panel_section(self) -> QWidget:
        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(*self._margins)
        lbl = QLabel("PANEL")
        lbl.setObjectName("panelLabel")
        lay.addWidget(lbl)
        try:
            cam = cmds.modelPanel(self._panel, q=True, cam=True)
            panel_text = f"{self._panel} ({cam})"
        except Exception:
            panel_text = self._panel
        value = QLabel(panel_text)
        value.setObjectName("pbFormLabel")
        lay.addWidget(value)
        lay.addStretch()
        return body

    def _build_layers_section(self) -> QWidget:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(*self._compact_margins)
        self._layer_list = QListWidget()
        _, min_h = get_relative_size(self, width_ratio=0.0, height_ratio=0.35)
        self._layer_list.setMinimumHeight(min_h)
        self._layer_list.setSelectionMode(QListWidget.NoSelection)
        self._layer_list.setItemDelegate(_PlayblastLayerDelegate(self._layer_list))
        lay.addWidget(self._layer_list)
        return body

    def _build_output_section(self) -> QWidget:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(*self._compact_margins)
        grid.setSpacing(self._spacing)

        # Renderer
        grid.addWidget(_form_label("Renderer"), 0, 0)
        self._renderer_combo = QComboBox()
        self._renderer_combo.addItem("Viewport 2.0", "")
        try:
            names = (
                cmds.modelEditor(
                    self._panel,
                    q=True,
                    rendererOverrideList=True,
                )
                or []
            )
            ui_names = (
                cmds.modelEditor(
                    self._panel,
                    q=True,
                    rendererOverrideListUI=True,
                )
                or []
            )
            for name, ui_name in zip(names, ui_names):
                if name not in self._RENDERER_OVERRIDE_IGNORE:
                    self._renderer_combo.addItem(ui_name, name)
        except Exception:
            logger.warning("Failed to query renderer overrides")
        grid.addWidget(self._renderer_combo, 0, 1)

        # Format
        grid.addWidget(_form_label("Format"), 1, 0)
        self._format_combo = QComboBox()
        self._format_combo.addItem("Image Sequence (PNG)", OutputMode.IMAGE_SEQUENCE)
        self._format_combo.addItem("Movie (MP4)", OutputMode.MOVIE)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        grid.addWidget(self._format_combo, 1, 1)

        # Delivery
        grid.addWidget(_form_label("Delivery"), 2, 0)
        self._delivery_combo = QComboBox()
        self._delivery_combo.addItem("Composite", DeliveryMode.COMPOSITE)
        self._delivery_combo.addItem("Per-Layer", DeliveryMode.PER_LAYER)
        self._delivery_combo.addItem("Both", DeliveryMode.BOTH)
        grid.addWidget(self._delivery_combo, 2, 1)

        # Path
        grid.addWidget(_form_label("Path"), 3, 0)
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        dir_row.addWidget(self._dir_edit, 1)
        self._browse_btn = QPushButton("Browse")
        self._browse_btn.clicked.connect(self._browse_output)
        dir_row.addWidget(self._browse_btn)
        grid.addLayout(dir_row, 3, 1)

        # Filename prefix
        grid.addWidget(_form_label("Filename"), 4, 0)
        self._prefix_edit = QLineEdit("vpcomp")
        self._prefix_edit.setPlaceholderText("e.g. vpcomp")
        grid.addWidget(self._prefix_edit, 4, 1)

        return body

    def _build_resolution_section(self) -> QWidget:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(*self._compact_margins)
        lay.setSpacing(self._spacing)

        # Radio buttons
        radio_row = QHBoxLayout()
        self._res_render_radio = QRadioButton("Render Settings")
        self._res_custom_radio = QRadioButton("Custom")
        self._res_group = QButtonGroup(self)
        self._res_group.addButton(self._res_render_radio, 0)
        self._res_group.addButton(self._res_custom_radio, 1)
        self._res_render_radio.setChecked(True)
        radio_row.addWidget(self._res_render_radio)
        radio_row.addWidget(self._res_custom_radio)
        radio_row.addStretch()
        lay.addLayout(radio_row)

        # Size row
        size_row = QHBoxLayout()
        size_row.addWidget(_form_label("Size"))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 16384)
        self._width_spin.setValue(1920)
        size_row.addWidget(self._width_spin)
        sep_lbl = QLabel("\u00d7")
        sep_lbl.setObjectName("pbSizeSep")
        sep_lbl.setFixedWidth(14)
        sep_lbl.setAlignment(Qt.AlignCenter)
        size_row.addWidget(sep_lbl)
        self._height_spin = QSpinBox()
        self._height_spin.setRange(1, 16384)
        self._height_spin.setValue(1080)
        size_row.addWidget(self._height_spin)
        lay.addLayout(size_row)

        # Scale row
        scale_row = QHBoxLayout()
        scale_row.addWidget(_form_label("Scale"))
        self._scale_spin = QSpinBox()
        self._scale_spin.setRange(1, 100)
        self._scale_spin.setValue(100)
        self._scale_spin.setSuffix(" %")
        scale_row.addWidget(self._scale_spin)
        scale_row.addStretch()
        lay.addLayout(scale_row)

        return body

    def _build_frame_range_section(self) -> QWidget:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(*self._compact_margins)
        lay.setSpacing(self._spacing)

        # Radio buttons
        radio_row = QHBoxLayout()
        self._frame_timeline_radio = QRadioButton("Timeline")
        self._frame_custom_radio = QRadioButton("Custom")
        self._frame_group = QButtonGroup(self)
        self._frame_group.addButton(self._frame_timeline_radio, 0)
        self._frame_group.addButton(self._frame_custom_radio, 1)
        self._frame_timeline_radio.setChecked(True)
        radio_row.addWidget(self._frame_timeline_radio)
        radio_row.addWidget(self._frame_custom_radio)
        radio_row.addStretch()
        lay.addLayout(radio_row)

        # Start / End row
        se_row = QHBoxLayout()
        se_row.addWidget(_form_label("Start"))
        self._start_spin = QSpinBox()
        self._start_spin.setRange(-100000, 100000)
        se_row.addWidget(self._start_spin)
        end_lbl = QLabel("End")
        end_lbl.setObjectName("pbFormLabel")
        end_lbl.setAlignment(Qt.AlignCenter)
        end_lbl.setFixedWidth(30)
        se_row.addWidget(end_lbl)
        self._end_spin = QSpinBox()
        self._end_spin.setRange(-100000, 100000)
        se_row.addWidget(self._end_spin)
        lay.addLayout(se_row)

        return body

    def _build_play_section(self) -> QWidget:
        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(*self._margins)
        self._play_cb = QCheckBox("Play after save")
        lay.addWidget(self._play_cb)
        self._player_combo = QComboBox()
        for player in get_available_players():
            self._player_combo.addItem(player.name, player)
        self._player_combo.setEnabled(False)
        lay.addWidget(self._player_combo)
        self._play_cb.toggled.connect(self._player_combo.setEnabled)
        return body

    def _build_progress_section(self) -> QWidget:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(*self._margins)
        lay.setSpacing(int(self._spacing * 0.7))
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setValue(0)
        lay.addWidget(self._progress)
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        lay.addWidget(self._status_label)
        return body

    # ------------------------------------------------------------------
    # Populate / Sync
    # ------------------------------------------------------------------

    def _populate_layers(self) -> None:
        self._layer_list.clear()
        # Display frontmost first (reversed from stack order)
        for i in range(len(self._stack) - 1, -1, -1):
            layer = self._stack[i]
            type_label = layer.layer_type.label
            item = QListWidgetItem(layer.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
            item.setData(Qt.UserRole, i)  # store stack index
            item.setData(_BADGE_ROLE, type_label)
            item.setData(_BADGE_COLOR_ROLE, LAYER_TYPE_COLORS.get(layer.layer_type, LAYER_TYPE_FALLBACK))
            self._layer_list.addItem(item)

    def _update_resolution_mode(self) -> None:
        is_render = self._res_render_radio.isChecked()
        self._width_spin.setEnabled(not is_render)
        self._height_spin.setEnabled(not is_render)
        if is_render:
            try:
                w = cmds.getAttr("defaultResolution.width")
                h = cmds.getAttr("defaultResolution.height")
                self._width_spin.setValue(w)
                self._height_spin.setValue(h)
            except Exception:
                pass

    def _update_frame_mode(self) -> None:
        is_timeline = self._frame_timeline_radio.isChecked()
        self._start_spin.setEnabled(not is_timeline)
        self._end_spin.setEnabled(not is_timeline)
        if is_timeline:
            try:
                s = int(cmds.playbackOptions(q=True, min=True))
                e = int(cmds.playbackOptions(q=True, max=True))
                self._start_spin.setValue(s)
                self._end_spin.setValue(e)
            except Exception:
                pass

    def _on_format_changed(self) -> None:
        is_movie = self._format_combo.currentData() is OutputMode.MOVIE
        if is_movie:
            self._delivery_combo.setCurrentIndex(0)  # Composite
            self._delivery_combo.setEnabled(False)
        else:
            self._delivery_combo.setEnabled(True)

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._dir_edit.setText(path)

    # ------------------------------------------------------------------
    # Run / Cancel
    # ------------------------------------------------------------------

    def _collect_settings(self) -> PlayblastSettings | None:
        """Build PlayblastSettings from UI state. Returns None on validation failure."""
        output_dir = self._dir_edit.text().strip()
        if not output_dir:
            self._status_label.setText("Please specify an output directory.")
            return None

        prefix = self._prefix_edit.text().strip() or "vpcomp"
        return PlayblastSettings(
            output_dir=output_dir,
            filename_prefix=prefix,
            width=self._width_spin.value(),
            height=self._height_spin.value(),
            scale=self._scale_spin.value() / 100.0,
            frame_start=self._start_spin.value(),
            frame_end=self._end_spin.value(),
            frame_padding=4,
            panel=self._panel,
            play_after=self._play_cb.isChecked(),
            output_mode=self._format_combo.currentData() or OutputMode.IMAGE_SEQUENCE,
            delivery_mode=self._delivery_combo.currentData() or DeliveryMode.COMPOSITE,
            fps=get_scene_fps(),
            renderer_override=self._renderer_combo.currentData() or "",
        )

    def _collect_render_configs(self) -> list[LayerRenderConfig]:
        """Build render configs from the layer list checkboxes."""
        configs: list[LayerRenderConfig] = []
        for row in range(self._layer_list.count()):
            item = self._layer_list.item(row)
            configs.append(
                LayerRenderConfig(
                    layer_index=item.data(Qt.UserRole),
                    enabled=item.checkState() == Qt.Checked,
                )
            )
        return configs

    def _handle_result(self, result, settings: PlayblastSettings, render_configs: list[LayerRenderConfig]) -> None:
        """Update status and launch player after a successful run."""
        output_files = result.output_files
        if self._cancelled:
            self._status_label.setText("Cancelled.")
            return

        if settings.output_mode is OutputMode.MOVIE:
            self._status_label.setText(f"Done — MP4 saved: {output_files[0]}")
        else:
            frame_count = settings.frame_end - settings.frame_start + 1
            delivery = settings.delivery_mode
            if delivery in (DeliveryMode.PER_LAYER, DeliveryMode.BOTH):
                n_layers = sum(1 for r in render_configs if r.enabled)
                prefix = "composite + " if delivery is DeliveryMode.BOTH else ""
                msg = f"Done — {prefix}{n_layers} layer(s) x {frame_count} frame(s) saved."
            else:
                msg = f"Done — {len(output_files)} frame(s) saved."
            self._status_label.setText(msg)
        self._progress.setValue(self._progress.maximum())

        if settings.play_after and output_files and not self._cancelled:
            player = self._player_combo.currentData()
            if player:
                try:
                    player.launch(result)
                except Exception as exc:
                    logger.warning("Player launch failed: %s", exc)

    def keyPressEvent(self, event) -> None:
        """Eat Esc to prevent reject(). During a run, also request cancel."""
        if event.key() == Qt.Key_Escape:
            if self._running and not self._cancelled:
                self._cancelled = True
                self._run_btn.setText("Cancelling...")
                self._run_btn.setEnabled(False)
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_run_clicked(self) -> None:
        if self._running:
            self._cancelled = True
            self._run_btn.setText("Cancelling...")
            self._run_btn.setEnabled(False)
            return

        settings = self._collect_settings()
        if settings is None:
            return

        render_configs = self._collect_render_configs()

        self._cancelled = False
        self._running = True
        self._run_btn.setText("Cancel")
        self._progress.setValue(0)
        self._status_label.setText("Starting...")

        try:
            result = run_playblast_composite(
                stack=self._stack,
                settings=settings,
                render_configs=render_configs,
                progress_callback=self._on_progress,
                cancel_check=lambda: self._cancelled,
            )
            self._handle_result(result, settings, render_configs)
        except Exception as exc:
            logger.error("Playblast failed: %s", exc)
            self._status_label.setText(f"Error: {exc}")
        finally:
            self._running = False
            self._cancelled = False
            self._run_btn.setText("Playblast")
            self._run_btn.setEnabled(True)

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(message)
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        """Restore UI values from saved settings."""
        data = self._settings.load_settings("playblast")
        if not data:
            return
        # Output
        fmt = data.get("format")
        if fmt is not None:
            idx = self._format_combo.findData(OutputMode(fmt))
            if idx >= 0:
                self._format_combo.setCurrentIndex(idx)
        delivery = data.get("delivery")
        if delivery is not None:
            idx = self._delivery_combo.findData(DeliveryMode(delivery))
            if idx >= 0:
                self._delivery_combo.setCurrentIndex(idx)
        path = data.get("path", "")
        if path:
            self._dir_edit.setText(path)
        filename = data.get("filename", "")
        if filename:
            self._prefix_edit.setText(filename)
        # Resolution
        width = data.get("width")
        if width is not None:
            self._width_spin.setValue(width)
        height = data.get("height")
        if height is not None:
            self._height_spin.setValue(height)
        scale = data.get("scale")
        if scale is not None:
            self._scale_spin.setValue(scale)

    def _save_settings(self) -> None:
        """Save current UI values to settings."""
        data = {
            "format": self._format_combo.currentData().value if self._format_combo.currentData() else OutputMode.IMAGE_SEQUENCE.value,
            "delivery": self._delivery_combo.currentData().value if self._delivery_combo.currentData() else DeliveryMode.COMPOSITE.value,
            "path": self._dir_edit.text().strip(),
            "filename": self._prefix_edit.text().strip(),
            "width": self._width_spin.value(),
            "height": self._height_spin.value(),
            "scale": self._scale_spin.value(),
        }
        self._settings.save_settings(data, "playblast")

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
