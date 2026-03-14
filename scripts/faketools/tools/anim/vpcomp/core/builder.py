"""Build a VP2 MRenderOverride from a LayerStack.

Converts the layer stack into an ordered sequence of render operations:
  CameraLayer  → MSceneRender  (objectSet-filtered scene draw)
  ImageLayer   → MQuadRender   (alpha-blended fullscreen quad)
  SequenceLayer→ MQuadRender   (alpha-blended quad, frame-synced texture swap)
  (final)      → MPresentTarget
"""

from __future__ import annotations

import contextlib
from logging import getLogger
import os

import maya.api.OpenMaya as om  # type: ignore
import maya.api.OpenMayaRender as omr  # type: ignore
import maya.cmds as cmds  # type: ignore
import maya.OpenMayaUI as omui  # type: ignore

from .geometry import compute_film_gate_rect_from_params, compute_placement_rect
from .model import CameraLayer, FitMode, ImageLayer, LayerStack, SequenceLayer
from .scene_queries import (
    camera_dag_path,
    camera_shape,
    create_object_set,
    parse_film_fit,
    query_panel_camera,
)

logger = getLogger(__name__)

OVERRIDE_NAME = "vpcomp_override"


# ---------------------------------------------------------------------------
# Maya-dependent wrappers (thin delegation to pure-math functions above)
# ---------------------------------------------------------------------------

_FULL_RECT = om.MFloatPoint(0.0, 0.0, 1.0, 1.0)


def compute_film_gate_rect(vp_w: int, vp_h: int, camera: str) -> om.MFloatPoint:
    """Compute the filmGate rectangle matching Maya's displayFilmGate.

    Thin wrapper around :func:`compute_film_gate_rect_from_params` that
    reads camera attributes from the Maya scene.

    Returns:
        ``MFloatPoint(x, y, width, height)`` in normalised viewport
        coordinates (0-1).
    """
    if vp_w <= 0 or vp_h <= 0:
        return _FULL_RECT

    shape = camera_shape(camera)
    hfa = cmds.camera(shape, q=True, horizontalFilmAperture=True)
    vfa = cmds.camera(shape, q=True, verticalFilmAperture=True)
    film_fit = parse_film_fit(cmds.camera(shape, q=True, filmFit=True))
    overscan = cmds.camera(shape, q=True, overscan=True)

    x, y, w, h = compute_film_gate_rect_from_params(vp_w, vp_h, hfa, vfa, film_fit, overscan)
    return om.MFloatPoint(x, y, w, h)


def _get_viewport_size(panel: str) -> tuple[int, int]:
    """Return (width, height) in pixels for a model panel."""
    try:
        view = omui.M3dView()
        omui.M3dView.getM3dViewFromModelPanel(panel, view)
        return (view.portWidth(), view.portHeight())
    except Exception:
        return (0, 0)


def _compute_viewport_rect(
    img_w: int,
    img_h: int,
    vp_w: int,
    vp_h: int,
    fit_mode: FitMode,
    reference_camera: str | None = None,
) -> om.MFloatPoint:
    """Return ``MFloatPoint(x, y, w, h)`` in normalised viewport coords.

    Thin wrapper around :func:`compute_placement_rect` that resolves a
    filmGate from the live Maya camera when needed.
    """
    film_gate_wh: tuple[float, float] | None = None

    if fit_mode in (FitMode.FILMGATE_HEIGHT, FitMode.FILMGATE_WIDTH) and reference_camera is not None:
        try:
            fg = compute_film_gate_rect(vp_w, vp_h, reference_camera)
            film_gate_wh = (fg[2], fg[3])
        except Exception:
            film_gate_wh = None

    x, y, w, h = compute_placement_rect(
        img_w,
        img_h,
        vp_w,
        vp_h,
        fit_mode,
        film_gate_wh,
    )
    return om.MFloatPoint(x, y, w, h)


def _read_image_size(path: str) -> tuple[int, int]:
    """Read image dimensions via MImage. Returns (width, height)."""
    try:
        img = om.MImage()
        img.readFromFile(path)
        w, h = img.getSize()
        return max(1, int(w)), max(1, int(h))
    except Exception:
        return (0, 0)


# ---------------------------------------------------------------------------
# MSceneRender — camera + objectSet
# ---------------------------------------------------------------------------


class _SceneRender(omr.MSceneRender):
    """Scene render pass filtered by an objectSet with camera override."""

    def __init__(
        self,
        name: str,
        cam_path,
        object_set_name: str,
        clear_color: bool,
        clear_depth: bool,
    ):
        super().__init__(name)
        self._set_name = object_set_name

        self._cam_override = omr.MCameraOverride()
        if hasattr(self._cam_override, "setCameraPath"):
            self._cam_override.setCameraPath(cam_path)
        else:
            self._cam_override.mCameraPath = cam_path

        self._fallback_set = om.MSelectionList()
        self._fallback_set.add(self._set_name)
        self._error_logged = False

        self._clear_op = None
        try:
            self._clear_op = omr.MSceneRender.clearOperation(self)
        except Exception:
            with contextlib.suppress(Exception):
                self._clear_op = super().clearOperation()
        self._configure_clear(clear_color, clear_depth)

    def _configure_clear(self, clear_color: bool, clear_depth: bool) -> None:
        if not self._clear_op:
            return

        if hasattr(self._clear_op, "setMask"):
            mask = 0
            if clear_color:
                mask |= getattr(omr.MClearOperation, "kClearColor", 0)
            if clear_depth:
                mask |= getattr(omr.MClearOperation, "kClearDepth", 0)
            if mask == 0:
                mask = getattr(omr.MClearOperation, "kClearNone", 0)
            self._clear_op.setMask(mask)

        if clear_color and hasattr(self._clear_op, "setOverridesColors"):
            self._clear_op.setOverridesColors(False)

        logger.debug(
            "clear: pass=%s colorClear=%s depthClear=%s",
            self.name(),
            clear_color,
            clear_depth,
        )

    def _build_object_set_members(self):
        try:
            sel = om.MSelectionList()
            sel.add(self._set_name)
            fn_set = om.MFnSet(sel.getDependNode(0))
            members = fn_set.getMembers(flatten=True)
            if isinstance(members, om.MSelectionList):
                return members
            converted = om.MSelectionList()
            if members:
                for item in members:
                    converted.add(item)
            return converted
        except Exception as exc:
            if not self._error_logged:
                logger.warning(
                    "objectSetOverride fallback for %s: %s",
                    self._set_name,
                    exc,
                )
                self._error_logged = True
            return self._fallback_set

    def cameraOverride(self):
        return self._cam_override

    def objectSetOverride(self):
        return self._build_object_set_members()

    def clearOperation(self):
        if self._clear_op is not None:
            return self._clear_op
        try:
            return omr.MSceneRender.clearOperation(self)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# MQuadRender — static image (alpha blend)
# ---------------------------------------------------------------------------

_EFFECT_NAMES = ("Copy", "mayaBlitColorDepth")
_TEXTURE_PARAMS = ("gSourceTex", "gInputTex", "gColorTex")


def _acquire_shader(shader_mgr, label: str):
    for name in _EFFECT_NAMES:
        try:
            shader = shader_mgr.getEffectsFileShader(name, "")
            if shader:
                logger.debug("%s: shader=%s", label, name)
                return shader
        except Exception:
            continue
    logger.error("%s: no usable effect shader found", label)
    return None


def _create_blend_state():
    try:
        desc = omr.MBlendStateDesc()
        target = desc.targetBlends[0]
        target.blendEnable = True
        target.sourceBlend = omr.MBlendState.kSourceAlpha
        target.destinationBlend = omr.MBlendState.kInvSourceAlpha
        target.blendOperation = omr.MBlendState.kAdd
        target.alphaSourceBlend = omr.MBlendState.kOne
        target.alphaDestinationBlend = omr.MBlendState.kInvSourceAlpha
        target.alphaBlendOperation = omr.MBlendState.kAdd
        desc.targetBlends[0] = target
        return omr.MStateManager.acquireBlendState(desc)
    except Exception as exc:
        logger.warning("blend state failed: %s", exc)
        return None


def _create_depth_state():
    try:
        desc = omr.MDepthStencilStateDesc()
        desc.depthEnable = False
        desc.depthWriteEnable = False
        return omr.MStateManager.acquireDepthStencilState(desc)
    except Exception as exc:
        logger.warning("depth state failed: %s", exc)
        return None


class _QuadRenderBase(omr.MQuadRender):
    """Base for alpha-blended quad renders with aspect-ratio fitting.

    Provides shared blend/depth state management, clear operation, and
    viewport rectangle caching.  Subclasses implement ``shader()`` and
    texture acquisition.
    """

    def __init__(
        self,
        name: str,
        panel: str,
        fit_mode: FitMode,
        reference_camera: str | None,
        clear_color: bool,
        img_w: int,
        img_h: int,
    ):
        super().__init__(name)
        self._panel = panel
        self._fit_mode = fit_mode
        self._reference_camera = reference_camera
        self._clear_color = clear_color
        self._img_w = img_w
        self._img_h = img_h

        self._blend_state = None
        self._depth_state = None
        self._states_ready = False

        self._cached_rect = _FULL_RECT
        self._cached_vp_size: tuple[int, int] = (0, 0)

    def _ensure_states(self):
        if self._states_ready:
            return
        self._states_ready = True
        self._blend_state = _create_blend_state()
        self._depth_state = _create_depth_state()

    def blendStateOverride(self):
        self._ensure_states()
        return self._blend_state

    def depthStencilStateOverride(self):
        self._ensure_states()
        return self._depth_state

    def clearOperation(self):
        op = super().clearOperation()
        if op and hasattr(op, "setMask"):
            if self._clear_color:
                mask = getattr(omr.MClearOperation, "kClearColor", 0) | getattr(omr.MClearOperation, "kClearDepth", 0)
                op.setMask(mask)
                if hasattr(op, "setOverridesColors"):
                    op.setOverridesColors(False)
            else:
                op.setMask(getattr(omr.MClearOperation, "kClearNone", 0))
        return op

    def viewportRectangleOverride(self):
        vp_size = _get_viewport_size(self._panel)
        if vp_size == self._cached_vp_size:
            return self._cached_rect
        self._cached_vp_size = vp_size
        self._cached_rect = _compute_viewport_rect(
            self._img_w,
            self._img_h,
            vp_size[0],
            vp_size[1],
            self._fit_mode,
            self._reference_camera,
        )
        return self._cached_rect


class _ImageQuadRender(_QuadRenderBase):
    """Fullscreen alpha-blended image quad with aspect-ratio fitting."""

    def __init__(
        self,
        name: str,
        image_path: str,
        panel: str,
        fit_mode: FitMode,
        reference_camera: str | None,
        clear_color: bool = False,
    ):
        img_w, img_h = _read_image_size(image_path)
        super().__init__(name, panel, fit_mode, reference_camera, clear_color, img_w, img_h)
        self._image_path = image_path
        self._shader_instance = None
        self._texture = None
        self._initialized = False
        self._failed = False

    def _init_resources(self) -> bool:
        if self._initialized:
            return not self._failed
        self._initialized = True

        shader_mgr = omr.MRenderer.getShaderManager()
        texture_mgr = omr.MRenderer.getTextureManager()
        if not shader_mgr or not texture_mgr:
            self._failed = True
            return False

        self._shader_instance = _acquire_shader(shader_mgr, "image")
        if not self._shader_instance:
            self._failed = True
            return False

        self._texture = self._acquire_texture(texture_mgr)
        if not self._texture:
            self._failed = True
            return False

        self._ensure_states()
        return True

    def _acquire_texture(self, texture_mgr):
        try:
            tex = texture_mgr.acquireTexture(self._image_path)
            if tex:
                return tex
        except Exception:
            pass

        try:
            img = om.MImage()
            img.readFromFile(self._image_path)
            w, h = img.getSize()
            w, h = int(w), int(h)
            pixels = img.pixels()
            if callable(pixels):
                pixels = pixels()
            rgba = bytes(pixels)[: w * h * 4]

            desc = omr.MTextureDescription()
            if hasattr(desc, "setToDefault2DTexture"):
                desc.setToDefault2DTexture()
            desc.fWidth = w
            desc.fHeight = h
            desc.fDepth = 1
            desc.fBytesPerRow = w * 4
            desc.fBytesPerSlice = w * h * 4
            desc.fMipmaps = 1
            desc.fArraySlices = 1

            tex = texture_mgr.acquireTexture(
                f"vpcomp::{self._image_path}",
                desc,
                rgba,
                False,
            )
            if tex:
                return tex
        except Exception as exc:
            logger.error("image: texture acquire failed: %r", exc)
        return None

    def shader(self):
        if not self._init_resources():
            return None
        for param in _TEXTURE_PARAMS:
            try:
                self._shader_instance.setParameter(param, self._texture)
                break
            except Exception:
                continue
        return self._shader_instance


# ---------------------------------------------------------------------------
# MQuadRender — image sequence (alpha blend, frame-synced)
# ---------------------------------------------------------------------------


class _SequenceQuadRender(_QuadRenderBase):
    """Alpha-blended image sequence quad. Swaps texture on frame change."""

    def __init__(
        self,
        name: str,
        pattern: str,
        frame_start: int,
        frame_end: int,
        panel: str,
        fit_mode: FitMode,
        reference_camera: str | None,
        clear_color: bool = False,
    ):
        self._pattern = pattern
        self._frame_start = frame_start
        self._frame_end = frame_end
        img_w, img_h = self._read_first_frame_size()
        super().__init__(name, panel, fit_mode, reference_camera, clear_color, img_w, img_h)

        self._shader_instance = None
        self._texture = None
        self._texture_mgr = None
        self._current_frame = None
        self._shader_ready = False

    def _read_first_frame_size(self) -> tuple[int, int]:
        for frame in range(self._frame_start, self._frame_end + 1):
            try:
                path = self._pattern % frame
            except (TypeError, ValueError):
                break
            if os.path.isfile(path):
                return _read_image_size(path)
        return (0, 0)

    def _ensure_shader(self) -> bool:
        if self._shader_ready:
            return self._shader_instance is not None
        self._shader_ready = True
        shader_mgr = omr.MRenderer.getShaderManager()
        if not shader_mgr:
            return False
        self._shader_instance = _acquire_shader(shader_mgr, "seq")
        return self._shader_instance is not None

    def _resolve_frame_path(self, frame: int) -> str | None:
        clamped = max(self._frame_start, min(self._frame_end, int(frame)))
        path = self._pattern % clamped
        if os.path.isfile(path):
            return path
        return None

    def _update_texture(self, frame: int) -> bool:
        if frame == self._current_frame:
            return self._texture is not None

        path = self._resolve_frame_path(frame)
        if path is None:
            return self._texture is not None

        if not self._texture_mgr:
            self._texture_mgr = omr.MRenderer.getTextureManager()
        if not self._texture_mgr:
            return False

        if self._texture is not None:
            with contextlib.suppress(Exception):
                self._texture_mgr.releaseTexture(self._texture)
            self._texture = None

        try:
            self._texture = self._texture_mgr.acquireTexture(path)
            if self._texture:
                self._current_frame = frame
                return True
        except Exception as exc:
            logger.error("seq: texture acquire failed frame=%d: %r", frame, exc)
        return False

    def shader(self):
        if not self._ensure_shader():
            return None

        frame = int(cmds.currentTime(q=True))
        self._update_texture(frame)

        if self._texture:
            for param in _TEXTURE_PARAMS:
                try:
                    self._shader_instance.setParameter(param, self._texture)
                    break
                except Exception:
                    continue
        return self._shader_instance


# ---------------------------------------------------------------------------
# MRenderOverride — assembled from LayerStack
# ---------------------------------------------------------------------------


class _VpcompOverride(omr.MRenderOverride):
    """MRenderOverride built from a vpcomp LayerStack."""

    def __init__(self, name: str, operations: list):
        super().__init__(name)
        self._ops = operations
        self._index = 0

    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def startOperationIterator(self):
        self._index = 0
        return True

    def renderOperation(self):
        return self._ops[self._index]

    def nextRenderOperation(self):
        self._index += 1
        return self._index < len(self._ops)

    def setup(self, destination):
        return True

    def cleanup(self):
        return None

    def uiName(self):
        return "VP Compositor"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _make_camera_op(
    layer: CameraLayer,
    op_index: int,
    is_first: bool,
) -> _SceneRender:
    """Create a _SceneRender operation for a camera layer."""
    create_object_set(layer.object_set)
    shape = camera_shape(layer.camera)
    dag_path = camera_dag_path(shape)
    op = _SceneRender(
        f"vpcomp_scene_{op_index}",
        dag_path,
        layer.object_set,
        clear_color=is_first,
        clear_depth=True,
    )
    logger.debug(
        "op[%d] SceneRender camera=%s set=%s clearColor=%s",
        op_index,
        layer.camera,
        layer.object_set,
        is_first,
    )
    return op


def _make_image_op(
    layer: ImageLayer,
    op_index: int,
    is_first: bool,
    panel: str,
    ref_cam: str | None,
) -> _ImageQuadRender:
    """Create an _ImageQuadRender operation for an image layer."""
    fm = layer.fit_mode
    rc = ref_cam if fm in (FitMode.FILMGATE_HEIGHT, FitMode.FILMGATE_WIDTH) else None
    op = _ImageQuadRender(
        f"vpcomp_image_{op_index}",
        layer.file_path,
        panel,
        fm,
        rc,
        clear_color=is_first,
    )
    logger.debug(
        "op[%d] ImageQuadRender path=%s fit=%s",
        op_index,
        layer.file_path,
        fm.value,
    )
    return op


def _make_sequence_op(
    layer: SequenceLayer,
    op_index: int,
    is_first: bool,
    panel: str,
    ref_cam: str | None,
) -> _SequenceQuadRender:
    """Create a _SequenceQuadRender operation for a sequence layer."""
    fm = layer.fit_mode
    rc = ref_cam if fm in (FitMode.FILMGATE_HEIGHT, FitMode.FILMGATE_WIDTH) else None
    op = _SequenceQuadRender(
        f"vpcomp_seq_{op_index}",
        layer.file_pattern,
        layer.frame_start,
        layer.frame_end,
        panel,
        fm,
        rc,
        clear_color=is_first,
    )
    logger.debug(
        "op[%d] SequenceQuadRender pattern=%s range=%d-%d fit=%s",
        op_index,
        layer.file_pattern,
        layer.frame_start,
        layer.frame_end,
        fm.value,
    )
    return op


def build_override(
    stack: LayerStack,
    panel: str,
    override_name: str = OVERRIDE_NAME,
    reference_camera: str | None = None,
) -> _VpcompOverride:
    """Convert a *LayerStack* into a live ``MRenderOverride``.

    For each visible layer an appropriate render operation is created:

    - **CameraLayer** → ``_SceneRender``
      (first camera clears color+depth; subsequent cameras clear depth only)
    - **ImageLayer** → ``_ImageQuadRender`` (alpha blend, aspect-ratio fitted)
    - **SequenceLayer** → ``_SequenceQuadRender`` (alpha blend, frame sync, fitted)

    An ``MPresentTarget`` is appended as the final operation.

    Camera layers whose objectSets do not yet exist will have them
    auto-created.  Each image/sequence layer carries its own ``fit_mode``.

    Args:
        stack: Layer stack to convert.
        panel: Model panel name (e.g. ``"modelPanel4"``).
        override_name: Name for the MRenderOverride.
        reference_camera: Camera for filmGate modes. If *None*, the panel's
            active camera at call time is used.

    Raises:
        RuntimeError: If the stack contains no visible layers.
    """
    ref_cam: str | None = reference_camera or query_panel_camera(panel)
    logger.debug("reference camera = %s", ref_cam)

    ops: list = []
    op_index = 0

    for layer in stack.layers:
        if not layer.visible:
            continue

        is_first = len(ops) == 0

        if isinstance(layer, CameraLayer):
            ops.append(_make_camera_op(layer, op_index, is_first))
        elif isinstance(layer, ImageLayer):
            ops.append(_make_image_op(layer, op_index, is_first, panel, ref_cam))
        elif isinstance(layer, SequenceLayer):
            ops.append(_make_sequence_op(layer, op_index, is_first, panel, ref_cam))

        op_index += 1

    if not ops:
        raise RuntimeError("No visible layers to build override from")

    ops.append(omr.MPresentTarget("vpcomp_present"))
    logger.info(
        "Built override '%s' with %d operation(s)",
        override_name,
        len(ops),
    )
    return _VpcompOverride(override_name, ops)
