"""Dataclasses for the language profile system.

Kept separate from ``__init__.py`` so the module can re-export both the
types and the concrete profile instances without running into circular
imports between the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .folding_strategy import FoldingStrategy
from .indent_resolver import IndentResolver


@dataclass(frozen=True)
class ShelfConfig:
    """Maya shelf-button configuration for a language.

    Attributes:
        source_type (str): ``cmdScrollFieldExecuter`` / ``shelfButton -stp`` value
            (e.g. ``"python"`` or ``"mel"``).
        label (str): Button label shown on the shelf.
        icon (str): Icon resource name (e.g. ``"pythonFamily.png"``).
    """

    source_type: str
    label: str
    icon: str


@dataclass(frozen=True)
class LanguageProfile:
    """Per-language configuration for the code editor.

    Required fields identify the language and its file association.
    Optional fields enable individual editor features; a ``None`` value
    disables that feature for the language and consumers should treat it as
    a signal to skip / hide / grey out the corresponding UI affordance.

    Attributes:
        id (str): Stable identifier used as a settings key (e.g. ``"python"``).
        display_name (str): Human-readable name shown in UI.
        extensions (tuple[str, ...]): File extensions that map to this profile,
            including the leading dot (e.g. ``(".py",)``).
        default_extension (str): Extension applied when creating new files.
        line_comment (Optional[str]): Line-comment prefix. ``None`` disables
            the comment toggle keybinding.
        indent_resolver (Optional[IndentResolver]): Language-specific
            auto-indent strategy. Subclass :class:`IndentResolver` and
            override :meth:`_indent_on_enter` (and optionally
            :meth:`_iter_code_brackets` etc.). ``None`` falls back to a
            default resolver that only applies the bracket-based Rules
            (hanging indent / closing alignment / current-indent carry-over).
        source_type (Optional[str]): ``cmdScrollFieldExecuter`` ``sourceType``.
            ``None`` disables run-related actions.
        shelf_config (Optional[ShelfConfig]): Shelf-button settings. ``None``
            disables the "Add to Shelf" menu item.
        context_menu_extender (Optional[Callable]): Callback that adds
            language-specific entries to the right-click menu (Inspect /
            Reload / etc.). The extender owns each entry's full lifecycle
            — wiring the menu item, dispatching the action, and running
            inspection snippets through the executer — so all the
            language-specific code lives here rather than being split
            across multiple profile fields. ``None`` skips the
            language-specific section. The extender receives the raw
            selected text and is responsible for any sanity checks; the
            execution side already surfaces NameError-style failures
            gracefully so we don't gate menu items on identifier syntax.
        highlighter_factory (Optional[Callable]): Factory returning a
            ``QSyntaxHighlighter``. ``None`` falls back to plain text.
        completion_engine_factory (Optional[Callable]): Factory returning a
            completion engine. ``None`` disables autocomplete.
        folding_strategy (Optional[FoldingStrategy]): Per-language fold-region
            detector. Subclass :class:`FoldingStrategy` and override
            :meth:`detect`. ``None`` disables folding for the language;
            ``CodeFoldingManager`` then keeps an empty region map.
    """

    id: str
    display_name: str
    extensions: tuple[str, ...]
    default_extension: str

    line_comment: Optional[str] = None

    indent_resolver: Optional[IndentResolver] = None

    source_type: Optional[str] = None

    shelf_config: Optional[ShelfConfig] = None

    context_menu_extender: Optional[Callable] = None

    highlighter_factory: Optional[Callable] = None
    completion_engine_factory: Optional[Callable] = None
    folding_strategy: Optional[FoldingStrategy] = None

    @property
    def file_filter(self) -> str:
        """Qt file dialog filter, e.g. ``"Python Files (*.py)"``."""
        ext_pattern = " ".join(f"*{e}" for e in self.extensions)
        return f"{self.display_name} Files ({ext_pattern})"

    @property
    def line_comment_with_space(self) -> Optional[str]:
        """``line_comment`` followed by a single space, or ``None`` when unset."""
        return f"{self.line_comment} " if self.line_comment else None


__all__ = ["LanguageProfile", "ShelfConfig"]
