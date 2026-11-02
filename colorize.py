"""Give every part in a GLB its own pastel material so the parts read apart."""

from __future__ import annotations

import argparse
import colorsys
import json
import struct
from pathlib import Path

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
PHI = 0.6180339887498949


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def part_color(i: int) -> list[float]:
    hue = (i * PHI) % 1.0
    sat = 0.32 + 0.20 * ((i * 7) % 3) / 2.0
    val = 0.86 + 0.12 * ((i * 5) % 2)
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return [srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), 1.0]


def read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    magic, _, total = struct.unpack_from("<III", raw, 0)
    if magic != GLB_MAGIC:
        raise ValueError("not a GLB")
    doc, bin_chunk = None, b""
    offset = 12
    while offset < total:
        length, ctype = struct.unpack_from("<II", raw, offset)
        data = raw[offset + 8 : offset + 8 + length]
        if ctype == CHUNK_JSON:
            doc = json.loads(data.decode("utf-8"))
        elif ctype == CHUNK_BIN:
            bin_chunk = data
        offset += 8 + length
    assert doc is not None
    return doc, bin_chunk


def write_glb(path: Path, doc: dict, bin_chunk: bytes) -> None:
    json_bytes = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * (-len(json_bytes) % 4)
    bin_chunk += b"\x00" * (-len(bin_chunk) % 4)
    out = struct.pack("<III", GLB_MAGIC, 2, 12 + 8 + len(json_bytes) + 8 + len(bin_chunk))
    out += struct.pack("<II", len(json_bytes), CHUNK_JSON) + json_bytes
    out += struct.pack("<II", len(bin_chunk), CHUNK_BIN) + bin_chunk
    path.write_bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--saturation", type=float, default=1.0, help="scale the palette saturation")
    args = ap.parse_args()

    doc, bin_chunk = read_glb(Path(args.src))
    materials = doc.setdefault("materials", [])

    base = None
    for mat in materials:
        pbr = mat.get("pbrMetallicRoughness", {})
        if "baseColorFactor" in pbr:
            base = dict(pbr)
            base.pop("baseColorFactor")
            break
    if base is None:
        base = {"metallicFactor": 0.2, "roughnessFactor": 0.55}

    template = {
        "name": "__template__",
        "doubleSided": True,
        "pbrMetallicRoughness": base,
    }
    materials.clear()
    materials.append(template)

    colored = 0
    for mesh_index, mesh in enumerate(doc.get("meshes", [])):
        color = part_color(mesh_index)
        if args.saturation != 1.0:
            grey = sum(color[:3]) / 3.0
            color = [
                grey + (c - grey) * args.saturation for c in color[:3]
            ] + [1.0]
        mat = json.loads(json.dumps(template))
        mat.pop("name")
        mat["name"] = f"part_{mesh_index}"
        mat["pbrMetallicRoughness"]["baseColorFactor"] = color
        materials.append(mat)
        new_index = len(materials) - 1
        for prim in mesh.get("primitives", []):
            prim["material"] = new_index
        colored += 1

    out = Path(args.dst)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_glb(out, doc, bin_chunk)
    print(f"parts coloured: {colored}")
    print(f"materials     : {len(materials)}")
    print(f"output        : {out}  {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
