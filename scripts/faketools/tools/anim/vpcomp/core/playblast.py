"""Playblast compositing orchestrator.

Coordinates per-layer renderers (capture + composite) into a PNG sequence.
Heavy lifting is delegated to :mod:`vpcomp.core.layer_renderers`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from logging import getLogger
import os
import re
import shutil
import tempfile
from typing import Callable

import maya.cmds as cmds  # type: ignore

from .ffmpeg import check_ffmpeg, encode_sequence_to_mp4
from .layer_renderers import HAS_PILLOW, get_camera_film_gate_wh, get_renderer
from .model import CameraLayer, LayerStack

logger = getLogger(__name__)

# Re-export for external consumers (playblast_ui.py etc.)
__all__ = [
    "DeliveryMode",
    "HAS_PILLOW",
    "LayerRenderConfig",
    "OutputMode",
    "PlayblastSettings",
    "run_playblast_composite",
]


# Deferred import to avoid circular dependency (players imports playblast)
def _make_result(
    output_files: list[str],
    composite_dir: str | None,
    per_layer_dirs: dict[int, str],
    active_layers: list[tuple[int, object]],
    settings: PlayblastSettings,
):
    """Build a PlayblastResult (lazy import to break circular ref)."""
    from .players import PlayblastResult

    return PlayblastResult(
        output_files=output_files,
        composite_dir=composite_dir,
        per_layer_dirs=per_layer_dirs,
        active_layers=active_layers,
        settings=settings,
    )


class OutputMode(Enum):
    """Playblast output format."""

    IMAGE_SEQUENCE = "image_sequence"
    MOVIE = "movie"


class DeliveryMode(Enum):
    """How playblast frames are delivered."""

    COMPOSITE = "composite"  # All layers merged into one sequence
    PER_LAYER = "per_layer"  # Each layer as a separate sequence
    BOTH = "both"  # Composite + per-layer


# ---------------------------------------------------------------------------
# Pillow import guard (conditional — only when actually running)
# ---------------------------------------------------------------------------

try:
    from PIL import Image  # type: ignore
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PlayblastSettings:
    """Configuration for a playblast composite run."""

    output_dir: str
    filename_prefix: str  # prefix for output files (e.g. "vpcomp" -> "vpcomp_0001.png")
    width: int
    height: int
    scale: float  # 0.01 – 1.0
    frame_start: int
    frame_end: int
    frame_padding: int  # zero-padding digits
    panel: str  # model panel to playblast from
    play_after: bool = False
    output_mode: OutputMode = OutputMode.IMAGE_SEQUENCE
    delivery_mode: DeliveryMode = DeliveryMode.COMPOSITE
    fps: float = 24.0
    renderer_override: str = ""  # rendererOverrideName ("" = Viewport 2.0)


@dataclass
class LayerRenderConfig:
    """Per-layer enable toggle for playblast."""

    layer_index: int  # index into LayerStack
    enabled: bool = True


# ---------------------------------------------------------------------------
# Panel state save / restore
# ---------------------------------------------------------------------------

# (key, query_fn(panel) -> value, restore_fn(panel, value) | None)
_PANEL_PROPS: list[tuple[str, Callable, Callable | None]] = [
    ("camera", lambda p: cmds.modelPanel(p, q=1, cam=1), lambda p, v: cmds.modelPanel(p, e=1, cam=v)),
    ("displayAppearance", lambda p: cmds.modelEditor(p, q=1, displayAppearance=1), None),
    ("bgColor", lambda p: cmds.displayRGBColor("background", q=1), lambda p, v: cmds.displayRGBColor("background", *v)),
    ("bgColorTop", lambda p: cmds.displayRGBColor("backgroundTop", q=1), lambda p, v: cmds.displayRGBColor("backgroundTop", *v)),
    ("bgColorBot", lambda p: cmds.displayRGBColor("backgroundBottom", q=1), lambda p, v: cmds.displayRGBColor("backgroundBottom", *v)),
    ("gradient", lambda p: cmds.displayPref(q=1, displayGradient=1), lambda p, v: cmds.displayPref(displayGradient=v)),
    ("hud", lambda p: cmds.modelEditor(p, q=1, hud=1), lambda p, v: cmds.modelEditor(p, e=1, hud=v)),
    ("grid", lambda p: cmds.modelEditor(p, q=1, grid=1), lambda p, v: cmds.modelEditor(p, e=1, grid=v)),
]


def _save_panel_state(panel: str) -> dict:
    """Save panel display state that will be modified during playblast."""
    state: dict = {}
    for key, query_fn, _ in _PANEL_PROPS:
        try:
            state[key] = query_fn(panel)
        except Exception:
            pass

    # Special: isolate select
    try:
        state["isolate"] = cmds.isolateSelect(panel, q=True, state=True)
    except Exception:
        state["isolate"] = False

    # Special: renderer override
    try:
        state["rendererOverrideName"] = cmds.modelEditor(panel, q=True, rendererOverrideName=True)
    except Exception:
        state["rendererOverrideName"] = ""

    return state


def _restore_panel_state(panel: str, state: dict) -> None:
    """Restore panel display state saved by _save_panel_state."""
    for key, _, restore_fn in _PANEL_PROPS:
        if restore_fn is None or key not in state:
            continue
        try:
            restore_fn(panel, state[key])
        except Exception:
            pass

    # Special: isolate — turn off first, then restore
    try:
        cmds.isolateSelect(panel, state=False)
    except Exception:
        pass
    if state.get("isolate"):
        try:
            cmds.isolateSelect(panel, state=True)
        except Exception:
            pass

    # Always restore to Viewport 2.0 after playblast
    try:
        cmds.modelEditor(panel, e=True, rendererOverrideName="")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNSAFE_DIR_CHARS = re.compile(r'[<>:"/\\|?*]')


def _sanitize_dirname(name: str) -> str:
    """Sanitize a layer name for use as a directory name."""
    sanitized = _UNSAFE_DIR_CHARS.sub("_", name)
    sanitized = sanitized.strip(" .")
    return sanitized or "_"


def _make_layer_dirs(
    active_layers: list[tuple[int, object]],
    output_dir: str,
) -> dict[int, str]:
    """Create per-layer subdirectories and return {layer_index: dir_path}.

    Duplicate sanitized names get ``_2``, ``_3`` suffixes.
    """
    used: dict[str, int] = {}
    result: dict[int, str] = {}
    for layer_idx, layer in active_layers:
        base = _sanitize_dirname(layer.name)
        if base in used:
            used[base] += 1
            dirname = f"{base}_{used[base]}"
        else:
            used[base] = 1
            dirname = base
        layer_dir = os.path.join(output_dir, dirname)
        os.makedirs(layer_dir, exist_ok=True)
        result[layer_idx] = layer_dir
    return result


# ---------------------------------------------------------------------------
# Pipeline phases (private)
# ---------------------------------------------------------------------------


def _build_active_layers(
    stack: LayerStack,
    render_configs: list[LayerRenderConfig],
    eff_w: int,
    eff_h: int,
) -> tuple[
    list[tuple[int, object]],
    str | None,
    tuple[float, float] | None,
]:
    """Filter visible+enabled layers and resolve film gate.

    Returns:
        ``(active_layers, ref_cam, film_gate_wh)``
    """
    enabled_map = {rc.layer_index: rc.enabled for rc in render_configs}
    active_layers: list[tuple[int, object]] = []
    for i, layer in enumerate(stack.layers):
        if enabled_map.get(i, True) and layer.visible:
            active_layers.append((i, layer))

    if not active_layers:
        raise RuntimeError("No enabled layers to composite")

    ref_cam: str | None = None
    for _, layer in active_layers:
        if isinstance(layer, CameraLayer):
            ref_cam = layer.camera
            break

    film_gate_wh: tuple[float, float] | None = None
    if ref_cam:
        film_gate_wh = get_camera_film_gate_wh(ref_cam, eff_w, eff_h)

    return active_layers, ref_cam, film_gate_wh


def _capture_layers(
    active_layers: list[tuple[int, object]],
    panel: str,
    eff_w: int,
    eff_h: int,
    settings: PlayblastSettings,
    tmp_dir: str,
    progress: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> tuple[dict[int, dict[int, str]], bool]:
    """Phase A: Capture camera layers via per-layer renderers.

    Returns:
        ``(cam_frames, interrupted)`` — *interrupted* is True when
        cancelled or ``cmds.playblast()`` was interrupted by Esc.
    """
    cam_frames: dict[int, dict[int, str]] = {}
    for layer_idx, layer in active_layers:
        if cancelled():
            return cam_frames, True
        renderer = get_renderer(layer.layer_type)
        captured = renderer.capture(
            layer,
            panel,
            eff_w,
            eff_h,
            settings.frame_start,
            settings.frame_end,
            tmp_dir,
        )
        if captured is None:
            return cam_frames, True
        if captured:
            cam_frames[layer_idx] = captured
            progress(f"Playblast: {layer.camera}")
    return cam_frames, False


def _composite_frames(
    active_layers: list[tuple[int, object]],
    settings: PlayblastSettings,
    cam_frames: dict[int, dict[int, str]],
    composite_dir: str,
    eff_w: int,
    eff_h: int,
    film_gate_wh: tuple[float, float] | None,
    progress: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> list[str]:
    """Phase B: Frame-by-frame Pillow composite."""
    output_files: list[str] = []
    for frame in range(settings.frame_start, settings.frame_end + 1):
        if cancelled():
            break
        progress(f"Compositing frame {frame}")
        canvas = Image.new("RGBA", (eff_w, eff_h), (0, 0, 0, 0))
        for layer_idx, layer in active_layers:
            renderer = get_renderer(layer.layer_type)
            captured = cam_frames.get(layer_idx, {})
            canvas = renderer.composite_frame(
                layer,
                frame,
                canvas,
                eff_w,
                eff_h,
                film_gate_wh,
                captured,
            )
        frame_str = str(frame).zfill(settings.frame_padding)
        out_name = f"{settings.filename_prefix}_{frame_str}.png"
        out_path = os.path.join(composite_dir, out_name)
        canvas.save(out_path, "PNG")
        output_files.append(out_path)
    return output_files


def _output_per_layer_frames(
    active_layers: list[tuple[int, object]],
    settings: PlayblastSettings,
    cam_frames: dict[int, dict[int, str]],
    eff_w: int,
    eff_h: int,
    film_gate_wh: tuple[float, float] | None,
    progress: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> tuple[dict[int, str], list[str]]:
    """Phase B2: Per-layer individual output.

    Returns:
        ``(layer_dirs, output_files)``
    """
    layer_dirs = _make_layer_dirs(active_layers, settings.output_dir)
    output_files: list[str] = []
    for frame in range(settings.frame_start, settings.frame_end + 1):
        if cancelled():
            break
        for layer_idx, layer in active_layers:
            if cancelled():
                break
            progress(f"Per-layer {layer.name} frame {frame}")
            canvas = Image.new("RGBA", (eff_w, eff_h), (0, 0, 0, 0))
            renderer = get_renderer(layer.layer_type)
            captured = cam_frames.get(layer_idx, {})
            canvas = renderer.composite_frame(
                layer,
                frame,
                canvas,
                eff_w,
                eff_h,
                film_gate_wh,
                captured,
            )
            frame_str = str(frame).zfill(settings.frame_padding)
            out_name = f"{settings.filename_prefix}_{frame_str}.png"
            out_path = os.path.join(layer_dirs[layer_idx], out_name)
            canvas.save(out_path, "PNG")
            output_files.append(out_path)
    return layer_dirs, output_files


def _encode_movie(
    settings: PlayblastSettings,
    tmp_dir: str,
    eff_w: int,
    eff_h: int,
    progress: Callable[[str], None],
) -> str:
    """Phase C: Encode PNG sequence to MP4 via ffmpeg."""
    progress("Encoding MP4...")
    padding_fmt = f"%0{settings.frame_padding}d"
    filename_pattern = f"{settings.filename_prefix}_{padding_fmt}.png"
    movie_name = f"{settings.filename_prefix}.mp4"
    movie_path = os.path.join(settings.output_dir, movie_name)
    encode_sequence_to_mp4(
        image_dir=tmp_dir,
        filename_pattern=filename_pattern,
        output_path=movie_path,
        fps=settings.fps,
        frame_start=settings.frame_start,
        width=eff_w,
        height=eff_h,
    )
    return movie_path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_playblast_composite(
    stack: LayerStack,
    settings: PlayblastSettings,
    render_configs: list[LayerRenderConfig],
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
):
    """Execute the full playblast composite pipeline.

    Returns:
        :class:`~vpcomp.core.players.PlayblastResult` with output paths
        and metadata for external player launch.

    Raises:
        RuntimeError: If Pillow is unavailable or no layers are enabled.
    """
    if not HAS_PILLOW:
        raise RuntimeError("Pillow is required for playblast compositing. Install it with: pip install Pillow")

    is_movie = settings.output_mode is OutputMode.MOVIE
    delivery = settings.delivery_mode
    do_composite = delivery in (DeliveryMode.COMPOSITE, DeliveryMode.BOTH)
    do_per_layer = delivery in (DeliveryMode.PER_LAYER, DeliveryMode.BOTH) and not is_movie

    if is_movie:
        check_ffmpeg()

    eff_w = max(1, int(settings.width * settings.scale))
    eff_h = max(1, int(settings.height * settings.scale))

    active_layers, ref_cam, film_gate_wh = _build_active_layers(
        stack,
        render_configs,
        eff_w,
        eff_h,
    )

    # Progress tracking
    frame_count = settings.frame_end - settings.frame_start + 1
    camera_count = sum(1 for _, ly in active_layers if isinstance(ly, CameraLayer))
    composite_frames = frame_count if do_composite else 0
    per_layer_frames = frame_count * len(active_layers) if do_per_layer else 0
    total_steps = camera_count + composite_frames + per_layer_frames + (1 if is_movie else 0)
    current_step = 0

    def _progress(msg: str) -> None:
        nonlocal current_step
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, msg)

    force_cancel = False

    def _cancelled() -> bool:
        return force_cancel or (cancel_check() if cancel_check else False)

    tmp_dir = tempfile.mkdtemp(prefix="vpcomp_pb_")
    output_files: list[str] = []
    layer_dirs: dict[int, str] = {}
    composite_dir: str | None = None
    panel = settings.panel
    saved_state = _save_panel_state(panel)

    try:
        cmds.modelEditor(
            panel,
            e=True,
            rendererOverrideName=settings.renderer_override,
        )
    except Exception:
        pass

    try:
        cam_frames, interrupted = _capture_layers(
            active_layers,
            panel,
            eff_w,
            eff_h,
            settings,
            tmp_dir,
            _progress,
            _cancelled,
        )
        if interrupted:
            force_cancel = True

        os.makedirs(settings.output_dir, exist_ok=True)
        composite_dir = tmp_dir if is_movie else settings.output_dir

        if do_composite:
            output_files = _composite_frames(
                active_layers,
                settings,
                cam_frames,
                composite_dir,
                eff_w,
                eff_h,
                film_gate_wh,
                _progress,
                _cancelled,
            )

        if do_per_layer and not _cancelled():
            dirs, per_layer_files = _output_per_layer_frames(
                active_layers,
                settings,
                cam_frames,
                eff_w,
                eff_h,
                film_gate_wh,
                _progress,
                _cancelled,
            )
            layer_dirs.update(dirs)
            if not do_composite:
                output_files.extend(per_layer_files)

        if is_movie and output_files and not _cancelled():
            movie_path = _encode_movie(settings, tmp_dir, eff_w, eff_h, _progress)
            output_files = [movie_path]

    finally:
        _restore_panel_state(panel, saved_state)
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    logger.info(
        "Playblast composite complete: %d frame(s) -> %s",
        len(output_files),
        settings.output_dir,
    )
    return _make_result(
        output_files=output_files,
        composite_dir=composite_dir if do_composite else None,
        per_layer_dirs=layer_dirs if do_per_layer else {},
        active_layers=active_layers,
        settings=settings,
    )
