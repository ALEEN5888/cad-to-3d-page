"""双击 转换.cmd 时弹出的文件选择框。

把选中的文件逐个打印到标准输出，由 .cmd 读取后交给 make_viewer.py。

  python pick_files.py            弹出选择框
  python pick_files.py --check    只自检窗口组件是否可用，不弹框
"""

from __future__ import annotations

import sys

PATTERNS = (
    "*.step *.stp *.iges *.igs *.stl *.obj *.ply *.3mf *.glb *.gltf"
)


def self_check() -> int:
    """没有图形界面时也要干净地失败，而不是抛出漫长堆栈。"""
    import tkinter

    root = tkinter.Tk()
    root.destroy()
    return 0


def pick() -> int:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    files = filedialog.askopenfilenames(
        title="选择要转换的 CAD 模型（可多选）",
        filetypes=[("CAD 模型", PATTERNS), ("所有文件", "*.*")],
    )
    root.destroy()

    for path in files:
        print(path, flush=True)
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(pick())
