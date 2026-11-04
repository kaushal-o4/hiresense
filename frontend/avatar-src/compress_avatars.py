"""Shrink the interviewer GLBs for the web: WebP textures (Pillow) + meshopt geometry compression (gltf-transform).

    python frontend/avatar-src/compress_avatars.py IN.glb OUT.glb [IN2.glb OUT2.glb ...]

Run it on the ORIGINAL Blender exports, not on already-compressed files. The originals are in git history:
    git show 33b7614:frontend/public/avatars/victor.glb > victor_original.glb

Steps per model:
  1. gltf-transform `copy` unpacks the GLB into model.gltf + separate image files
  2. Pillow re-encodes every image as WebP (colour q88, normal maps q95, alpha kept) and the glTF gets
     EXT_texture_webp. (gltf-transform's own `webp` command fails on this Windows machine:
     "colourspace: parameter space not set", a sharp/libvips bug.)
  3. gltf-transform `meshopt` quantizes + compresses vertices, skin weights and the 44 blendshapes, and repacks a GLB.
Three.js needs `loader.setMeshoptDecoder(MeshoptDecoder)` for the result (see src/voice/Avatar3D.jsx). Bones, the skin
and the morph-target names are unchanged. Needs Node (npx) and Pillow with WebP support.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

CLI = "@gltf-transform/cli@4.1.1"


def npx(*args):
    subprocess.run(["npx", "-y", CLI, *args], check=True, shell=sys.platform == "win32")


def compress(src: Path, dst: Path) -> None:
    work = Path(tempfile.mkdtemp(prefix="avatar_"))
    try:
        gltf = work / "model.gltf"
        npx("copy", str(src), str(gltf))
        doc = json.loads(gltf.read_text(encoding="utf-8"))
        normal_images = {doc["textures"][m["normalTexture"]["index"]]["source"]
                         for m in doc.get("materials", []) if "normalTexture" in m}
        for i, img in enumerate(doc.get("images", [])):
            path = work / img["uri"]
            out = path.with_suffix(".webp")
            with Image.open(path) as im:
                has_alpha = "A" in im.getbands() or "transparency" in im.info
                im = im.convert("RGBA" if has_alpha else "RGB")
                if i in normal_images:
                    im.save(out, "WEBP", quality=95, method=6)
                else:
                    im.save(out, "WEBP", quality=88, method=6, alpha_quality=100)
            img["uri"] = out.name
            img["mimeType"] = "image/webp"
        for t in doc.get("textures", []):
            t["extensions"] = {**t.get("extensions", {}), "EXT_texture_webp": {"source": t.pop("source")}}
        for key in ("extensionsUsed", "extensionsRequired"):
            doc[key] = sorted(set(doc.get(key, [])) | {"EXT_texture_webp"})
        gltf.write_text(json.dumps(doc), encoding="utf-8")
        dst.parent.mkdir(parents=True, exist_ok=True)
        npx("meshopt", str(gltf), str(dst), "--level", "medium")
        print(f"{src.name}: {src.stat().st_size / 1e6:.2f} MB -> {dst.stat().st_size / 1e6:.2f} MB")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or len(a) % 2:
        sys.exit(__doc__)
    for s, d in zip(a[::2], a[1::2]):
        compress(Path(s), Path(d))
