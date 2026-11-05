"""把 CAD 文件转成一个可以发给别人的单文件三维网页。

用法：  python make_viewer.py 模型.STEP
        python make_viewer.py 模型.STEP --flip-axis x --target-mb 20

流程：  CAD → GLB 网格化 → 每个零件单独上色 → 顶点量化压缩 → 内嵌进单文件 HTML
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEP_EXT = {".step", ".stp"}
IGES_EXT = {".iges", ".igs"}
BREP_EXT = STEP_EXT | IGES_EXT
MESH_EXT = {".stl", ".obj", ".ply", ".3mf", ".glb", ".gltf"}


LOG_PATH = HERE / "转换日志.txt"


def ensure_ascii_temp() -> None:
    """cascadio/OpenCASCADE 在临时目录含中文时会失败：
    "File C:\\Users\\张三\\AppData\\Local\\Temp\\cascadio_xxx.bin.tmp can not be created"。
    这里把 TEMP 换到一个纯英文路径，其他逻辑都不受影响。"""
    def usable(p: str) -> bool:
        return bool(p) and p.isascii() and Path(p).is_dir()

    if usable(os.environ.get("TEMP", "")) or usable(os.environ.get("TMP", "")):
        return

    for base in (os.environ.get("PUBLIC") or r"C:\Users\Public", r"C:\Windows\Temp"):
        target = Path(base) / "cad2web-tmp"
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / f".probe_{os.getpid()}"
            probe.write_bytes(b"")
            probe.unlink()
        except OSError:
            continue
        os.environ["TEMP"] = os.environ["TMP"] = str(target)
        tempfile.tempdir = str(target)
        log(f"      TEMP 路径含中文，临时文件改用 {target}")
        return


def log(msg: str) -> None:
    """同时打到控制台和 转换日志.txt —— 窗口关了也还能回看。"""
    print(msg, flush=True)
    try:
        if LOG_PATH.stat().st_size > 512_000:
            LOG_PATH.unlink()
    except OSError:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


# 角度公差的上限（弧度）。再放粗圆柱面就只剩七八段，圆管会明显发棱，
# 宁可文件大一点也不要变成多边形。
ANG_MAX = 0.3


def check_deps(need_cascadio: bool) -> None:
    """这台机器上可能有多个 Python，只有部分装了依赖——先说清楚用的是哪个。"""
    import importlib.util

    log(f"解释器：{sys.executable}  (Python {sys.version.split()[0]})")

    wanted = ["trimesh"] + (["cascadio"] if need_cascadio else [])
    missing = [m for m in wanted if importlib.util.find_spec(m) is None]
    if missing:
        raise SystemExit(
            f"[错误] 这个 Python 缺少依赖：{'、'.join(missing)}\n"
            f"      解释器：{sys.executable}\n"
            "      最快的解决办法：双击文件夹里的 install-deps.cmd。\n"
            "      或者手工执行：\n"
            f'      "{sys.executable}" -m pip install cascadio trimesh'
        )


def find_gltfpack() -> str | None:
    exe = shutil.which("gltfpack")
    if exe:
        return exe
    for cand in (
        Path.home() / "AppData/Roaming/npm/gltfpack.cmd",
        Path.home() / "AppData/Roaming/npm/gltfpack",
        Path("C:/Program Files/nodejs/gltfpack.cmd"),
    ):
        if cand.exists():
            return str(cand)
    return None


class ConvertFailed(RuntimeError):
    """网格化没能产出结果。"""


def check_file_integrity(src: Path) -> None:
    """STEP/IGES 文件被截断是"网格化失败"最常见的原因，先在本地查出来。"""
    size = src.stat().st_size
    if size < 1024:
        raise SystemExit(f"[错误] {src.name} 只有 {size} 字节，明显不是完整的模型文件。")

    if src.suffix.lower() not in STEP_EXT:
        return

    with src.open("rb") as fh:
        head = fh.read(4096)
        fh.seek(max(0, size - 4096))
        tail = fh.read()

    if b"ISO-10303-21" not in head:
        raise SystemExit(
            f"[错误] {src.name} 不是有效的 STEP 文件（开头缺少 ISO-10303-21 标识）。\n"
            "      它可能其实是别的格式，或者文件已经损坏。"
        )
    if b"END-ISO-10303-21" not in tail:
        raise SystemExit(
            f"[错误] {src.name} 看起来没有写完（{size / 1e6:.1f} MB，末尾缺少 END-ISO-10303-21）。\n"
            "      最常见的原因：从 SolidWorks 导出后立刻拖过来，文件还在写。\n"
            "      请等导出完成，或重新导出一次再试。"
        )

    # 只有曲线/点的 STEP 也能"转换成功"，但网页里只会显示成几根细线，
    # 看起来就像"线条没画出来"。先在文件里数一下实体面。
    text = src.read_text(encoding="utf-8", errors="ignore")
    faces = len(re.findall(r"\b(?:ADVANCED_FACE|FACE_SURFACE)\s*\(", text))
    surfaces = len(re.findall(r"\b(?:SHELL_BASED_SURFACE_MODEL|OPEN_SHELL)\s*\(", text))
    curves = len(re.findall(r"\bGEOMETRIC_CURVE_SET\s*\(", text))
    if faces == 0:
        detail = "只有曲面" if surfaces else ("只有曲线/点" if curves else "没有任何面")
        raise SystemExit(
            f"[错误] {src.name} 里没有实体面（ADVANCED_FACE = 0），{detail}。\n"
            "      这种文件转出来只会是几根细线，看起来像'线条太细'。\n"
            "      在 SolidWorks 里重新导出：文件 → 另存为 → STEP → 选项里\n"
            "      把'输出'设为 实体/曲面几何体（不要选'曲线'），再勾上'导出面/边线'。"
        )
    log(f"      STEP 实体面：{faces} 个")


def convert_brep(src: Path, dst: Path, tol: float, ang: float) -> None:
    import cascadio

    t0 = time.time()
    data = cascadio.to_glb_bytes(
        src.read_bytes(),
        tol_linear=tol,
        tol_angular=ang,
        tol_relative=True,
        merge_primitives=True,
        use_parallel=True,
    )
    if not data:
        raise ConvertFailed("OpenCASCADE 返回空结果")
    dst.write_bytes(data)
    log(f"    网格化完成：{len(data) / 1e6:.2f} MB，用 {time.time() - t0:.1f} 秒")


def convert_mesh(src: Path, dst: Path) -> None:
    import trimesh

    t0 = time.time()
    loaded = trimesh.load(str(src), force="scene")
    if not isinstance(loaded, trimesh.Scene):
        scene = trimesh.Scene(loaded)
    else:
        scene = loaded
    dst.write_bytes(scene.export(file_type="glb"))
    log(f"    载入完成：{dst.stat().st_size / 1e6:.2f} MB，用 {time.time() - t0:.1f} 秒")


def run_tool(script: str, *args: str) -> None:
    cmd = [sys.executable, str(HERE / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        log(proc.stdout or "")
        log(proc.stderr or "")
        raise SystemExit(f"[错误] {script} 执行失败")


def main() -> None:
    ap = argparse.ArgumentParser(description="CAD 文件 → 单文件三维网页")
    ap.add_argument("src", help="STEP / STP / IGES / STL / OBJ 文件")
    ap.add_argument("--out", default=None, help="输出的 HTML 路径，默认放在原文件旁边")
    ap.add_argument("--title", default=None, help="网页标题，默认用文件名")
    ap.add_argument(
        "--flip-axis",
        choices=["none", "x", "z"],
        default="none",
        help="把整个装配翻转 180 度（模型上下颠倒时用 x）",
    )
    ap.add_argument("--color", dest="color", action="store_true", default=True, help="每个零件单独上色（默认）")
    ap.add_argument("--mono", dest="color", action="store_false", help="不分色，用统一白模")
    ap.add_argument("--target-mb", type=float, default=12.0, help="压缩后模型体积上限，默认 12 MB")
    ap.add_argument("--max-attempts", type=int, default=8, help="放粗精度的最大重试次数")
    ap.add_argument("--tol-linear", type=float, default=0.0004, help="线性公差（相对包围盒），默认 0.0004")
    ap.add_argument("--tol-angular", type=float, default=0.15, help="角度公差（弧度），默认 0.15")
    ap.add_argument("--open", action="store_true", help="做完后自动用浏览器打开")
    args = ap.parse_args()

    log("")
    log(f"===== {time.strftime('%Y-%m-%d %H:%M:%S')}  {' '.join(sys.argv[1:])} =====")
    ensure_ascii_temp()

    # 目标特别小时才允许把圆管压成多边形，否则一律保住圆柱面。
    ang_max = 0.8 if args.target_mb < 8 else ANG_MAX

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"[错误] 找不到文件：{src}")

    ext = src.suffix.lower()
    if ext not in BREP_EXT | MESH_EXT:
        raise SystemExit(
            f"[错误] 不支持 {ext} 格式。支持："
            + "、".join(sorted(BREP_EXT | MESH_EXT))
        )

    check_deps(need_cascadio=ext in BREP_EXT)

    out = Path(args.out) if args.out else src.with_name(f"{src.stem}_三维查看.html")
    title = args.title or src.stem
    gltfpack = find_gltfpack()

    log("=" * 56)
    log(f"输入：{src}")
    log(f"体积：{src.stat().st_size / 1e6:.2f} MB")
    log(f"输出：{out}")
    log(f"压缩：{'gltfpack ' + gltfpack if gltfpack else '未找到 gltfpack，文件会偏大'}")
    log("=" * 56)

    if ext in BREP_EXT:
        check_file_integrity(src)

    tol, ang = args.tol_linear, args.tol_angular
    built: Path | None = None
    best: tuple[float, Path] | None = None
    prev: tuple[float, Path] | None = None

    with tempfile.TemporaryDirectory(prefix="cad2web_") as tmpdir:
        tmp = Path(tmpdir)
        raw, colored, packed = tmp / "raw.glb", tmp / "colored.glb", tmp / "packed.glb"

        for attempt in range(1, args.max_attempts + 1):
            log(f"[{attempt}] 精度：线性 {tol:g}（相对）· 角度 {ang:g} 弧度")
            log("    正在网格化…（大模型可能要几分钟，请先别关窗口）")
            try:
                if ext in BREP_EXT:
                    convert_brep(src, raw, tol, ang)
                else:
                    convert_mesh(src, raw)
            except ConvertFailed as exc:
                log(f"    网格化失败：{exc}")
                if attempt == args.max_attempts:
                    raise SystemExit(
                        "[错误] 试了多种精度都网格化不出来，通常是模型本身的问题：\n"
                        f"      文件：{src}\n"
                        "      可以试试：\n"
                        "      1) 在 SolidWorks 里重新导出 STEP（AP203 或 AP214 都行）；\n"
                        "      2) 如果是超大总装（几百个零件），先删掉不需要的内部零件；\n"
                        "      3) 关掉 CAD、浏览器等占内存的程序后再跑一次。"
                    )
                step = 3.0
                tol *= step
                ang = min(ang * 1.5, ang_max)
                log(f"    改用更粗的精度重试（线性 {tol:g}）…")
                continue
            except Exception as exc:  # 文件读取、内存等意外错误
                log(f"    转换过程中出错：{type(exc).__name__}: {exc}")
                if attempt == args.max_attempts:
                    raise SystemExit("[错误] 转换失败，请把上面这行错误信息发给我。")
                step = 3.0
                tol *= step
                ang = min(ang * 1.5, ang_max)
                log("    降低精度后重试…")
                continue

            source = raw
            if args.color:
                try:
                    run_tool("colorize.py", str(raw), str(colored))
                    source = colored
                except SystemExit as exc:
                    log(f"    [提示] 分色失败，改用纯色继续（照样能看图）：{exc}")

            if gltfpack:
                proc = subprocess.run(
                    [gltfpack, "-i", str(source), "-o", str(packed)],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode == 0 and packed.exists():
                    source = packed

            size_mb = source.stat().st_size / 1e6
            log(f"    当前体积：{size_mb:.2f} MB")
            if best is None or size_mb < best[0]:
                best = (size_mb, source)

            if size_mb <= args.target_mb or ext in MESH_EXT:
                built = source
                break

            if attempt == args.max_attempts:
                break

            # 再放粗只能省一点点（不到 5%）就停手：宁可文件大一点，
            # 也不要把细节换成体积。
            if prev is not None and size_mb > prev[0] * 0.95:
                log(f"    再放粗只能省 {100 * (1 - size_mb / prev[0]):.0f}%，"
                    "收益太小，保留上一版更精细的结果。")
                built = prev[1]
                break
            prev = (size_mb, source)

            # triangles scale roughly as 1 / tolerance, so step by the size ratio
            step = min(max(size_mb / args.target_mb, 1.4), 12.0)
            tol *= step
            ang = min(ang * min(step**0.5, 2.5), ang_max)
            log(f"    超过目标体积，精度放粗 {step:.1f} 倍后重试…")

        if built is None:
            if best is None:
                raise SystemExit("[错误] 转换失败")
            built = best[1]
            log("")
            log(f"注意：{args.max_attempts} 轮之后最小只能到 {best[0]:.2f} MB，"
                f"没达到 {args.target_mb:.2f} MB 的目标。")
            log("      这个模型本身很重（零件多或细节多）。如果嫌大可以：")
            log("      1) 加 --target-mb 15 放宽目标；2) 在 CAD 里删掉不需要的内部零件再导出。")

        # 先写到临时文件名，成功了再替换：中途失败不会毁掉上一次的成品。
        tmp_out = out.with_name(out.name + ".part")
        try:
            run_tool(
                "build_html.py",
                str(built),
                str(tmp_out),
                "--title",
                title,
                "--flip-axis",
                args.flip_axis,
            )
            tmp_out.replace(out)
        finally:
            if tmp_out.exists():
                try:
                    tmp_out.unlink()
                except OSError:
                    pass

    size = out.stat().st_size / 1e6
    log("=" * 56)
    log(f"完成：{out}")
    log(f"体积：{size:.2f} MB")
    log("这个 HTML 是单文件，发给别人双击即可查看，不需要装 CAD、不需要联网。")
    log("=" * 56)

    import os

    if args.open:
        if os.environ.get("CAD2WEB_NO_OPEN"):
            log("（已设置 CAD2WEB_NO_OPEN，跳过自动打开）")
        else:
            try:
                os.startfile(str(out))  # noqa: S606  (windows only)
            except Exception as exc:  # pragma: no cover
                log(f"（自动打开失败：{exc}）")


if __name__ == "__main__":
    main()
