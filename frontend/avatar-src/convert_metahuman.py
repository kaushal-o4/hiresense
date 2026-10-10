"""Convert a MetaHuman (imported into Blender with the free Poly Hammer "Character DNA" add-on) into a web GLB
for the live interviewer. Full walkthrough: METAHUMAN_GUIDE.md (same folder).

MetaHuman faces are driven by ~800 facial joints plus corrective shapes, evaluated by Epic's RigLogic. Browsers
can't run RigLogic, so this script BAKES the poses the app needs into plain blendshapes (morph targets):
  * the 52 ARKit expressions (blinks, gaze, brows, smiles, jaw, lips...), and
  * optional MetaHuman visemes ("viseme_AA" ...) when the map names a pose for them.
For every target it sets face-board controls (from metahuman_bake_map.json), lets RigLogic deform the mesh, and
stores the evaluated vertex positions as a shape key. The facial joints are then left at rest, so the web app
drives the face through blendshapes only, while the head/neck/spine bones still move the head.

Run with Blender 4.5+ on a .blend in which you imported the MetaHuman with Character DNA:
  1) list what the rig contains (control names, pose-library actions, meshes) - do this first:
       blender -b mh_aria.blend --python convert_metahuman.py -- --list
  2) bake and export:
       blender -b mh_aria.blend --python convert_metahuman.py -- ../public/avatars/hd/aria.glb
  options:  --map <json> (default: metahuman_bake_map.json)  --lod <n> (default 1)  --tex <px> (default 2048)

Status: written against Blender's standard Python API (depsgraph evaluation, shape keys, glTF exporter). The
add-on's own control names could not be verified without a real export, so --list reports every map entry whose
control is missing; fix those names in the map before trusting the bake (METAHUMAN_GUIDE.md, step 5).
"""
import json
import os
import re
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default):
    if name in args:
        i = args.index(name)
        val = args[i + 1]
        del args[i:i + 2]
        return val
    return default


HERE = os.path.dirname(os.path.abspath(__file__))
MAP = opt("--map", os.path.join(HERE, "metahuman_bake_map.json"))
LOD = int(opt("--lod", "1"))
TEX = int(opt("--tex", "2048"))
LIST = "--list" in args
if LIST:
    args.remove("--list")
OUT = os.path.abspath(args[0]) if args else None

scene = bpy.context.scene


def face_board():
    """The face-board armature (its pose bones are the GUI controls RigLogic reads)."""
    cands = [o for o in bpy.data.objects if o.type == "ARMATURE" and re.search(r"face.?board|gui", o.name, re.I)]
    if not cands:  # fall back to the armature with the most CTRL_ bones
        cands = sorted((o for o in bpy.data.objects if o.type == "ARMATURE"),
                       key=lambda o: -sum(b.name.startswith("CTRL_") for b in o.pose.bones))
    return cands[0] if cands else None


def lod_of(name):
    m = re.search(r"lod_?(\d)", name, re.I)
    return int(m.group(1)) if m else None


def face_meshes():
    """Meshes of the head that RigLogic deforms (head, teeth, eyes, lashes, eye shell, saliva...) at the chosen LOD."""
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        lod = lod_of(o.name)
        if lod is not None and lod != LOD:
            continue
        if re.search(r"head|teeth|tongue|saliva|eye|lash|brow|cartilage", o.name, re.I) and o.visible_get():
            out.append(o)
    return out


def reset(board):
    for pb in board.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def evaluate():
    """Let RigLogic (driven by frame/depsgraph updates) apply the current face-board pose."""
    scene.frame_set(scene.frame_current)
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def capture(meshes):
    dg = evaluate()
    shot = {}
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        shot[o.name] = [v.co.copy() for v in me.vertices]
        ev.to_mesh_clear()
    return shot


def apply_target(board, spec, actions):
    """spec: {"CTRL_L_eye_blink": [x, y], ...} or {"pose": "<action name>"}; values are face-board locations."""
    reset(board)
    if "pose" in spec:
        act = actions.get(spec["pose"])
        board.animation_data_create()
        board.animation_data.action = act
        scene.frame_set(int(act.frame_range[0]))
        return
    if board.animation_data:
        board.animation_data.action = None
    for ctrl, val in spec.items():
        pb = board.pose.bones[ctrl]
        x, y = (val + [0, 0])[:2] if isinstance(val, list) else (0, val)
        pb.location = (x, y, 0)


def main():
    board = face_board()
    meshes = face_meshes()
    actions = {a.name: a for a in bpy.data.actions}
    spec = json.load(open(MAP, encoding="utf-8"))
    targets = {k: v for k, v in spec.items() if not k.startswith("_")}
    controls = {pb.name for pb in board.pose.bones} if board else set()

    missing = {}
    for name, t in targets.items():
        if "pose" in t:
            if t["pose"] not in actions:
                missing[name] = [f"pose action '{t['pose']}'"]
        else:
            bad = [c for c in t if c not in controls]
            if bad:
                missing[name] = bad

    if LIST or not OUT:
        print("\n=== face board:", board.name if board else "NOT FOUND")
        print("controls (%d):" % len(controls))
        for c in sorted(controls):
            print("  ", c)
        print("\n=== actions / pose-library poses (%d):" % len(actions))
        for a in sorted(actions):
            print("  ", a)
        print("\n=== meshes used at LOD %d:" % LOD, [o.name for o in meshes])
        print("\n=== map entries with unknown controls (%d):" % len(missing))
        for k, v in missing.items():
            print("  ", k, "->", v)
        return
    if not board or not meshes:
        sys.exit("face board or head meshes not found - run with --list and check METAHUMAN_GUIDE.md")
    if missing:
        print("WARNING: skipping targets with unknown controls:", ", ".join(missing))

    # ---- bake: neutral first, then every target as (posed - neutral)
    reset(board)
    neutral = capture(meshes)
    baked = {}
    for name, t in targets.items():
        if name in missing:
            continue
        apply_target(board, t, actions)
        shot = capture(meshes)
        baked[name] = {o: [p - q for p, q in zip(shot[o], neutral[o])] for o in shot}
        print("baked", name)
    reset(board)
    if board.animation_data:
        board.animation_data.action = None

    # ---- freeze: stop RigLogic, replace the corrective shapes with the baked ones
    for o in meshes:
        o.data.shape_keys and o.shape_key_clear()
        basis = o.shape_key_add(name="Basis", from_mix=False)
        for name, deltas in baked.items():
            d = deltas[o.name]
            if max((v.length for v in d), default=0) < 1e-6:
                continue  # this pose doesn't move this mesh (e.g. blink on the teeth)
            kb = o.shape_key_add(name=name, from_mix=False)
            for i, v in enumerate(d):
                kb.data[i].co = basis.data[i].co + v
    for o in list(bpy.data.objects):  # drop other LODs, the face board and helper objects from the export
        lod = lod_of(o.name)
        if o == board or (o.type == "MESH" and lod is not None and lod != LOD):
            bpy.data.objects.remove(o, do_unlink=True)

    # ---- textures: downsize for the web
    for img in bpy.data.images:
        if img.size[0] > TEX:
            limit = TEX if re.search(r"head|face|skin", img.name, re.I) else TEX // 2
            img.scale(limit, limit)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT, export_format="GLB", export_skins=True, export_morph=True, export_morph_normal=True,
        export_animations=False, export_image_format="JPEG", export_jpeg_quality=88, export_yup=True, export_apply=False,
    )
    print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB;", len(baked), "blendshapes")


main()
