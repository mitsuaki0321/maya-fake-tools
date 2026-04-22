# Maya Autocomplete Stubs

This directory contains pre-generated `.pyi` stubs for `maya.cmds` and
the `maya.api.OpenMaya*` family, committed per Maya version. The Code
Editor's autocomplete picks them up automatically — **end users don't
have to run anything**.

Layout:

```
maya_stubs/
  maya2023/
    maya-stubs/
      __init__.pyi
      cmds.pyi
      api/
        __init__.pyi
        OpenMaya.pyi
        OpenMayaAnim.pyi
        OpenMayaRender.pyi
        OpenMayaUI.pyi
  maya2025/
    ...
```

## Regenerating (maintainer-only)

When a new Maya version ships or plugins meaningfully change the command
set, open the target Maya, open its Script Editor, and run:

```python
from faketools.tools.common.code_editor.command import stub_generator
stub_generator.generate_bundled()
```

This writes straight into this folder. Commit the diff.

Because flag sets and OpenMaya bindings vary across releases, stubs are
kept per Maya version. `maya2023` and `maya2025` are both supported today.
