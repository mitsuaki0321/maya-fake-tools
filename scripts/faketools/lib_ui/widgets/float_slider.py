"""Float slider widget with label and spinbox.

This module provides a composite widget that combines a QLabel, QSlider and
QDoubleSpinBox for labeled numeric value input with synchronized updates.
"""

from logging import getLogger
from typing import Optional

from ..base_window import get_spacing
from ..qt_compat import QDoubleSpinBox, QHBoxLayout, QLabel, QSlider, Qt, QWidget, Signal
from ..ui_utils import get_text_width

logger = getLogger(__name__)


class FloatSlider(QWidget):
    """A widget combining a label, slider and spinbox for float value input.

    This widget provides a label, horizontal slider, and QDoubleSpinBox
    for numeric input. Values are synchronized between slider and spinbox
    while preventing circular updates.

    Attributes:
        valueChanged: Signal emitted when the value changes (float).

    Example:
        >>> slider = FloatSlider(
        ...     label="Distance:",
        ...     minimum=0.0,
        ...     maximum=1.0,
        ...     default=0.5,
        ...     decimals=2,
        ... )
        >>> slider.valueChanged.connect(lambda v: print(f"Value: {v}"))
    """

    valueChanged = Signal(float)

    def __init__(
        self,
        label: str = "",
        minimum: float = 0.0,
        maximum: float = 1.0,
        default: float = 0.5,
        decimals: int = 2,
        parent=None,
    ):
        """Initialize the float slider widget.

        Args:
            label (str): Label text displayed on the left. Defaults to "".
            minimum (float): Minimum allowed value. Defaults to 0.0.
            maximum (float): Maximum allowed value. Defaults to 1.0.
            default (float): Initial value. Defaults to 0.5.
            decimals (int): Number of decimal places. Defaults to 2.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent=parent)

        self._label_text = label
        self._minimum = minimum
        self._maximum = maximum
        self._decimals = decimals
        self._multiplier = 10**decimals

        self._setup_ui()
        self.setValue(default)

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout()
        spacing = get_spacing(self, direction="horizontal")
        layout.setSpacing(spacing)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create label
        if self._label_text:
            self._label = QLabel(self._label_text)
            self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Calculate minimum width based on text
            min_label_width = get_text_width(self._label_text, self._label)
            self._label.setMinimumWidth(min_label_width)
            layout.addWidget(self._label)

        # Create slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(int(self._minimum * self._multiplier))
        self._slider.setMaximum(int(self._maximum * self._multiplier))
        layout.addWidget(self._slider)

        # Create spinbox
        self._spinbox = QDoubleSpinBox()
        self._spinbox.setDecimals(self._decimals)
        self._spinbox.setMinimum(self._minimum)
        self._spinbox.setMaximum(self._maximum)
        self._spinbox.setSingleStep(1.0 / self._multiplier)
        layout.addWidget(self._spinbox)

        self.setLayout(layout)

        # Connect signals
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _on_slider_changed(self, slider_value: int):
        """Handle slider value changed.

        Args:
            slider_value (int): Slider value (scaled by multiplier).
        """
        float_value = slider_value / self._multiplier

        # Block spinbox signals to prevent circular updates
        self._spinbox.blockSignals(True)
        self._spinbox.setValue(float_value)
        self._spinbox.blockSignals(False)

        self.valueChanged.emit(float_value)

    def _on_spinbox_changed(self, value: float):
        """Handle spinbox value changed.

        Args:
            value (float): Spinbox value.
        """
        # Block slider signals to prevent circular updates
        self._slider.blockSignals(True)
        self._slider.setValue(int(value * self._multiplier))
        self._slider.blockSignals(False)

        self.valueChanged.emit(value)

    def value(self) -> float:
        """Get the current value.

        Returns:
            float: Current value.
        """
        return self._spinbox.value()

    def setValue(self, value: float) -> None:
        """Set the value.

        Args:
            value (float): Value to set.
        """
        # Clamp value to valid range
        value = max(self._minimum, min(self._maximum, value))

        # Block all signals during setValue
        self._slider.blockSignals(True)
        self._spinbox.blockSignals(True)

        self._slider.setValue(int(value * self._multiplier))
        self._spinbox.setValue(value)

        self._slider.blockSignals(False)
        self._spinbox.blockSignals(False)

    def setMinimum(self, minimum: float) -> None:
        """Set the minimum value.

        Args:
            minimum (float): Minimum value.
        """
        self._minimum = minimum
        self._slider.setMinimum(int(minimum * self._multiplier))
        self._spinbox.setMinimum(minimum)

    def setMaximum(self, maximum: float) -> None:
        """Set the maximum value.

        Args:
            maximum (float): Maximum value.
        """
        self._maximum = maximum
        self._slider.setMaximum(int(maximum * self._multiplier))
        self._spinbox.setMaximum(maximum)

    def setRange(self, minimum: float, maximum: float) -> None:
        """Set the value range.

        Args:
            minimum (float): Minimum value.
            maximum (float): Maximum value.
        """
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def setDecimals(self, decimals: int) -> None:
        """Set the number of decimal places.

        Args:
            decimals (int): Number of decimal places.
        """
        self._decimals = decimals
        self._multiplier = 10**decimals
        self._spinbox.setDecimals(decimals)
        self._spinbox.setSingleStep(1.0 / self._multiplier)
        # Update slider range
        self._slider.setMinimum(int(self._minimum * self._multiplier))
        self._slider.setMaximum(int(self._maximum * self._multiplier))
        self._slider.setValue(int(self._spinbox.value() * self._multiplier))

    def setLabel(self, text: str) -> None:
        """Set the label text.

        Args:
            text (str): Label text.
        """
        if hasattr(self, "_label"):
            self._label.setText(text)
            min_label_width = get_text_width(text, self._label)
            self._label.setMinimumWidth(min_label_width)

    def label(self) -> Optional[QLabel]:
        """Get the label widget.

        Returns:
            Optional[QLabel]: The label widget, or None if no label was created.
        """
        return getattr(self, "_label", None)

    def spinbox(self) -> QDoubleSpinBox:
        """Get the spinbox widget.

        Returns:
            QDoubleSpinBox: The spinbox widget.
        """
        return self._spinbox

    def get_label_width(self) -> int:
        """Get the width required to display the label text.

        Returns:
            int: Width in pixels based on font metrics.
        """
        if hasattr(self, "_label"):
            return get_text_width(self._label_text, self._label)
        return 0

    def get_spinbox_value_width(self) -> int:
        """Get the width required for the spinbox.

        Calculates the width needed to display the maximum value
        with the configured decimal places, plus space for buttons and padding.
        All calculations are based on font metrics (resolution-independent).

        Returns:
            int: Width in pixels.
        """
        fm = self._spinbox.fontMetrics()

        # Text width for maximum value
        max_value_text = f"{self._maximum:.{self._decimals}f}"
        text_width = fm.horizontalAdvance(max_value_text)

        # Button width (based on font height, as buttons scale with font)
        button_width = fm.height()

        # Internal padding (half of font height for left/right margins)
        padding = fm.height() // 2

        # Scale for comfortable display
        return int((text_width + button_width + padding) * 1.25)

    def set_label_width(self, width: int) -> None:
        """Set fixed width for the label.

        Args:
            width (int): Width in pixels.
        """
        if hasattr(self, "_label"):
            self._label.setFixedWidth(width)

    def set_spinbox_width(self, width: int) -> None:
        """Set fixed width for the spinbox.

        Args:
            width (int): Width in pixels.
        """
        self._spinbox.setFixedWidth(width)


def unify_slider_widths(sliders: list["FloatSlider"]) -> None:
    """Unify label and spinbox widths across multiple FloatSlider widgets.

    Finds the maximum label width and maximum spinbox width
    among the provided sliders and applies them to all sliders.

    Args:
        sliders (list[FloatSlider]): List of FloatSlider widgets to unify.
    """
    if not sliders:
        return

    # Find max label width
    max_label_width = 0
    for slider in sliders:
        label_width = slider.get_label_width()
        if label_width > max_label_width:
            max_label_width = label_width

    # Find max spinbox width
    max_spinbox_width = 0
    for slider in sliders:
        spinbox_width = slider.get_spinbox_value_width()
        if spinbox_width > max_spinbox_width:
            max_spinbox_width = spinbox_width

    # Apply to all sliders
    for slider in sliders:
        if max_label_width > 0:
            slider.set_label_width(max_label_width)
        if max_spinbox_width > 0:
            slider.set_spinbox_width(max_spinbox_width)


__all__ = ["FloatSlider", "unify_slider_widths"]
