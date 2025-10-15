"""Field and slider widget with synchronized values.

This module provides a composite widget that combines a QLineEdit and QSlider
for numeric value input with synchronized updates.
"""

from logging import getLogger

from ..base_window import get_spacing
from ..qt_compat import QDoubleValidator, QHBoxLayout, QIntValidator, QLineEdit, QSizePolicy, QSlider, Qt, QWidget, Signal

logger = getLogger(__name__)


class FieldSliderWidget(QWidget):
    """A widget combining a text field and slider with synchronized values.

    This widget provides a LineEdit for numeric input and a horizontal Slider
    for visual adjustment. Values are synchronized between both controls while
    preventing circular updates.

    Attributes:
        valueChanged: Signal emitted when the value changes (float or int).
    """

    valueChanged = Signal(object)  # Can be float or int

    def __init__(
        self,
        min_value: float = 0.0,
        max_value: float = 1.0,
        default_value: float = 1.0,
        decimals: int = 2,
        value_type: str = "float",
        parent=None,
    ):
        """Initialize the field-slider widget.

        Args:
            min_value (float): Minimum allowed value. Defaults to 0.0.
            max_value (float): Maximum allowed value. Defaults to 1.0.
            default_value (float): Initial value. Defaults to 1.0.
            decimals (int): Number of decimal places for display (float only). Defaults to 2.
            value_type (str): Value type - "float" or "int". Defaults to "float".
            parent (QWidget, optional): Parent widget. Defaults to None.

        Raises:
            ValueError: If value_type is not "float" or "int".
        """
        super().__init__(parent=parent)

        if value_type not in ["float", "int"]:
            raise ValueError(f"value_type must be 'float' or 'int', got: {value_type}")

        self._value_type = value_type
        self._min_value = min_value
        self._max_value = max_value
        self._decimals = decimals

        # Calculate slider range based on value type
        if value_type == "float":
            # For float, use 0-100 or scaled range
            self._slider_multiplier = 100
            self._slider_min = int(min_value * self._slider_multiplier)
            self._slider_max = int(max_value * self._slider_multiplier)
        else:
            # For int, use direct values
            self._slider_multiplier = 1
            self._slider_min = int(min_value)
            self._slider_max = int(max_value)

        self._setup_ui()
        self.setValue(default_value)

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout()
        spacing = get_spacing(self, direction="horizontal")
        layout.setSpacing(spacing)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create field
        self.field = QLineEdit()
        if self._value_type == "float":
            self.field.setValidator(QDoubleValidator(self._min_value, self._max_value, self._decimals))
        else:
            self.field.setValidator(QIntValidator(int(self._min_value), int(self._max_value)))

        self.field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.field.setFixedWidth(int(self.field.sizeHint().width() / 2.0))
        layout.addWidget(self.field)

        # Create slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(self._slider_min, self._slider_max)
        layout.addWidget(self.slider)

        self.setLayout(layout)

        # Connect signals
        self.field.editingFinished.connect(self._on_field_finished)
        self.slider.valueChanged.connect(self._on_slider_changed)

    def _on_field_finished(self):
        """Handle field editing finished (Enter key or focus out)."""
        text = self.field.text()
        if text:
            try:
                if self._value_type == "float":
                    value = float(text)
                else:
                    value = int(text)

                # Clamp value to valid range
                value = max(self._min_value, min(self._max_value, value))

                # Block signals to prevent circular updates
                self.slider.blockSignals(True)
                if self._value_type == "float":
                    self.slider.setValue(int(value * self._slider_multiplier))
                else:
                    self.slider.setValue(value)
                self.slider.blockSignals(False)

                # Update field with clamped value
                self._update_field_text(value)

                # Emit value changed signal
                self.valueChanged.emit(value)

            except ValueError:
                # Reset to slider's current value if invalid
                self._update_field_from_slider()

    def _on_slider_changed(self, slider_value: int):
        """Handle slider value changed.

        Args:
            slider_value (int): Slider value
        """
        # Convert slider value to actual value
        if self._value_type == "float":
            value = slider_value / self._slider_multiplier
        else:
            value = slider_value

        # Block signals to prevent circular updates
        self.field.blockSignals(True)
        self._update_field_text(value)
        self.field.blockSignals(False)

        # Emit value changed signal
        self.valueChanged.emit(value)

    def _update_field_text(self, value):
        """Update field text with proper formatting.

        Args:
            value (float or int): Value to display
        """
        if self._value_type == "float":
            self.field.setText(str(value))
        else:
            self.field.setText(str(int(value)))

    def _update_field_from_slider(self):
        """Update field text from current slider value."""
        if self._value_type == "float":
            value = self.slider.value() / self._slider_multiplier
        else:
            value = self.slider.value()
        self._update_field_text(value)

    def value(self):
        """Get the current value.

        Returns:
            float or int: Current value based on value_type
        """
        if self._value_type == "float":
            return self.slider.value() / self._slider_multiplier
        else:
            return self.slider.value()

    def setValue(self, value):
        """Set the value.

        Args:
            value (float or int): Value to set

        Raises:
            ValueError: If value is out of range
        """
        # Clamp value to valid range
        value = max(self._min_value, min(self._max_value, value))

        # Block all signals during setValue
        self.field.blockSignals(True)
        self.slider.blockSignals(True)

        # Update both widgets
        if self._value_type == "float":
            self.slider.setValue(int(value * self._slider_multiplier))
        else:
            self.slider.setValue(int(value))

        self._update_field_text(value)

        # Unblock signals
        self.field.blockSignals(False)
        self.slider.blockSignals(False)


__all__ = ["FieldSliderWidget"]
