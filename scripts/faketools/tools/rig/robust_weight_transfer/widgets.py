"""Robust Weight Transfer UI widgets.

This module contains reusable widget classes for the Robust Weight Transfer UI.
Each section of the UI is encapsulated in its own QGroupBox subclass.
"""

from ....lib_ui import FloatSlider, get_spacing, unify_slider_widths
from ....lib_ui.qt_compat import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
)
from ....lib_ui.widgets import extra_widgets


class SettingsSection(QGroupBox):
    """Settings section for matching parameters.

    Contains distance ratio, angle threshold, matching options, and deform options.
    """

    def __init__(self, default_settings: dict, parent=None):
        """Initialize the settings section.

        Args:
            default_settings: Dictionary containing default values.
            parent: Parent widget.
        """
        super().__init__("Settings", parent)
        self._default_settings = default_settings
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        spacing = get_spacing(self, direction="vertical")
        layout = QVBoxLayout(self)
        layout.setSpacing(int(spacing * 0.5))

        # Distance threshold
        self.distance_slider = FloatSlider(
            label="Distance Ratio:",
            minimum=0.001,
            maximum=0.5,
            default=self._default_settings["distance_ratio"],
            decimals=3,
        )
        layout.addWidget(self.distance_slider)

        # Angle threshold
        self.angle_slider = FloatSlider(
            label="Angle (degrees):",
            minimum=1.0,
            maximum=90.0,
            default=self._default_settings["angle_degrees"],
            decimals=1,
        )
        layout.addWidget(self.angle_slider)

        # Expand boundary
        self.expand_slider = FloatSlider(
            label="Expand Boundary:",
            minimum=0,
            maximum=5,
            default=self._default_settings.get("expand_boundary", 0),
            decimals=0,
        )
        self.expand_slider.setToolTip("Expand unmatched region by N edge rings for smoother boundary")
        layout.addWidget(self.expand_slider)

        # Checkboxes row 1: Flip + Fast
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(spacing)

        self.flip_normals_cb = QCheckBox("Flip Normals")
        self.flip_normals_cb.setToolTip("Allow matching with inverted normals")
        checkbox_layout.addWidget(self.flip_normals_cb)

        self.use_kdtree_cb = QCheckBox("Fast Mode (KDTree)")
        self.use_kdtree_cb.setToolTip("Faster but less accurate vertex matching")
        checkbox_layout.addWidget(self.use_kdtree_cb)

        layout.addLayout(checkbox_layout)

        # Checkboxes row 2: Deform options
        deform_layout = QHBoxLayout()
        deform_layout.setSpacing(spacing)

        self.deform_source_cb = QCheckBox("Use Deformed Source")
        self.deform_source_cb.setToolTip("Evaluate source mesh at current pose")
        deform_layout.addWidget(self.deform_source_cb)

        self.deform_target_cb = QCheckBox("Use Deformed Target")
        self.deform_target_cb.setToolTip("Evaluate target mesh at current pose")
        deform_layout.addWidget(self.deform_target_cb)

        layout.addLayout(deform_layout)

        # Unify slider widths
        unify_slider_widths([self.distance_slider, self.angle_slider, self.expand_slider])

    def collect_settings(self) -> dict:
        """Collect current settings values.

        Returns:
            Dictionary of settings values.
        """
        return {
            "distance_ratio": self.distance_slider.value(),
            "angle_degrees": self.angle_slider.value(),
            "expand_boundary": int(self.expand_slider.value()),
            "flip_normals": self.flip_normals_cb.isChecked(),
            "use_kdtree": self.use_kdtree_cb.isChecked(),
            "use_deformed_source": self.deform_source_cb.isChecked(),
            "use_deformed_target": self.deform_target_cb.isChecked(),
        }

    def apply_settings(self, settings_data: dict) -> None:
        """Apply settings values to widgets.

        Args:
            settings_data: Dictionary of settings values.
        """
        defaults = self._default_settings
        self.distance_slider.setValue(settings_data.get("distance_ratio", defaults["distance_ratio"]))
        self.angle_slider.setValue(settings_data.get("angle_degrees", defaults["angle_degrees"]))
        self.expand_slider.setValue(settings_data.get("expand_boundary", defaults.get("expand_boundary", 0)))
        self.flip_normals_cb.setChecked(settings_data.get("flip_normals", defaults["flip_normals"]))
        self.use_kdtree_cb.setChecked(settings_data.get("use_kdtree", defaults["use_kdtree"]))
        self.deform_source_cb.setChecked(settings_data.get("use_deformed_source", defaults["use_deformed_source"]))
        self.deform_target_cb.setChecked(settings_data.get("use_deformed_target", defaults["use_deformed_target"]))


class PostProcessingSection(QGroupBox):
    """Post-processing section combining smoothing and seam averaging.

    Contains smoothing options (enable, iterations, alpha) and
    seam averaging options (enable, internal seams, tolerance).
    """

    def __init__(self, default_settings: dict, parent=None):
        """Initialize the post-processing section.

        Args:
            default_settings: Dictionary containing default values.
            parent: Parent widget.
        """
        super().__init__("Post Processing", parent)
        self._default_settings = default_settings
        self._setup_ui()
        self._connect_signals()
        self._update_smooth_enabled_state()
        self._update_seam_enabled_state()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        spacing = get_spacing(self, direction="vertical")
        layout = QVBoxLayout(self)
        layout.setSpacing(int(spacing * 0.5))

        # --- Smoothing ---
        self.smooth_cb = QCheckBox("Enable Smoothing")
        self.smooth_cb.setChecked(self._default_settings["enable_smoothing"])
        layout.addWidget(self.smooth_cb)

        self.smooth_iter_slider = FloatSlider(
            label="Iterations:",
            minimum=1,
            maximum=50,
            default=self._default_settings["smooth_iterations"],
            decimals=0,
        )
        layout.addWidget(self.smooth_iter_slider)

        self.smooth_alpha_slider = FloatSlider(
            label="Alpha:",
            minimum=0.01,
            maximum=1.0,
            default=self._default_settings["smooth_alpha"],
            decimals=2,
        )
        layout.addWidget(self.smooth_alpha_slider)

        # --- Separator ---
        layout.addWidget(extra_widgets.HorizontalSeparator())

        # --- Seam Averaging ---
        self.seam_cb = QCheckBox("Average Seam Weights")
        self.seam_cb.setToolTip("Average weights for vertices at the same position.\nUseful for clothing seams (e.g., collar and shirt).")
        layout.addWidget(self.seam_cb)

        self.seam_internal_cb = QCheckBox("Include Internal Seams")
        self.seam_internal_cb.setChecked(self._default_settings["seam_internal"])
        self.seam_internal_cb.setToolTip(
            "Also average vertices at the same position within a single mesh.\n"
            "Useful for UV seams where vertices are split but share the same position."
        )
        layout.addWidget(self.seam_internal_cb)

        self.seam_tolerance_slider = FloatSlider(
            label="Position Tolerance:",
            minimum=0.0001,
            maximum=0.01,
            default=self._default_settings["seam_tolerance"],
            decimals=4,
        )
        self.seam_tolerance_slider.setToolTip("Maximum distance to consider vertices as coincident")
        layout.addWidget(self.seam_tolerance_slider)

        # Unify all slider widths
        unify_slider_widths([self.smooth_iter_slider, self.smooth_alpha_slider, self.seam_tolerance_slider])

    def _connect_signals(self) -> None:
        """Connect signals to slots."""
        self.smooth_cb.toggled.connect(self._update_smooth_enabled_state)
        self.seam_cb.toggled.connect(self._update_seam_enabled_state)

    def _update_smooth_enabled_state(self) -> None:
        """Update enabled state of smoothing widgets based on checkbox."""
        enabled = self.smooth_cb.isChecked()
        self.smooth_iter_slider.setEnabled(enabled)
        self.smooth_alpha_slider.setEnabled(enabled)

    def _update_seam_enabled_state(self) -> None:
        """Update enabled state of seam widgets based on checkbox."""
        enabled = self.seam_cb.isChecked()
        self.seam_internal_cb.setEnabled(enabled)
        self.seam_tolerance_slider.setEnabled(enabled)

    def collect_settings(self) -> dict:
        """Collect current settings values.

        Returns:
            Dictionary of settings values.
        """
        return {
            "enable_smoothing": self.smooth_cb.isChecked(),
            "smooth_iterations": int(self.smooth_iter_slider.value()),
            "smooth_alpha": self.smooth_alpha_slider.value(),
            "seam_average": self.seam_cb.isChecked(),
            "seam_internal": self.seam_internal_cb.isChecked(),
            "seam_tolerance": self.seam_tolerance_slider.value(),
        }

    def apply_settings(self, settings_data: dict) -> None:
        """Apply settings values to widgets.

        Args:
            settings_data: Dictionary of settings values.
        """
        defaults = self._default_settings
        self.smooth_cb.setChecked(settings_data.get("enable_smoothing", defaults["enable_smoothing"]))
        self.smooth_iter_slider.setValue(settings_data.get("smooth_iterations", defaults["smooth_iterations"]))
        self.smooth_alpha_slider.setValue(settings_data.get("smooth_alpha", defaults["smooth_alpha"]))
        self.seam_cb.setChecked(settings_data.get("seam_average", defaults["seam_average"]))
        self.seam_internal_cb.setChecked(settings_data.get("seam_internal", defaults["seam_internal"]))
        self.seam_tolerance_slider.setValue(settings_data.get("seam_tolerance", defaults["seam_tolerance"]))


__all__ = [
    "SettingsSection",
    "PostProcessingSection",
]
