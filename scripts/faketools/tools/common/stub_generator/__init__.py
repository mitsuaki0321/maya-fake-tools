"""
Maintenance library for generating ``maya.cmds`` / ``maya.api.OpenMaya``
autocomplete stubs.

**Not a FakeTools menu tool.** The ``TOOL_CONFIG`` attribute is intentionally
absent so :class:`~faketools.core.registry.ToolRegistry` skips this module.
Stubs are generated manually by maintainers inside each supported Maya
version and the resulting ``.pyi`` files are committed under
``scripts/faketools/resources/maya_stubs/``. End users then get autocomplete
for ``cmds`` / ``OpenMaya`` without running a generator tool themselves.

See :mod:`.command` for the regenerate-and-commit workflow.
"""
