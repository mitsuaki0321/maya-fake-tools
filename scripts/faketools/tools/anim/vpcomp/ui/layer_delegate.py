"""QStyledItemDelegate for Photoshop-style layer rows."""

from __future__ import annotations

from .....lib_ui.qt_compat import (
    QColor,
    QEvent,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QSize,
    QStyle,
    QStyledItemDelegate,
    Qt,
)
from ..core.model import LayerType
from .colors import (
    LAYER_TYPE_COLORS,
    LAYER_TYPE_FALLBACK,
    MENU_DOTS,
    MENU_DOTS_HOVER,
    ROW_BG_DEFAULT,
    ROW_BG_HOVER,
    ROW_BG_SELECTED,
    ROW_BORDER_SELECTED,
    TEXT_LAYER_NAME,
    VISIBILITY_OFF,
    VISIBILITY_ON,
    ZONE_SEPARATOR,
)
from .layer_model import ROLE_BADGE, ROLE_LAYER_TYPE, ROLE_NAME, ROLE_VISIBLE
from .resource_utils import load_svg_pixmap

# ── Zone layout constants ──
VIS_W = 28  # visibility icon zone width
TYPE_W = 28  # type icon zone width
BAR_W = 3  # colour bar width
MENU_W = 24  # menu dots zone width
ROW_H = 36  # row height
ITEM_MARGIN_H = 6  # horizontal margin between item and view edge
ITEM_RADIUS = 3  # border radius for item rounded rect

_TYPE_ICONS = {
    LayerType.CAMERA: "type_cam",
    LayerType.IMAGE: "type_img",
    LayerType.SEQUENCE: "type_seq",
}


def hit_zone(x: int, total_w: int) -> str:
    """Return the zone name at horizontal pixel *x*."""
    if x < ITEM_MARGIN_H + VIS_W:
        return "vis"
    if x > total_w - ITEM_MARGIN_H - MENU_W:
        return "menu"
    return "info"


class LayerDelegate(QStyledItemDelegate):
    """Custom delegate that paints each layer row."""

    # Set by LayerView on mouse-move
    hovered_row: int = -1
    hovered_zone: str = ""  # "vis" | "menu" | ""

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect

        # Inset rect for margins and rounded corners
        inner = rect.adjusted(ITEM_MARGIN_H, 1, -ITEM_MARGIN_H, -1)

        # ── 1. Background (rounded rect) ──
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected:
            bg = QColor(ROW_BG_SELECTED)
        elif hovered:
            bg = QColor(ROW_BG_HOVER)
        else:
            bg = QColor(ROW_BG_DEFAULT)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(inner, ITEM_RADIUS, ITEM_RADIUS)

        # ── 2. Selection border (blue outline) ──
        if selected:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(ROW_BORDER_SELECTED), 1))
            painter.drawRoundedRect(inner, ITEM_RADIUS, ITEM_RADIUS)

        painter.setRenderHint(QPainter.Antialiasing, False)

        # Offsets relative to inner rect
        left = inner.left()

        # ── 3. Vis zone (eye icon) ──
        visible = index.data(ROLE_VISIBLE)
        if visible:
            eye_pix = load_svg_pixmap("eye_on", VISIBILITY_ON, 15)
        else:
            eye_pix = load_svg_pixmap("eye_off", VISIBILITY_OFF, 15)
        eye_x = left + (VIS_W - 15) // 2
        eye_y = inner.top() + (inner.height() - 15) // 2
        painter.drawPixmap(eye_x, eye_y, eye_pix)

        # vis zone right separator
        sep_x = left + VIS_W
        painter.setPen(QPen(QColor(ZONE_SEPARATOR), 1))
        painter.drawLine(sep_x, inner.top() + 4, sep_x, inner.bottom() - 4)

        # ── 4. Type zone (type icon) ──
        layer_type = index.data(ROLE_LAYER_TYPE)
        type_color = LAYER_TYPE_COLORS.get(layer_type, LAYER_TYPE_FALLBACK)
        type_icon_name = _TYPE_ICONS.get(layer_type, "type_cam")
        type_pix = load_svg_pixmap(type_icon_name, type_color, 14)
        type_x = left + VIS_W + (TYPE_W - 14) // 2
        type_y = inner.top() + (inner.height() - 14) // 2
        painter.drawPixmap(type_x, type_y, type_pix)

        # type zone right separator
        sep_x2 = left + VIS_W + TYPE_W
        painter.setPen(QPen(QColor(ZONE_SEPARATOR), 1))
        painter.drawLine(sep_x2, inner.top() + 4, sep_x2, inner.bottom() - 4)

        # ── 5. Colour bar ──
        bar_color = QColor(type_color)
        bar_color.setAlpha(178)
        bar_x = left + VIS_W + TYPE_W
        painter.fillRect(bar_x, inner.top(), BAR_W, inner.height(), bar_color)

        # ── 6. Info area (badge + name) ──
        info_left = left + VIS_W + TYPE_W + BAR_W + 6
        info_width = inner.width() - VIS_W - TYPE_W - BAR_W - MENU_W - 8

        # Badge (type label)
        badge_text = index.data(ROLE_BADGE) or ""
        badge_font = QFont()
        badge_font.setPointSize(7)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        painter.setPen(QColor(type_color))
        painter.drawText(info_left, inner.top() + 13, badge_text)

        # Name
        name_text = index.data(ROLE_NAME) or ""
        name_font = QFont()
        name_font.setPointSize(9)
        painter.setFont(name_font)
        painter.setPen(QColor(TEXT_LAYER_NAME))
        fm = QFontMetrics(name_font)
        elided = fm.elidedText(name_text, Qt.ElideRight, info_width)
        painter.drawText(info_left, inner.top() + 27, elided)

        # ── 7. Menu zone (⋮) ──
        is_menu_hovered = index.row() == self.hovered_row and self.hovered_zone == "menu"
        menu_color = MENU_DOTS_HOVER if is_menu_hovered else MENU_DOTS
        menu_pix = load_svg_pixmap("menu_dots", menu_color, 13)
        menu_x = inner.right() - MENU_W + (MENU_W - 13) // 2
        menu_y = inner.top() + (inner.height() - 13) // 2
        painter.drawPixmap(menu_x, menu_y, menu_pix)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def editorEvent(self, event, model, option, index):
        if event.type() != QEvent.MouseButtonRelease:
            return False
        if event.button() != Qt.LeftButton:
            return False

        x = event.pos().x()
        zone = hit_zone(x, option.rect.width())

        if zone == "vis":
            current = index.data(ROLE_VISIBLE)
            model.setData(index, not current, ROLE_VISIBLE)
            return True

        return False
