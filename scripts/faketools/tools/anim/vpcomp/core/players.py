"""External player launchers for playblast output.

Strategy pattern: each Player subclass knows how to open a specific
application with the correct arguments for both image sequences and movies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import getLogger
import os
import shutil
import subprocess

from .model import Layer
from .playblast import DeliveryMode, OutputMode, PlayblastSettings

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# PlayblastResult — structured return value from run_playblast_composite
# ---------------------------------------------------------------------------


@dataclass
class PlayblastResult:
    """Structured result returned by :func:`run_playblast_composite`."""

    output_files: list[str]
    composite_dir: str | None
    per_layer_dirs: dict[int, str]
    active_layers: list[tuple[int, Layer]]
    settings: PlayblastSettings


# ---------------------------------------------------------------------------
# Player ABC + implementations
# ---------------------------------------------------------------------------


class Player(ABC):
    """Base class for external playblast viewers."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if this player can be used on the current system."""
        ...

    @abstractmethod
    def launch(self, result: PlayblastResult) -> None: ...


class OpenRVPlayer(Player):
    """Launch OpenRV via *rvpush* (reuses running instance)."""

    name = "OpenRV"

    @classmethod
    def is_available(cls) -> bool:
        """True if rvpush is found on PATH."""
        return shutil.which("rvpush") is not None

    @classmethod
    def _resolve_rvpush(cls) -> str | None:
        """Return rvpush path from PATH, or None."""
        return shutil.which("rvpush")

    def launch(self, result: PlayblastResult) -> None:
        s = result.settings

        # Movie → send MP4 file directly
        if s.output_mode is OutputMode.MOVIE:
            self._rvpush_set(result.output_files)
            return

        # Image Sequence
        if s.delivery_mode is DeliveryMode.COMPOSITE:
            sources = [self._make_seq_source(result.composite_dir, s)]
            self._rvpush_set(sources)
        else:
            # PER_LAYER / BOTH: stack all layers in RV with -over
            # RV treats the first source as foreground, so reverse
            # from back-to-front (LayerStack order) to front-to-back.
            sources = [
                self._make_seq_source(result.per_layer_dirs[idx], s) for idx, _ in reversed(result.active_layers) if idx in result.per_layer_dirs
            ]
            self._rvpush_set(sources, over=True)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _make_seq_source(dir_path: str | None, settings: PlayblastSettings) -> str:
        """Build a printf-style sequence path for rvpush."""
        fmt = f"%0{settings.frame_padding}d"
        pattern = f"{settings.filename_prefix}_{fmt}.png"
        return os.path.join(dir_path or "", pattern)

    @classmethod
    def _rvpush_set(cls, sources: list[str], *, over: bool = False) -> None:
        """Invoke ``rvpush set`` with the given source list."""
        rvpush = cls._resolve_rvpush()
        if not rvpush:
            raise FileNotFoundError("rvpush not found")
        cmd: list[str] = [rvpush, "set"]
        for src in sources:
            cmd += ["[", src, "]"]
        if over and len(sources) > 1:
            cmd.append("-over")
        logger.info("rvpush command: %s", cmd)
        subprocess.Popen(cmd)


class FallbackPlayer(Player):
    """Open the first output file with the OS default application."""

    name = "System Default"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def launch(self, result: PlayblastResult) -> None:
        if not result.output_files:
            return
        first = result.output_files[0]
        if os.name == "nt":
            os.startfile(first)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open", first])


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Priority order: first match wins in get_available_players().
PLAYERS: list[Player] = [OpenRVPlayer(), FallbackPlayer()]


def get_available_players() -> list[Player]:
    """Return players whose is_available() returns True (priority order)."""
    return [p for p in PLAYERS if p.is_available()]
