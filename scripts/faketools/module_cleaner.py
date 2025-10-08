"""
FakeTools module cleanup utility.

This module provides functionality to safely remove all faketools
modules from memory and close any running tool instances.

Usage:
    import faketools.module_cleaner
    faketools.module_cleaner.cleanup()

    # Then restart faketools
    import faketools
    faketools.menu.add_menu()
"""

import gc
import logging
import sys

# Note: We use basic logging here to avoid dependency on logging_config
# which might be cleaned up during module cleanup
logger = logging.getLogger(__name__)


def close_tools():
    """Close any running tool instances before cleanup."""
    try:
        # Try to close all open tool windows
        import maya.cmds as cmds

        # List all windows and close faketools-related ones
        all_windows = cmds.lsUI(windows=True) or []
        closed_count = 0

        for window in all_windows:
            # Check if window name contains faketools-related identifiers
            if any(keyword in window for keyword in ["faketools", "FakeTools", "MainWindow"]):
                try:
                    if cmds.window(window, exists=True):
                        cmds.deleteUI(window, window=True)
                        closed_count += 1
                        logger.debug(f"Closed window: {window}")
                except RuntimeError:
                    # Window might be already deleted
                    pass

        if closed_count > 0:
            logger.info(f"Closed {closed_count} tool window(s)")

    except ImportError:
        # Maya not available
        pass
    except Exception as e:
        logger.warning(f"Error closing tools: {e}")


def remove_menu():
    """Remove FakeTools menu from Maya."""
    try:
        from . import menu

        menu.remove_menu()
        logger.info("FakeTools menu removed")
    except ImportError:
        # Menu module not loaded
        pass
    except Exception as e:
        logger.warning(f"Error removing menu: {e}")


def cleanup():
    """
    Clean up all faketools modules from memory.

    This function:
    1. Closes any running tool instances
    2. Removes the FakeTools menu
    3. Removes all faketools modules from sys.modules
    4. Forces garbage collection
    """
    logger.info("=" * 50)
    logger.info("FakeTools - Module Cleanup")
    logger.info("=" * 50)

    # Step 1: Close any running tool instances
    close_tools()

    # Step 2: Remove FakeTools menu
    remove_menu()

    # Step 3: Find all faketools modules
    modules_to_remove = []
    for module_name in list(sys.modules.keys()):
        if "faketools" in module_name:
            modules_to_remove.append(module_name)

    # Step 4: Remove modules
    if modules_to_remove:
        logger.info(f"Removing {len(modules_to_remove)} modules...")
        for module_name in sorted(modules_to_remove, reverse=True):
            if module_name in sys.modules:
                del sys.modules[module_name]
                logger.debug(f"  Removed: {module_name}")
    else:
        logger.info("No faketools modules found to remove")

    # Step 5: Force garbage collection
    gc.collect()

    logger.info("Cleanup complete!")
    logger.info("Now run: import faketools; faketools.menu.add_menu()")


# Convenience function for direct execution
def clean():
    """Short alias for cleanup()."""
    cleanup()


if __name__ == "__main__":
    cleanup()
