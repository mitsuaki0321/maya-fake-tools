"""Per-layer-type rendering strategies for playblast compositing.

Each LayerRenderer subclass knows how to capture frames (Phase A) and
composite a single frame onto a canvas (Phase B).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from logging import getLogger
import os

import maya.cmds as cmds  # type: ignore
from PIL import Image  # type: ignore

from .geometry import compute_film_gate_rect_from_params, compute_placement_rect
from .model import (
    CameraLayer,
    FitMode,
    ImageLayer,
    LayerType,
    SequenceLayer,
)
from .scene_queries import camera_shape, parse_film_fit

logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class LayerRenderer(ABC):
    """Strategy interface for per-layer playblast capture and compositing."""

    @abstractmethod
    def capture(
        self,
        layer: object,
        panel: str,
        width: int,
        height: int,
        frame_start: int,
        frame_end: int,
        tmp_dir: str,
    ) -> dict[int, str]:
        """Capture frames.  Camera layers playblast; others return ``{}``."""

    @abstractmethod
    def composite_frame(
        self,
        layer: object,
        frame: int,
        canvas: Image.Image,
        canvas_w: int,
        canvas_h: int,
        film_gate_wh: tuple[float, float] | None,
        captured_frames: dict[int, str],
    ) -> Image.Image:
        """Composite one frame onto *canvas* and return the result."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _setup_isolate(panel: str, layer: CameraLayer) -> None:
    """Configure isolate select for a camera layer's objectSet."""
    if not cmds.objExists(layer.object_set):
        cmds.isolateSelect(panel, state=False)
        return
    members = cmds.sets(layer.object_set, q=True) or []
    if not members:
        cmds.isolateSelect(panel, state=False)
        return
    cmds.isolateSelect(panel, state=True)
    for member in members:
        cmds.isolateSelect(panel, addDagObject=member)
    cmds.isolateSelect(panel, update=True)


def _set_black_background() -> None:
    cmds.displayRGBColor("background", 0, 0, 0)
    cmds.displayRGBColor("backgroundTop", 0, 0, 0)
    cmds.displayRGBColor("backgroundBottom", 0, 0, 0)
    cmds.displayPref(displayGradient=False)


def _scan_prefix_frames(tmp_dir: str, prefix: str) -> dict[int, str]:
    """Scan *tmp_dir* for playblast PNGs matching *prefix* -> {frame: path}."""
    frames: dict[int, str] = {}
    for fname in os.listdir(tmp_dir):
        if not (fname.startswith(prefix) and fname.endswith(".png")):
            continue
        stem = fname[len(prefix) :].replace(".png", "").lstrip(".")
        try:
            frames[int(stem)] = os.path.join(tmp_dir, fname)
        except ValueError:
            continue
    return frames


def get_camera_film_gate_wh(
    camera: str,
    vp_w: int,
    vp_h: int,
) -> tuple[float, float] | None:
    """Return (gate_w, gate_h) normalised coords for a camera, or None."""
    try:
        shape = camera_shape(camera)
        hfa = cmds.camera(shape, q=True, horizontalFilmAperture=True)
        vfa = cmds.camera(shape, q=True, verticalFilmAperture=True)
        film_fit = parse_film_fit(cmds.camera(shape, q=True, filmFit=True))
        overscan = cmds.camera(shape, q=True, overscan=True)
        _, _, gw, gh = compute_film_gate_rect_from_params(
            vp_w,
            vp_h,
            hfa,
            vfa,
            film_fit,
            overscan,
        )
        return (gw, gh)
    except Exception as exc:
        logger.warning("get_camera_film_gate_wh(%s) failed: %s", camera, exc)
        return None


def _place_image_on_canvas(
    canvas: Image.Image,
    src_img: Image.Image,
    canvas_w: int,
    canvas_h: int,
    fit_mode: FitMode,
    film_gate_wh: tuple[float, float] | None,
) -> Image.Image:
    """Composite *src_img* onto *canvas* using placement math."""
    if fit_mode not in (FitMode.FILMGATE_HEIGHT, FitMode.FILMGATE_WIDTH):
        film_gate_wh = None
    img_w, img_h = src_img.size
    nx, ny, nw, nh = compute_placement_rect(
        img_w,
        img_h,
        canvas_w,
        canvas_h,
        fit_mode,
        film_gate_wh,
    )
    px = int(nx * canvas_w)
    py = int(ny * canvas_h)
    pw = max(1, int(nw * canvas_w))
    ph = max(1, int(nh * canvas_h))

    resized = src_img.resize((pw, ph), Image.LANCZOS).convert("RGBA")
    temp = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    temp.paste(resized, (px, py))
    return Image.alpha_composite(canvas, temp)


# ---------------------------------------------------------------------------
# _CameraRenderer
# ---------------------------------------------------------------------------


class _CameraRenderer(LayerRenderer):
    """Playblast a camera layer using native RGBA alpha."""

    def capture(
        self,
        layer: CameraLayer,
        panel: str,
        width: int,
        height: int,
        frame_start: int,
        frame_end: int,
        tmp_dir: str,
    ) -> dict[int, str] | None:
        prefix = f"cam_{layer.camera}_"
        out_path = os.path.join(tmp_dir, prefix)

        # Camera switch
        cmds.lookThru(panel, layer.camera)

        # Isolate — reset then configure
        cmds.isolateSelect(panel, state=False)
        _setup_isolate(panel, layer)

        # Black background for clean alpha
        _set_black_background()

        # HUD / Grid off
        cmds.modelEditor(panel, e=True, hud=False, grid=False)

        # playblast() always captures from the active panel
        cmds.setFocus(panel)
        cmds.refresh(force=True)

        pb_result = cmds.playblast(
            startTime=frame_start,
            endTime=frame_end,
            format="image",
            compression="png",
            filename=out_path,
            widthHeight=[width, height],
            percent=100,
            quality=100,
            viewer=False,
            offScreen=True,
            forceOverwrite=True,
            clearCache=True,
            showOrnaments=False,
        )

        if pb_result is None:
            logger.info("Playblast interrupted by user: %s", layer.camera)
            return None

        frame_map = _scan_prefix_frames(tmp_dir, prefix)
        logger.debug(
            "Playblast %s: %d frame(s) found",
            layer.camera,
            len(frame_map),
        )
        return frame_map

    def composite_frame(
        self,
        layer: CameraLayer,
        frame: int,
        canvas: Image.Image,
        canvas_w: int,
        canvas_h: int,
        film_gate_wh: tuple[float, float] | None,
        captured_frames: dict[int, str],
    ) -> Image.Image:
        path = captured_frames.get(frame)
        if not path:
            logger.warning("Missing frame %d for %s", frame, layer.camera)
            return canvas
        layer_img = Image.open(path).convert("RGBA")
        return Image.alpha_composite(canvas, layer_img)


# ---------------------------------------------------------------------------
# _ImageRenderer
# ---------------------------------------------------------------------------


class _ImageRenderer(LayerRenderer):
    """Static image overlay — no playblast needed."""

    def capture(self, layer, panel, width, height, frame_start, frame_end, tmp_dir) -> dict[int, str]:
        return {}

    def composite_frame(
        self,
        layer: ImageLayer,
        frame: int,
        canvas: Image.Image,
        canvas_w: int,
        canvas_h: int,
        film_gate_wh: tuple[float, float] | None,
        captured_frames: dict[int, str],
    ) -> Image.Image:
        try:
            src = Image.open(layer.file_path).convert("RGBA")
            return _place_image_on_canvas(
                canvas,
                src,
                canvas_w,
                canvas_h,
                layer.fit_mode,
                film_gate_wh,
            )
        except Exception as exc:
            logger.warning("Image layer %s failed: %s", layer.name, exc)
            return canvas


# ---------------------------------------------------------------------------
# _SequenceRenderer
# ---------------------------------------------------------------------------


class _SequenceRenderer(LayerRenderer):
    """Image-sequence overlay synced to frame — no playblast needed."""

    def capture(self, layer, panel, width, height, frame_start, frame_end, tmp_dir) -> dict[int, str]:
        return {}

    def composite_frame(
        self,
        layer: SequenceLayer,
        frame: int,
        canvas: Image.Image,
        canvas_w: int,
        canvas_h: int,
        film_gate_wh: tuple[float, float] | None,
        captured_frames: dict[int, str],
    ) -> Image.Image:
        clamped = max(layer.frame_start, min(layer.frame_end, frame))
        try:
            seq_path = layer.file_pattern % clamped
        except (TypeError, ValueError):
            return canvas
        if not os.path.isfile(seq_path):
            return canvas
        try:
            src = Image.open(seq_path).convert("RGBA")
            return _place_image_on_canvas(
                canvas,
                src,
                canvas_w,
                canvas_h,
                layer.fit_mode,
                film_gate_wh,
            )
        except Exception as exc:
            logger.warning("Sequence frame %d failed: %s", frame, exc)
            return canvas


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_RENDERER_REGISTRY: dict[LayerType, LayerRenderer] = {
    LayerType.CAMERA: _CameraRenderer(),
    LayerType.IMAGE: _ImageRenderer(),
    LayerType.SEQUENCE: _SequenceRenderer(),
}


def get_renderer(layer_type: LayerType) -> LayerRenderer:
    """Return the renderer for *layer_type*.

    Raises:
        KeyError: If no renderer is registered for the type.
    """
    return _RENDERER_REGISTRY[layer_type]


def register_renderer(layer_type: LayerType, renderer: LayerRenderer) -> None:
    """Register (or replace) the renderer for *layer_type*."""
    _RENDERER_REGISTRY[layer_type] = renderer
