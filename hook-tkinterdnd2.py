import os
import platform

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


system = platform.system()
platform_files = {
    "Windows": (
        {"win-arm64", "win-x86", "win-x86-tcl9", "win-x64", "win-x64-tcl9"},
        {"tkdnd_unix.tcl", "tkdnd_macosx.tcl"},
    ),
    "Linux": (
        {"linux-x64", "linux-x64-tcl9", "linux-arm64", "linux-arm64-tcl9"},
        {"tkdnd_windows.tcl", "tkdnd_macosx.tcl"},
    ),
    "Darwin": (
        {"osx-x64", "osx-arm64"},
        {"tkdnd_windows.tcl", "tkdnd_unix.tcl"},
    ),
}

if system not in platform_files:
    raise RuntimeError(f"TkinterDnD2 is not supported on platform {system!r}.")

allowed_binaries, excluded_scripts = platform_files[system]
datas = {
    item
    for item in (
        *collect_data_files("tkinterdnd2"),
        *collect_dynamic_libs("tkinterdnd2"),
    )
    if os.path.split(item[1])[1] in allowed_binaries
    and os.path.split(item[0])[1] not in excluded_scripts
}
