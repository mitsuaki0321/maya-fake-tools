"""Auto-detect numbered image sequences from a single sample file.

Supported naming patterns:
    name_001.png   (separator + digits)
    name.001.png   (dot separator + digits)
    name001.png    (digits directly appended)

Returns a printf-style pattern, frame_start, and frame_end by scanning the
directory for all matching files.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
import os
import re

logger = getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _build_sequence_re() -> re.Pattern[str]:
    """Build the sequence regex dynamically from SUPPORTED_EXTENSIONS."""
    # Strip leading dots and escape for regex, e.g. {".png", ".jpeg"} -> "png|jpeg"
    alts = "|".join(re.escape(ext.lstrip(".")) for ext in sorted(SUPPORTED_EXTENSIONS))
    return re.compile(
        rf"^(.*?)(\d+)(\.(?:{alts}))$",
        re.IGNORECASE,
    )


# Regex: capture (prefix)(digits)(extension)
# Matches the *last* contiguous digit group before the extension.
_SEQUENCE_RE = _build_sequence_re()


@dataclass(frozen=True)
class SequenceInfo:
    """Result of a successful sequence detection."""

    file_pattern: str  # printf-style, e.g. "img.%04d.png"
    frame_start: int
    frame_end: int
    frame_count: int


def detect_sequence(sample_path: str) -> SequenceInfo | None:
    """Detect an image sequence from a single sample file path.

    Args:
        sample_path: Absolute path to one file in the sequence.

    Returns:
        *SequenceInfo* on success, *None* if no sequence could be detected.
    """
    sample_path = os.path.normpath(sample_path)
    directory = os.path.dirname(sample_path)
    filename = os.path.basename(sample_path)

    m = _SEQUENCE_RE.match(filename)
    if m is None:
        logger.warning("No sequence pattern found in: %s", filename)
        return None

    prefix, digits, ext = m.group(1), m.group(2), m.group(3)
    padding = len(digits)

    # Build a regex to find all siblings with the same prefix/ext/padding
    # Allow varying digit lengths >= padding (e.g. 0001 and 10000 both match)
    sibling_re = re.compile(
        re.escape(prefix) + r"(\d{" + str(padding) + r",})" + re.escape(ext) + "$",
        re.IGNORECASE,
    )

    frames: list[int] = []
    try:
        for entry in os.listdir(directory):
            sm = sibling_re.match(entry)
            if sm:
                frames.append(int(sm.group(1)))
    except OSError as exc:
        logger.error("Failed to scan directory %s: %s", directory, exc)
        return None

    if not frames:
        logger.warning("No sequence frames found for pattern in: %s", directory)
        return None

    frames.sort()
    frame_start = frames[0]
    frame_end = frames[-1]

    # Build printf pattern
    pattern = os.path.join(directory, f"{prefix}%0{padding}d{ext}")

    logger.debug(
        "Detected sequence: pattern=%s range=%d-%d count=%d",
        pattern,
        frame_start,
        frame_end,
        len(frames),
    )

    return SequenceInfo(
        file_pattern=pattern,
        frame_start=frame_start,
        frame_end=frame_end,
        frame_count=len(frames),
    )
