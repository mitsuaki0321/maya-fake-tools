"""One-shot benchmark: autocomplete fast-path filter strategies.

Loads identifier lists from the bundled Maya stubs and times three
strategies over a realistic query set:

- prefix               : str.startswith(query)                (current)
- ci_substring         : query.lower() in name.lower()        (target)
- subsequence          : subsequence check on lowered name    (fuzzy)

Run:
    uv run python scripts/debug/benchmark_autocomplete_filter.py

Not part of the shipped code — safe to delete after confirming results.
"""

from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
STUBS_ROOT = REPO_ROOT / "scripts" / "faketools" / "resources" / "maya_stubs"

# Matches the three top-level stub shapes we emit:
#   def name(...): ...
#   class name:
#   name: Any = ...
_TOP_LEVEL_NAME_RE = re.compile(r"^(?:def|class)\s+(\w+)|^(\w+)\s*:\s*Any\s*=\s*\.\.\.")


def extract_names(pyi_path: Path) -> list[str]:
    names: list[str] = []
    for line in pyi_path.read_text(encoding="utf-8").splitlines():
        if not line or line[0].isspace():
            continue
        match = _TOP_LEVEL_NAME_RE.match(line)
        if match:
            names.append(match.group(1) or match.group(2))
    return names


# ---------------- strategies ----------------
# Each takes pre-split (names, names_lower) so none of them pay a repeated
# lowercase cost that the real engine would amortise at cache populate time.

FilterFn = Callable[[list[str], list[str], str, str], list[str]]


def match_prefix(names: list[str], names_lower: list[str], query: str, query_lower: str) -> list[str]:
    return [n for n in names if n.startswith(query)]


def match_ci_substring(names: list[str], names_lower: list[str], query: str, query_lower: str) -> list[str]:
    return [n for n, nl in zip(names, names_lower) if query_lower in nl]


def match_subsequence(names: list[str], names_lower: list[str], query: str, query_lower: str) -> list[str]:
    out: list[str] = []
    for n, nl in zip(names, names_lower):
        it = iter(nl)
        if all(ch in it for ch in query_lower):
            out.append(n)
    return out


STRATEGIES: dict[str, FilterFn] = {
    "prefix": match_prefix,
    "ci_substring": match_ci_substring,
    "subsequence": match_subsequence,
}


# ---------------- driver ----------------


def bench(label: str, names: list[str], queries: list[str], iterations: int = 500) -> None:
    names_lower = [n.lower() for n in names]
    print(f"\n=== {label} ({len(names)} names, {iterations} iterations per cell) ===")
    header = f"{'query':<10}" + "".join(f"{s:>30}" for s in STRATEGIES)
    print(header)
    print("-" * len(header))
    for query in queries:
        q_lower = query.lower()
        cells: list[str] = [f"{query:<10}"]
        for fn in STRATEGIES.values():
            # quick warmup
            fn(names, names_lower, query, q_lower)
            start = time.perf_counter()
            for _ in range(iterations):
                result = fn(names, names_lower, query, q_lower)
            per_call_ms = (time.perf_counter() - start) * 1000 / iterations
            cells.append(f"{per_call_ms:>7.3f} ms / {len(result):>4} hits".rjust(30))
        print("".join(cells))


def main() -> None:
    # Pick the largest Maya version we have — stub sizes are effectively
    # equivalent across versions for filter cost purposes.
    version = "maya2025"
    cmds_file = STUBS_ROOT / version / "maya-stubs" / "cmds.pyi"
    om_file = STUBS_ROOT / version / "maya-stubs" / "api" / "OpenMaya.pyi"

    if not cmds_file.exists():
        raise SystemExit(f"stub not found: {cmds_file}")

    cmds_names = extract_names(cmds_file)
    om_names = extract_names(om_file)
    print(f"cmds={len(cmds_names)} names, OpenMaya top-level={len(om_names)} names")

    # Queries chosen to exercise (a) first-character typing, (b) typical
    # mid-identifier drill-in, (c) cases where prefix matches nothing but
    # substring/subsequence do.
    cmds_queries = ["p", "po", "poly", "polyC", "ls", "xform", "Cube", "constrain"]
    om_queries = ["M", "MV", "MVec", "MPlug", "Fn", "Matrix"]

    bench("cmds (~lowerCamel, ~1500 names)", cmds_names, cmds_queries)
    bench("OpenMaya top-level (~UpperCamel)", om_names, om_queries)


if __name__ == "__main__":
    main()
