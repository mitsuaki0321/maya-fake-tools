"""Pure-math placement and film-gate computations (Maya-API-free)."""

from __future__ import annotations

from .model import FitMode

_FULL_RECT_TUPLE = (0.0, 0.0, 1.0, 1.0)


def compute_film_gate_rect_from_params(
    vp_w: int,
    vp_h: int,
    hfa: float,
    vfa: float,
    film_fit: int,
    overscan: float,
) -> tuple[float, float, float, float]:
    """Compute filmGate rectangle from camera parameters. Maya API free.

    Args:
        vp_w: Viewport / output width in pixels.
        vp_h: Viewport / output height in pixels.
        hfa: Horizontal film aperture (inches).
        vfa: Vertical film aperture (inches).
        film_fit: Film fit mode integer (0=fill, 1=horizontal, 2=vertical, 3=overscan).
        overscan: Camera overscan value.

    Returns:
        ``(x, y, width, height)`` in normalised coordinates (0-1).
    """
    if vp_w <= 0 or vp_h <= 0 or not vfa:
        return _FULL_RECT_TUPLE

    film_aspect = hfa / vfa
    vp_aspect = vp_w / vp_h

    if film_fit == 1:  # Horizontal
        width = 1.0
        height = vp_aspect / film_aspect
    elif film_fit == 2:  # Vertical
        width = film_aspect / vp_aspect
        height = 1.0
    elif film_fit == 0:  # Fill
        if film_aspect > vp_aspect:
            width = film_aspect / vp_aspect
            height = 1.0
        else:
            width = 1.0
            height = vp_aspect / film_aspect
    else:  # Overscan (3)
        if film_aspect > vp_aspect:
            width = 1.0
            height = vp_aspect / film_aspect
        else:
            width = film_aspect / vp_aspect
            height = 1.0

    if overscan and overscan != 1.0:
        width /= overscan
        height /= overscan

    x = (1.0 - width) / 2.0
    y = (1.0 - height) / 2.0
    return (x, y, width, height)


def compute_placement_rect(
    img_w: int,
    img_h: int,
    vp_w: int,
    vp_h: int,
    fit_mode: FitMode,
    film_gate_wh: tuple[float, float] | None = None,
) -> tuple[float, float, float, float]:
    """Pure-math image placement. Maya API free.

    Args:
        img_w: Source image width in pixels.
        img_h: Source image height in pixels.
        vp_w: Viewport / canvas width in pixels.
        vp_h: Viewport / canvas height in pixels.
        fit_mode: How the image fits the viewport / filmGate.
        film_gate_wh: ``(gate_w, gate_h)`` in normalised coords, required
            for filmGate fit modes. If *None* and a filmGate mode is
            requested, the corresponding viewport mode is used as fallback.

    Returns:
        ``(x, y, w, h)`` in normalised coordinates (0-1).
    """
    if img_w <= 0 or img_h <= 0 or vp_w <= 0 or vp_h <= 0:
        return _FULL_RECT_TUPLE

    img_aspect = img_w / img_h
    vp_aspect = vp_w / vp_h

    if fit_mode == FitMode.VIEWPORT_HEIGHT:
        h = 1.0
        w = img_aspect / vp_aspect
        x = (1.0 - w) / 2.0
        y = 0.0

    elif fit_mode == FitMode.VIEWPORT_WIDTH:
        w = 1.0
        h = vp_aspect / img_aspect
        x = 0.0
        y = (1.0 - h) / 2.0

    elif fit_mode in (FitMode.FILMGATE_HEIGHT, FitMode.FILMGATE_WIDTH):
        if film_gate_wh is None:
            fallback = FitMode.VIEWPORT_HEIGHT if fit_mode == FitMode.FILMGATE_HEIGHT else FitMode.VIEWPORT_WIDTH
            return compute_placement_rect(img_w, img_h, vp_w, vp_h, fallback)

        fg_w, fg_h = film_gate_wh

        if fit_mode == FitMode.FILMGATE_HEIGHT:
            h = fg_h
            w = fg_h * img_aspect / vp_aspect
        else:  # FILMGATE_WIDTH
            w = fg_w
            h = fg_w * vp_aspect / img_aspect

        x = (1.0 - w) / 2.0
        y = (1.0 - h) / 2.0

    else:
        return _FULL_RECT_TUPLE

    # Clamp to viewport bounds while preserving aspect ratio.
    if w > 1.0 or h > 1.0:
        scale = min(1.0 / w, 1.0 / h)
        w *= scale
        h *= scale
        x = (1.0 - w) / 2.0
        y = (1.0 - h) / 2.0

    return (x, y, w, h)
