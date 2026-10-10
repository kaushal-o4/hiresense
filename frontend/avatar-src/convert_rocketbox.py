"""Convert a Microsoft Rocketbox avatar (MIT licence) from FBX to a web-ready GLB for the live interviewer.

Run with Blender (one-time build step, output is committed to frontend/public/avatars/):
  blender -b --factory-startup --python convert_rocketbox.py -- <avatar_folder> <output.glb>

<avatar_folder> is a folder from https://github.com/microsoft/Microsoft-Rocketbox/tree/master/Assets/Avatars
containing Export/<name>_facial.fbx and Textures/*.tga.

What it does:
  * imports the "_facial" FBX (rigged body + 176 facial blendshapes),
  * keeps only the blendshapes the app animates (15 visemes + ~25 ARKit expressions) to keep the file small,
  * relinks the textures, downsizes them and stores them as JPEG/PNG (browsers can't read TGA),
  * exports GLB with skin + morph targets (no animations).
"""
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
name = os.path.basename(SRC.rstrip("\\/"))
TEX = os.path.join(SRC, "Textures")
import tempfile  # noqa: E402

TMP = tempfile.mkdtemp(prefix="rocketbox_tex_")  # converted textures are embedded in the GLB; never in public/

KEEP_PREFIX = ("AA_VI_",)  # all 15 visemes
KEEP_ARKIT = {
    "EyeBlinkLeft", "EyeBlinkRight", "EyeLookUpLeft", "EyeLookUpRight", "EyeLookDownLeft", "EyeLookDownRight",
    "EyeLookInLeft", "EyeLookInRight", "EyeLookOutLeft", "EyeLookOutRight", "EyeSquintLeft", "EyeSquintRight",
    "EyeWideLeft", "EyeWideRight", "BrowInnerUp", "BrowOuterUpLeft", "BrowOuterUpRight", "BrowDownLeft",
    "BrowDownRight", "MouthSmileLeft", "MouthSmileRight", "CheekSquintLeft", "CheekSquintRight", "JawOpen",
    "MouthClose", "MouthPressLeft", "MouthPressRight", "MouthDimpleLeft", "MouthDimpleRight",
}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(SRC, "Export", f"{name}_facial.fbx"))

# ---- textures: relink, downsize, convert
for img in list(bpy.data.images):
    fname = os.path.basename(img.filepath.replace("\\", "/"))
    local = os.path.join(TEX, fname)
    if not os.path.exists(local):
        print("missing texture", fname)
        continue
    img.filepath = local
    img.reload()
    is_head = "_head_" in fname
    is_alpha = "opacity" in fname
    size = 2048 if (is_head and "color" in fname) else 1024
    if img.size[0] > size:
        img.scale(size, size)
    ext = "png" if is_alpha else "jpg"
    out = os.path.join(TMP, os.path.splitext(fname)[0] + "." + ext)
    img.filepath_raw = out
    img.file_format = "PNG" if is_alpha else "JPEG"
    img.save()
    img.filepath = out
    img.name = os.path.splitext(fname)[0]

# drop specular maps (not used by the web renderer) to save space
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    nt = mat.node_tree
    for node in list(nt.nodes):
        if node.type == "TEX_IMAGE" and node.image and "specular" in node.image.name:
            nt.nodes.remove(node)
    # hair / eyelashes: colour + alpha come from the opacity texture
    if "opacity" in mat.name:
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
        if tex:
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        try:
            mat.surface_render_method = "DITHERED"
        except AttributeError:
            mat.blend_method = "CLIP"

# ---- shape keys: keep only what the app uses
for obj in bpy.data.objects:
    if obj.type != "MESH" or not obj.data.shape_keys:
        continue
    keys = obj.data.shape_keys.key_blocks
    for kb in list(keys)[1:]:
        arkit = kb.name[6:] if kb.name.startswith("AK_") else None
        if not (kb.name.startswith(KEEP_PREFIX) or (arkit and arkit in KEEP_ARKIT)):
            obj.shape_key_remove(kb)
    print("kept shape keys:", [k.name for k in obj.data.shape_keys.key_blocks][1:])

bpy.ops.export_scene.gltf(
    filepath=OUT, export_format="GLB", export_skins=True, export_morph=True, export_morph_normal=False,
    export_animations=False, export_image_format="AUTO", export_yup=True, export_apply=False,
)
print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")
