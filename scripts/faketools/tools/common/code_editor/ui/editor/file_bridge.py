"""Editor-aware adapters around :mod:`...command.file_io`.

The lower :mod:`...command.file_io` module returns ``(value, error)``
tuples so the UI can choose how to surface failures. These helpers are
the UI side: they call into ``file_io``, raise a themed message box on
error, and update the editor's bookkeeping (``file_path`` /
``is_modified`` / ``QTextDocument.setModified``) on success.

:func:`get_display_name` belongs here because the asterisk-and-fallback
logic reads the same ``file_path`` / ``is_modified`` state the load /
save paths write.
"""

import os

from ...command import file_io
from ...languages import get_profile_for_path
from ..dialogs import CodeEditorMessageBox


def load_file(editor, file_path: str) -> bool:
    """Load ``file_path`` into ``editor`` and rebind the language profile.

    The tab widget constructs editors with the default profile and only
    learns the file path here, so a ``foo.mel`` opened into a freshly
    built editor would stay bound to Python without this rebind —
    Run / placeholder / highlighter would all dispatch to the wrong
    language.
    """
    content, error = file_io.read_text(file_path)
    if content is None:
        CodeEditorMessageBox.warning(editor, "Error", f"Failed to load file: {error}")
        return False
    new_language = get_profile_for_path(file_path)
    if new_language is not editor.language:
        editor.set_language(new_language)
    editor.setPlainText(content)
    editor.file_path = file_path
    editor.is_modified = False
    return True


def save_file(editor, file_path: str = None) -> bool:
    """Write the editor's contents through the command-layer writer.

    Falls back to ``editor.file_path`` when ``file_path`` is omitted, so
    Ctrl+S on an already-named buffer doesn't need to know its own path.
    Returns False without writing when neither argument nor the editor
    carries a path (i.e. an Untitled buffer that hasn't been Save-As'd).
    """
    if file_path is None:
        file_path = editor.file_path
    if file_path is None:
        return False

    error = file_io.write_text(file_path, editor.toPlainText())
    if error:
        CodeEditorMessageBox.warning(editor, "Error", f"Failed to save file: {error}")
        return False

    editor.file_path = file_path
    editor.is_modified = False
    editor.document().setModified(False)
    return True


def get_display_name(editor) -> str:
    """Return the tab label for ``editor``.

    Preview tabs surface their ``preview_title`` verbatim (no asterisk —
    they're transient by definition). Draft tabs are always "Draft" and
    never get an asterisk so they don't read as "modified" in the UI.
    Regular tabs show the basename, with ``*`` appended when either our
    own ``is_modified`` flag or the underlying ``QTextDocument`` reports
    a pending edit.
    """
    if getattr(editor, "is_preview", False):
        return getattr(editor, "preview_title", None) or "Preview"

    is_draft = getattr(editor, "is_draft", False)
    if is_draft:
        name = "Draft"
    elif editor.file_path:
        name = os.path.basename(editor.file_path)
    else:
        name = "Untitled"

    is_modified = (editor.is_modified or editor.document().isModified()) and not is_draft
    if is_modified:
        name += "*"
    return name


__all__ = ["get_display_name", "load_file", "save_file"]
