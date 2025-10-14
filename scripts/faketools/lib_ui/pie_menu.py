"""
Directional pie menu widget for Maya tools.

Supports 2, 4, or 8 directional segments with customizable actions.
"""

from logging import getLogger
import math

from .qt_compat import QBrush, QColor, QPainter, QPainterPath, QPen, QPointF, QRectF, QRegion, Qt, QtGui, QWidget, Signal

logger = getLogger(__name__)


class PieMenu(QWidget):
    """
    Directional pie menu widget with support for 2, 4, or 8 segments.

    Supports:
    - 2 segments: Up, Down
    - 4 segments: Up, Right, Down, Left
    - 8 segments: Up, UpRight, Right, DownRight, Down, DownLeft, Left, UpLeft

    Empty items (None) are supported and will show only the segment without text.
    """

    item_selected = Signal(str)

    # Direction names for each segment count
    DIRECTION_NAMES = {
        2: ["Up", "Down"],
        4: ["Up", "Right", "Down", "Left"],
        8: ["Up", "UpRight", "Right", "DownRight", "Down", "DownLeft", "Left", "UpLeft"],
    }

    # Size presets (outer_radius, inner_radius)
    SIZE_SMALL = (100, 25)
    SIZE_MEDIUM = (130, 35)
    SIZE_LARGE = (170, 45)
    SIZE_XLARGE = (210, 55)

    def __init__(self, items, parent=None, outer_radius=None, inner_radius=None, size_preset=None, scale=1.0):
        """
        Initialize pie menu.

        Args:
            items (list): List of menu items (str, dict with 'label' and 'callback', or None)
                         Supported counts: 2, 4, or 8
                         Order:
                         - 2 items: [Up, Down]
                         - 4 items: [Up, Right, Down, Left]
                         - 8 items: [Up, UpRight, Right, DownRight, Down, DownLeft, Left, UpLeft]
                         None items show empty segment (no text)
            parent (QWidget): Parent widget
            outer_radius (int, optional): Outer radius of the pie menu in pixels
                                         If None, uses size_preset or default
            inner_radius (int, optional): Inner radius (center circle) in pixels
                                         If None, uses size_preset or default
            size_preset (tuple, optional): Size preset tuple (outer_radius, inner_radius)
                                          Use SIZE_SMALL, SIZE_MEDIUM, SIZE_LARGE, or SIZE_XLARGE
                                          Ignored if outer_radius and inner_radius are specified
            scale (float): Scale factor to apply to radius values (default: 1.0)
                          Applied after size_preset or default values
        """
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background: transparent;")

        # Validate segment count
        if len(items) not in self.DIRECTION_NAMES:
            raise ValueError(f"Pie menu supports 2, 4, or 8 items. Got {len(items)} items.")

        self.items = items
        self.segment_count = len(items)
        self.directions = self.DIRECTION_NAMES[self.segment_count]
        self.hovered_item = -1

        # Determine radius values
        if outer_radius is not None and inner_radius is not None:
            # Explicit radius values provided
            self.outer_radius = int(outer_radius * scale)
            self.inner_radius = int(inner_radius * scale)
        elif size_preset is not None:
            # Use preset
            preset_outer, preset_inner = size_preset
            self.outer_radius = int(preset_outer * scale)
            self.inner_radius = int(preset_inner * scale)
        else:
            # Use default (MEDIUM)
            self.outer_radius = int(self.SIZE_MEDIUM[0] * scale)
            self.inner_radius = int(self.SIZE_MEDIUM[1] * scale)

        # Calculate angle step based on segment count
        self.angle_step = 360.0 / self.segment_count

        # Calculate widget size
        size = (self.outer_radius + 20) * 2
        self.setFixedSize(size, size)

    def show_at_cursor(self):
        """Show the pie menu at the current cursor position."""
        cursor_pos = QtGui.QCursor.pos()

        # Create circular mask to show only the pie menu area
        self._create_mask()

        # Position the widget so cursor is at center
        self.move(cursor_pos.x() - self.width() // 2, cursor_pos.y() - self.height() // 2)
        self.show()

    def _create_mask(self):
        """Create a circular mask for the widget."""
        center = self.rect().center()
        # Add padding for border and anti-aliasing
        mask_radius = self.outer_radius + 5
        mask = QRegion(
            center.x() - mask_radius,
            center.y() - mask_radius,
            mask_radius * 2,
            mask_radius * 2,
            QRegion.RegionType.Ellipse,
        )
        self.setMask(mask)

    def paintEvent(self, event):
        """Paint the pie menu."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.rect().center()

        # Start angle: up is 0 degrees (Qt uses 3 o'clock as 0, counter-clockwise positive)
        start_angle = 90.0

        for i, item in enumerate(self.items):
            # Calculate segment start angle
            current_start_angle = start_angle + (self.angle_step / 2) - (self.angle_step * i)
            span_angle = -self.angle_step  # Negative for clockwise

            # Determine colors
            is_hovered = i == self.hovered_item
            if is_hovered:
                fill_color = QColor(80, 120, 160, 220)
                border_color = QColor(255, 255, 255)  # White border for hover
                text_color = QColor(255, 255, 255)  # White text for hover
            else:
                fill_color = QColor(70, 70, 70, 180)
                border_color = QColor(180, 180, 180)  # Medium-light gray for border
                text_color = QColor(230, 230, 230)  # Very light gray for text

            # Create pie segment path
            path = QPainterPath()

            # Calculate outer arc start point
            start_angle_rad = math.radians(current_start_angle)
            outer_start_x = center.x() + self.outer_radius * math.cos(start_angle_rad)
            outer_start_y = center.y() - self.outer_radius * math.sin(start_angle_rad)

            # Outer arc
            outer_rect = QRectF(
                center.x() - self.outer_radius,
                center.y() - self.outer_radius,
                self.outer_radius * 2,
                self.outer_radius * 2,
            )
            path.moveTo(outer_start_x, outer_start_y)
            path.arcTo(outer_rect, current_start_angle, span_angle)

            # Inner arc
            inner_rect = QRectF(
                center.x() - self.inner_radius,
                center.y() - self.inner_radius,
                self.inner_radius * 2,
                self.inner_radius * 2,
            )

            # Line from outer arc end to inner arc end
            end_angle_rad = math.radians(current_start_angle + span_angle)
            inner_end_x = center.x() + self.inner_radius * math.cos(end_angle_rad)
            inner_end_y = center.y() - self.inner_radius * math.sin(end_angle_rad)
            path.lineTo(inner_end_x, inner_end_y)

            # Draw inner arc in reverse direction
            path.arcTo(inner_rect, current_start_angle + span_angle, -span_angle)
            path.closeSubpath()

            # Draw segment
            painter.setPen(QPen(border_color, 2))
            painter.setBrush(QBrush(fill_color))
            painter.drawPath(path)

            # Draw text label if item is not None
            if item is not None:
                label = item if isinstance(item, str) else item.get("label", "")

                if label:
                    # Calculate text position (center of segment)
                    mid_angle = current_start_angle + span_angle / 2
                    mid_angle_rad = math.radians(mid_angle)
                    text_radius = (self.outer_radius + self.inner_radius) / 2
                    text_x = center.x() + text_radius * math.cos(mid_angle_rad)
                    text_y = center.y() - text_radius * math.sin(mid_angle_rad)

                    # Font settings
                    font = painter.font()
                    font.setPointSize(10)
                    font.setBold(is_hovered)
                    painter.setFont(font)

                    # Text rectangle
                    fm = painter.fontMetrics()
                    text_width = fm.horizontalAdvance(label)
                    text_height = fm.height()
                    text_rect = QRectF(text_x - text_width / 2, text_y - text_height / 2, text_width, text_height)

                    # Draw text
                    painter.setPen(QPen(text_color))
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        # Draw radial lines between segments
        painter.setPen(QPen(QColor(180, 180, 180), 2))
        line_start_radius = self.inner_radius + 2  # Start outside center circle
        for i in range(self.segment_count):
            # Calculate boundary angle for each segment
            angle = start_angle + (self.angle_step / 2) - (self.angle_step * i)
            angle_rad = math.radians(angle)

            # Draw line from inner circle to outer circle
            inner_x = center.x() + line_start_radius * math.cos(angle_rad)
            inner_y = center.y() - line_start_radius * math.sin(angle_rad)
            outer_x = center.x() + self.outer_radius * math.cos(angle_rad)
            outer_y = center.y() - self.outer_radius * math.sin(angle_rad)

            painter.drawLine(QPointF(inner_x, inner_y), QPointF(outer_x, outer_y))

        # Draw center circle
        painter.setPen(QPen(QColor(180, 180, 180), 2))
        painter.setBrush(QBrush(QColor(60, 60, 60, 220)))
        painter.drawEllipse(center, self.inner_radius, self.inner_radius)

    def mouseMoveEvent(self, event):
        """Handle mouse move to detect hovered item."""
        center = self.rect().center()
        mouse_pos = event.pos()

        # Calculate distance from center
        dx = mouse_pos.x() - center.x()
        dy = mouse_pos.y() - center.y()
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < self.inner_radius:
            # Inside center circle
            self.hovered_item = -1
        elif distance < self.outer_radius:
            # Inside menu area - calculate which segment
            angle = math.degrees(math.atan2(-dy, dx))  # -dy to flip Y axis
            # Normalize to 0-360 degrees with up as 0
            angle = (90 - angle) % 360

            # Offset by half step and divide by angle_step
            half_step = self.angle_step / 2
            adjusted_angle = (angle + half_step) % 360
            item_index = int(adjusted_angle / self.angle_step) % self.segment_count
            self.hovered_item = item_index
        else:
            # Outside menu area
            self.hovered_item = -1

        self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to select item."""
        if 0 <= self.hovered_item < len(self.items):
            item = self.items[self.hovered_item]

            # Skip if item is None (empty segment)
            if item is not None:
                label = item if isinstance(item, str) else item.get("label", "")

                # Emit signal
                self.item_selected.emit(label)

                # Execute callback if available
                if isinstance(item, dict) and "callback" in item:
                    try:
                        item["callback"]()
                    except Exception as e:
                        logger.error(f"Error executing pie menu callback for '{label}': {e}")

        self.close()

    def keyPressEvent(self, event):
        """Handle escape key to close menu."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()


class PieMenuButton:
    """
    Mixin class to add pie menu support to any QWidget.

    Usage:
        class MyButton(PieMenuButton, QPushButton):
            def __init__(self):
                super().__init__()
                self.setup_pie_menu(
                    items=[...],
                    trigger_button=Qt.MouseButton.MiddleButton
                )

    Note:
        This is a mixin class and should not inherit from QWidget.
        It should be used as the first base class in multiple inheritance.
    """

    def setup_pie_menu(self, items, trigger_button=Qt.MouseButton.MiddleButton, outer_radius=None, inner_radius=None, size_preset=None, scale=1.0):
        """
        Setup pie menu for this widget.

        Can be called multiple times with different trigger buttons to set up multiple pie menus.

        Args:
            items (list): List of menu items (see PieMenu for format)
            trigger_button (Qt.MouseButton): Mouse button to trigger menu (MiddleButton, LeftButton, RightButton)
            outer_radius (int, optional): Outer radius of the pie menu
                                         If None, uses size_preset or default
            inner_radius (int, optional): Inner radius of the pie menu
                                         If None, uses size_preset or default
            size_preset (tuple, optional): Size preset tuple (outer_radius, inner_radius)
                                          Use PieMenu.SIZE_SMALL, SIZE_MEDIUM, SIZE_LARGE, or SIZE_XLARGE
            scale (float): Scale factor to apply to radius values (default: 1.0)
        """
        # Initialize pie menu configurations dict if not exists
        if not hasattr(self, "_pie_menu_configs"):
            self._pie_menu_configs = {}

        # Store configuration for this trigger button
        self._pie_menu_configs[trigger_button] = {
            "items": items,
            "outer_radius": outer_radius,
            "inner_radius": inner_radius,
            "size_preset": size_preset,
            "scale": scale,
        }

    def mousePressEvent(self, event):
        """Handle mouse press to show pie menu."""
        if hasattr(self, "_pie_menu_configs") and event.button() in self._pie_menu_configs:
            self._show_pie_menu(event.button())
            event.accept()
        else:
            super().mousePressEvent(event)

    def _show_pie_menu(self, trigger_button):
        """Show the pie menu for the specified trigger button.

        Args:
            trigger_button (Qt.MouseButton): The mouse button that triggered the menu
        """
        if not hasattr(self, "_pie_menu_configs") or trigger_button not in self._pie_menu_configs:
            return

        config = self._pie_menu_configs[trigger_button]
        pie_menu = PieMenu(
            items=config["items"],
            parent=self,
            outer_radius=config.get("outer_radius"),
            inner_radius=config.get("inner_radius"),
            size_preset=config.get("size_preset"),
            scale=config.get("scale", 1.0),
        )
        pie_menu.show_at_cursor()


__all__ = ["PieMenu", "PieMenuButton"]
