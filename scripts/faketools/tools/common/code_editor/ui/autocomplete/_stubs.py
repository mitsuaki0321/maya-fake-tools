"""Maya stub-path setup for the shared :class:`JediEngine`.

Lives next to the autocomplete controller so the editor widget itself
stays Maya-agnostic at module scope. The single shared engine is reused
across all ``CodeEditor`` instances because jedi caches results by
source hash internally.

:func:`get_shared_engine` is a lazy getter — first call configures the
stub paths (a Maya ``cmds.about`` lookup), subsequent calls are free.
"""

from __future__ import annotations

from logging import getLogger
import time

from ...command.autocomplete import JediEngine

logger = getLogger(__name__)

_SHARED_JEDI_ENGINE = JediEngine()
_STUB_PATHS_CONFIGURED = False


def get_shared_engine() -> JediEngine:
    """Return the process-wide :class:`JediEngine`, configuring stubs once."""
    _configure_stub_paths()
    return _SHARED_JEDI_ENGINE


def _configure_stub_paths() -> None:
    """Point the shared jedi engine at the bundled Maya stubs.

    Runs lazily on the first editor construction so we only pay for the
    ``maya.cmds.about`` call when someone actually opens the Code Editor.
    Stubs live under ``faketools/resources/maya_stubs/maya{version}/`` and
    are committed with the repo — there's no per-user generator step. If we
    haven't shipped stubs for this Maya version yet (or we're outside Maya),
    this is a silent no-op and jedi falls back to live introspection via
    ``exec_globals``.
    """
    global _STUB_PATHS_CONFIGURED
    if _STUB_PATHS_CONFIGURED:
        return
    _STUB_PATHS_CONFIGURED = True

    t_start = time.perf_counter()

    try:
        import maya.cmds as _cmds  # type: ignore

        maya_version = str(_cmds.about(version=True))
    except Exception:
        return

    try:
        from ...command import stub_generator as stub_command
    except Exception as exc:
        logger.debug(f"stub_generator unavailable: {exc}")
        return

    t_exist_start = time.perf_counter()
    stubs_ok = stub_command.stubs_exist(maya_version)
    t_exist_ms = (time.perf_counter() - t_exist_start) * 1000
    if not stubs_ok:
        logger.info(f"Maya {maya_version} stubs not bundled with this build — cmds / OpenMaya autocomplete will fall back to live introspection.")
        return

    # Pin the stub dir at ``sys.path[0]`` *and* on the jedi ``Project`` so
    # ``import maya`` resolves to the bundled ``maya-stubs`` package before
    # Maya's real install (which otherwise wins because its path is
    # auto-discovered by jedi's environment detection).
    import sys

    stubs_root = stub_command.get_package_root(maya_version)
    stubs_root_str = str(stubs_root)
    if stubs_root_str not in sys.path:
        sys.path.insert(0, stubs_root_str)

    _SHARED_JEDI_ENGINE.set_extra_paths([stubs_root_str])
    t_total_ms = (time.perf_counter() - t_start) * 1000
    logger.info(f"Autocomplete stubs active: {stubs_root} (setup={t_total_ms:.1f}ms stubs_exist={t_exist_ms:.1f}ms)")
