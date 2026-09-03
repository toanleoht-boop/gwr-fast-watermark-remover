"""Keep the bundled Qt runtime isolated from incompatible DLLs on PATH."""

import builtins
import os
import sys

bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
qt_root = os.path.join(bundle_root, "PyQt6", "Qt6")
qt_bin = os.path.join(qt_root, "bin")
qt_plugins = os.path.join(qt_root, "plugins")

if os.path.isdir(qt_plugins):
    os.environ["QT_PLUGIN_PATH"] = qt_plugins

if os.name == "nt" and os.path.isdir(qt_bin):
    # Keep the handle alive for the whole process; otherwise Windows removes
    # the directory from the DLL search path when it is garbage-collected.
    builtins._gwr_qt_dll_handle = os.add_dll_directory(qt_bin)
    os.environ["PATH"] = qt_bin + os.pathsep + os.environ.get("PATH", "")
