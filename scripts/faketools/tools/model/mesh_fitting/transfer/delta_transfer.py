"""Delta-based blend shape transfer — pure numpy, no Maya dependency.

Transfers blend shapes from a source base mesh to a fitted mesh by
computing per-vertex deltas (BS - source_base) and applying them to
the fitted mesh. Requires identical topology (same vertex count).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class TransferResult:
    """Result of transferring a single blend shape."""

    name: str
    vertices: np.ndarray  # (N, 3)
    max_delta_magnitude: float


@dataclass
class BatchTransferResult:
    """Result of a batch blend shape transfer."""

    results: list[TransferResult] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)


def validate_topology(
    source_base_verts: np.ndarray,
    bs_verts: np.ndarray,
    bs_name: str,
) -> str | None:
    """Check that a blend shape has the same vertex count as the source base.

    Returns:
        None if valid, or an error message string if invalid.
    """
    if source_base_verts.shape[0] != bs_verts.shape[0]:
        return f"'{bs_name}' has {bs_verts.shape[0]} vertices, expected {source_base_verts.shape[0]}"
    return None


def compute_delta(
    source_base_verts: np.ndarray,
    bs_verts: np.ndarray,
) -> np.ndarray:
    """Compute per-vertex delta: BS - source_base.

    Args:
        source_base_verts: (N, 3) base mesh vertices.
        bs_verts: (N, 3) blend shape vertices.

    Returns:
        (N, 3) delta array.
    """
    return bs_verts - source_base_verts


def apply_delta(
    fitted_verts: np.ndarray,
    delta: np.ndarray,
) -> np.ndarray:
    """Apply a delta to the fitted mesh vertices.

    Args:
        fitted_verts: (N, 3) fitted mesh vertices.
        delta: (N, 3) per-vertex delta.

    Returns:
        (N, 3) new vertex positions.
    """
    return fitted_verts + delta


def transfer_single(
    source_base_verts: np.ndarray,
    fitted_verts: np.ndarray,
    bs_verts: np.ndarray,
    bs_name: str,
) -> TransferResult:
    """Transfer a single blend shape from source to fitted mesh.

    Args:
        source_base_verts: (N, 3) source base vertices.
        fitted_verts: (N, 3) fitted mesh vertices.
        bs_verts: (N, 3) blend shape vertices.
        bs_name: Name for the result.

    Returns:
        TransferResult with new vertex positions.
    """
    delta = compute_delta(source_base_verts, bs_verts)
    new_verts = apply_delta(fitted_verts, delta)
    magnitudes = np.linalg.norm(delta, axis=1)
    return TransferResult(
        name=bs_name,
        vertices=new_verts,
        max_delta_magnitude=float(np.max(magnitudes)),
    )


def transfer_batch(
    source_base_verts: np.ndarray,
    fitted_verts: np.ndarray,
    bs_list: list[tuple[str, np.ndarray]],
    on_progress: Callable[[int, int, str], None] | None = None,
) -> BatchTransferResult:
    """Transfer a batch of blend shapes, skipping topology mismatches.

    Args:
        source_base_verts: (N, 3) source base vertices.
        fitted_verts: (N, 3) fitted mesh vertices.
        bs_list: List of (name, vertices) tuples for each blend shape.
        on_progress: Optional callback(current, total, name) for progress.

    Returns:
        BatchTransferResult with successful results and skipped entries.
    """
    result = BatchTransferResult()
    total = len(bs_list)

    for i, (name, verts) in enumerate(bs_list):
        if on_progress is not None:
            on_progress(i + 1, total, name)

        error = validate_topology(source_base_verts, verts, name)
        if error is not None:
            result.skipped.append((name, error))
            continue

        tr = transfer_single(source_base_verts, fitted_verts, verts, name)
        result.results.append(tr)

    return result
