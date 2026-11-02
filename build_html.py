"""Bundle a GLB into a single, fully offline HTML viewer."""

from __future__ import annotations

import argparse
import base64
import json
import struct
from pathlib import Path

import trimesh

VIEWER_JS = Path(__file__).resolve().parent / "vendor" / "model-viewer.min.js"

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>__TITLE__ — 三维查看</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; overflow: hidden; background: #14171c;
    overscroll-behavior: none;
    font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif; }
  #mv { width: 100%; height: 100%; --poster-color: transparent; background:
    radial-gradient(120% 90% at 50% 0%, #2b323c 0%, #14171c 70%);
    touch-action: none; user-select: none; -webkit-user-select: none;
    -webkit-tap-highlight-color: transparent; cursor: grab; }
  #mv:active { cursor: grabbing; }
  #mv::part(default-progress-bar) { display: none; }
  #hud { position: fixed; top: 0; left: 0; padding: 14px 18px; pointer-events: none;
    color: #e8ecf1; text-shadow: 0 1px 3px rgba(0,0,0,.8); }
  #hud h1 { margin: 0; font-size: 15px; font-weight: 600; letter-spacing: .04em; }
  #hud p { margin: 4px 0 0; font-size: 12px; color: #9aa5b1; }
  #hud p.keys { font-size: 11.5px; color: #79838f; }
  #bar { position: fixed; bottom: 0; left: 0; right: 0; display: flex; gap: 8px;
    padding: 14px 18px; flex-wrap: wrap; pointer-events: none; }
  #bar button { flex: 0 0 auto; padding: 9px 15px; font-size: 13px; color: #dbe2ea;
    background: rgba(40,46,55,.82); border: 1px solid rgba(255,255,255,.12);
    border-radius: 8px; cursor: pointer; pointer-events: auto;
    -webkit-tap-highlight-color: transparent; }
  #bar button:hover { background: rgba(56,64,76,.92); }
  #bar button:active { transform: translateY(1px); }
  #bar button[aria-pressed="true"] { border-color: #4c9aff; color: #fff; }
  #splash { position: fixed; inset: 0; display: flex; align-items: center;
    justify-content: center; flex-direction: column; gap: 10px; color: #9aa5b1;
    font-size: 13px; transition: opacity .4s; background: #14171c; z-index: 5; }
  #splash.gone { opacity: 0; pointer-events: none; }
  #splash b { color: #dbe2ea; font-weight: 600; }
  #err { position: fixed; left: 18px; right: 18px; bottom: 76px; padding: 12px 14px;
    border-radius: 8px; background: rgba(120,30,30,.9); color: #ffe3e3;
    font-size: 12px; white-space: pre-wrap; display: none; z-index: 6; }
</style>
</head>
<body>
<model-viewer id="mv" camera-controls touch-action="none" interaction-prompt="none"
  shadow-intensity="__SHADOW__" shadow-softness="1" exposure="1.15" environment-image="neutral"
  tone-mapping="neutral" rotation-per-second="18deg" min-field-of-view="3deg"
  max-field-of-view="55deg" loading="eager" reveal="auto"
  min-camera-orbit="auto 0deg auto" max-camera-orbit="auto 180deg auto"
  camera-orbit="35deg 65deg 105%" field-of-view="30deg"></model-viewer>

<div id="hud">
  <h1>__TITLE__</h1>
  <p>外形尺寸 __DIMS__ mm · 三角面 __TRIS__</p>
  <p class="keys">鼠标：左键拖动旋转 · 右键或 Shift+左键拖动平移 · 滚轮缩放</p>
  <p class="keys">触摸屏：单指拖动旋转 · 双指拖动平移 · 双指捏合缩放</p>
</div>

<div id="bar">
  <button id="btn-reset" type="button">复位</button>
  <button id="btn-color" type="button" aria-pressed="true">切换灰模</button>
  <button id="btn-spin" type="button" aria-pressed="false">自动旋转</button>
  <button id="btn-full" type="button">全屏</button>
</div>

<div id="splash"><b>正在加载模型…</b><span id="splash-note">单文件离线查看，无需安装任何软件</span></div>
<div id="err"></div>

<script type="application/octet-stream" id="model-data">__MODEL_B64__</script>

<script type="module">__VIEWER_JS__</script>

<script>
(function () {
  var mv = document.getElementById('mv');
  var splash = document.getElementById('splash');
  var errBox = document.getElementById('err');

  function fail(msg) {
    errBox.style.display = 'block';
    errBox.textContent = '模型加载失败：' + msg;
    splash.classList.add('gone');
  }

  var MONO = [0.72, 0.75, 0.78, 1];
  var colorBtn = document.getElementById('btn-color');
  var palette = null;
  var colorOn = true;

  function capturePalette() {
    try {
      palette = mv.model.materials.map(function (m) {
        var c = m.pbrMetallicRoughness.baseColorFactor;
        return [c[0], c[1], c[2], c[3]];
      });
    } catch (e) {
      palette = null;
    }
  }

  function setColor(on) {
    colorOn = on;
    colorBtn.textContent = on ? '切换灰模' : '切换彩色';
    colorBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (!palette || !mv.model) return;
    var mats = mv.model.materials;
    for (var i = 0; i < mats.length; i++) {
      var c = on && palette[i] ? palette[i] : MONO;
      mats[i].pbrMetallicRoughness.setBaseColorFactor(c);
    }
  }

  colorBtn.addEventListener('click', function () {
    setColor(!colorOn);
  });

  mv.addEventListener('load', function () {
    splash.classList.add('gone');
    capturePalette();
    setColor(true);
  });
  mv.addEventListener('error', function (e) {
    var d = e.detail && (e.detail.type || e.detail.sourceError);
    fail(String(d || '未知错误'));
  });
  setTimeout(function () { splash.classList.add('gone'); }, 20000);

  function boot() {
    try {
      var b64 = document.getElementById('model-data').textContent.trim();
      var bin = atob(b64);
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      mv.src = URL.createObjectURL(new Blob([bytes], { type: 'model/gltf-binary' }));
    } catch (e) {
      fail(String(e && e.message ? e.message : e));
    }
  }

  var ready = (window.customElements && !customElements.get('model-viewer'))
    ? customElements.whenDefined('model-viewer')
    : Promise.resolve();
  ready.then(__SETUP__).then(boot, function (e) {
    fail(String(e && e.message ? e.message : e));
  });

  document.getElementById('btn-reset').addEventListener('click', function () {
    mv.cameraOrbit = '35deg 65deg 105%';
    mv.fieldOfView = '30deg';
    mv.jumpCameraToGoal();
  });

  var spin = document.getElementById('btn-spin');
  spin.addEventListener('click', function () {
    var on = spin.getAttribute('aria-pressed') !== 'true';
    spin.setAttribute('aria-pressed', on ? 'true' : 'false');
    mv.autoRotate = on;
  });

  var full = document.getElementById('btn-full');
  full.addEventListener('click', function () {
    if (document.fullscreenElement) { document.exitFullscreen(); return; }
    var r = document.documentElement.requestFullscreen
      ? document.documentElement.requestFullscreen() : null;
    if (r && r.catch) r.catch(function () {});
  });

})();
</script>
</body>
</html>
"""


def patch_materials(
    glb: bytes,
    *,
    double_sided: bool,
    drop_textures: bool,
    rotate: tuple[float, float, float, float] | None = None,
) -> bytes:
    magic, version, total = struct.unpack_from("<III", glb, 0)
    if magic != GLB_MAGIC:
        raise ValueError("not a GLB file")

    chunks: list[tuple[int, bytes]] = []
    offset = 12
    while offset < total:
        clen, ctype = struct.unpack_from("<II", glb, offset)
        chunks.append((ctype, glb[offset + 8 : offset + 8 + clen]))
        offset += 8 + clen

    doc = None
    bin_chunk = b""
    for ctype, data in chunks:
        if ctype == CHUNK_JSON:
            doc = json.loads(data.decode("utf-8"))
        elif ctype == CHUNK_BIN:
            bin_chunk = data
    if doc is None:
        raise ValueError("GLB has no JSON chunk")

    for mat in doc.get("materials", []):
        if double_sided:
            mat["doubleSided"] = True
        if drop_textures:
            mat.pop("normalTexture", None)
        pbr = mat.setdefault("pbrMetallicRoughness", {})
        pbr.setdefault("metallicFactor", 0.15)
        pbr.setdefault("roughnessFactor", 0.55)
        base = pbr.get("baseColorFactor")
        if not base or base[:3] == [1, 1, 1]:
            pbr["baseColorFactor"] = [0.72, 0.75, 0.78, 1.0]
        mat.setdefault("extensions", {}).pop("KHR_materials_unlit", None)

    if rotate is not None:
        # wrap every scene root in a single node that carries the rotation, so the
        # transform applies uniformly to the whole assembly
        roots = []
        for scene_def in doc.get("scenes", []):
            roots.extend(scene_def.get("nodes", []))
            scene_def["nodes"] = [len(doc["nodes"])]
        doc["nodes"].append(
            {
                "name": "__root__",
                "rotation": list(rotate),
                "children": sorted(set(roots)),
            }
        )

    json_bytes = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * (-len(json_bytes) % 4)
    bin_chunk += b"\x00" * (-len(bin_chunk) % 4)

    out = struct.pack("<III", GLB_MAGIC, 2, 12 + 8 + len(json_bytes) + 8 + len(bin_chunk))
    out += struct.pack("<II", len(json_bytes), CHUNK_JSON) + json_bytes
    out += struct.pack("<II", len(bin_chunk), CHUNK_BIN) + bin_chunk
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("out")
    ap.add_argument("--title", default="模型")
    ap.add_argument("--no-double-sided", action="store_true")
    ap.add_argument("--drop-textures", action="store_true")
    ap.add_argument("--tris", default=None, help="override triangle count shown in HUD")
    ap.add_argument("--dims", default=None, help="override dims in mm shown in HUD")
    ap.add_argument(
        "--meshopt",
        action="store_true",
        help="enable the bundled meshopt decoder for EXT_meshopt_compression payloads",
    )
    ap.add_argument(
        "--flip-axis",
        choices=["none", "x", "z"],
        default="none",
        help="rotate the whole assembly 180 degrees about this horizontal axis",
    )
    ap.add_argument("--no-shadow", action="store_true", help="disable the ground shadow pass")
    args = ap.parse_args()

    src = Path(args.glb)
    rotate = {"none": None, "x": (1.0, 0.0, 0.0, 0.0), "z": (0.0, 0.0, 1.0, 0.0)}[
        args.flip_axis
    ]
    data = patch_materials(
        src.read_bytes(),
        double_sided=not args.no_double_sided,
        drop_textures=args.drop_textures,
        rotate=rotate,
    )

    try:
        scene = trimesh.load(src, force="scene")
        geoms = list(scene.geometry.values()) or [scene]
        tris = sum(len(g.faces) for g in geoms)
        size = scene.bounds[1] - scene.bounds[0]
        dims = " × ".join(f"{v * 1000:.0f}" for v in size)
    except Exception as exc:  # compressed payloads may be unreadable here
        print(f"stats: unavailable ({exc})")
        tris = 0
        dims = args.dims or "—"
    if args.tris:
        tris = int(args.tris.replace(",", ""))
    if args.dims:
        dims = args.dims

    viewer_js = VIEWER_JS.read_text(encoding="utf-8")
    viewer_js = viewer_js.replace("</script", "<\\/script")
    viewer_js = viewer_js.split("//# sourceMappingURL=")[0]

    b64 = base64.b64encode(data).decode("ascii")
    setup = (
        "function(){customElements.get('model-viewer').meshoptDecoderLocation="
        "URL.createObjectURL(new Blob(['/* decoder ships inside the bundle */'],"
        "{type:'text/javascript'}));}"
        if args.meshopt
        else "function(){}"
    )
    html = (
        PAGE.replace("__VIEWER_JS__", viewer_js)
        .replace("__MODEL_B64__", b64)
        .replace("__SETUP__", setup)
        .replace("__SHADOW__", "0" if args.no_shadow else "1.1")
        .replace("__TITLE__", args.title)
        .replace("__TRIS__", f"{tris:,}")
        .replace("__DIMS__", dims)
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"glb   : {len(data) / 1e6:.2f} MB")
    print(f"html  : {out}  {out.stat().st_size / 1e6:.2f} MB")
    print(f"tris  : {tris:,}")
    print(f"dims  : {dims} mm")


if __name__ == "__main__":
    main()
