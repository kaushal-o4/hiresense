# Photoreal interviewers with MetaHuman

The app already supports high-detail interviewers. Each persona in `backend/app/services/interviewers.py` has a
`hd_model` (`/avatars/hd/<id>.glb`). When that file exists, the interview loads it. When it doesn't, the app falls
back to the bundled Rocketbox model. So you can add characters one at a time and nothing breaks in between.

The pipeline: **MetaHuman Creator (Unreal Engine)** → **DCC Export** → **Blender + Character DNA add-on** →
`convert_metahuman.py` → `frontend/public/avatars/hd/<id>.glb`.

## Licence (checked October 2026)

MetaHumans fall under the standard Unreal Engine EULA:
- **Free** for individuals and companies earning under $1M a year.
- **Allowed in other software**, including this web app.
- **AI restriction:** you may use them alongside AI, but not to *train* AI models.

See <https://www.metahuman.com/license>.

## Hardware

MetaHuman Creator runs inside Unreal Engine 5.6 or later.
- **This laptop** (RTX 3050, 4 GB video memory) is below Epic's recommended spec. Expect it to be slow.
- **Before you start:** close Ollama and the HireSense backend to free up the GPU.
- **Disk space:** about 100 GB for the engine plus a project.
- **Rigging:** the auto-rigging step runs on Epic's servers, so you need an Epic account and an internet connection.

The finished GLB runs in the browser like the current avatars. Unreal is only needed to *create* the characters.

## Character recipes (original characters, not copies)

Build original faces. Don't recreate a real person (actor, celebrity, colleague) or another studio's character.
These recipes match the *style* you asked for.

**Aria (friendly):**
- Woman in her late 20s, East Asian features, soft oval face, gentle brows.
- Dark brown-black hair loosely tied back, with soft, wispy see-through bangs and a few loose strands at the temples.
- Natural, minimal makeup with a soft rose lip.
- Wardrobe: dusty-pink blazer over an open-collar top. If you add your own accessory mesh, a thin gold pendant necklace.
- Resting expression: a slight warm half-smile.

**Victor (strict technical):**
- Man in his mid-40s, strong straight brows, defined cheekbones and jaw, light stubble shadow.
- Short dark-brown hair, swept back and neatly groomed.
- Wardrobe: charcoal suit, white shirt, dark patterned tie.
- Resting expression: steady, focused, the faintest knowing half-smile.

**Marcus (stress)** and **Elena (HR):** give each a distinct face and hairstyle. The interview code already gives
them their own lighting, voice and behaviour.

## Step by step

1. **Install the tools**
   - Epic Games Launcher → install **Unreal Engine 5.6 or 5.7**.
   - **Blender 4.5+**.
   - Poly Hammer's **Character DNA** add-on (free edition, <https://www.polyhammer.com/character-dna-addon>). Install it in Blender under *Edit → Preferences → Add-ons*.
2. **Create the character**
   - In Unreal, create a blank project and enable the **MetaHuman** plugins (*Edit → Plugins*, search "MetaHuman").
   - In the Content Browser: *right-click → MetaHuman → MetaHuman Character*, then open it.
   - Blend the head presets, sculpt toward the recipe, then set skin, eyes, makeup, hair and wardrobe.
   - **Hair:** pick a style that includes a *cards* version. Browsers can't render strand grooms.
   - Press **Assemble** (the auto-rig).
3. **Export:** open the MetaHuman Creator **Export** category → **DCC Export**. Turn on **Bake Makeup** and export to a folder such as `D:\mh\aria_dcc`. Epic documents this step here: <https://dev.epicgames.com/documentation/metahuman/metahuman-creator-export-tool-in-unreal-engine>.
4. **Import into Blender**
   - Start from an empty scene → *File → Import → MetaHuman DNA (.dna)*, and pick `head.dna` from the export folder.
   - The add-on links the textures from the `Maps` folder next to it.
   - Move a few face-board controls by hand to check the face responds.
   - Save the file as `mh_aria.blend`.
5. **Check the control names** (once, with the first character):
   ```
   blender -b mh_aria.blend --python convert_metahuman.py -- --list > list.txt
   ```
   - The last section lists entries in `metahuman_bake_map.json` whose controls weren't found.
   - Fix those names in the map using the control list printed above it. Or send `list.txt` to Claude and it can update the map.
   - Optional: if the add-on's **Visemes** pose library appears under *actions*, add entries such as `"viseme_AA": {"pose": "<action name>"}`. You then get real MetaHuman mouth shapes for lip-sync.
6. **Bake and export:**
   ```
   blender -b mh_aria.blend --python convert_metahuman.py -- ../public/avatars/hd/aria.glb
   ```
   - Options: `--lod 1` (default; LOD0 is usually too heavy for a laptop browser, use `--lod 2` if it stutters) and `--tex 2048`.
   - Aim for a GLB under 40 MB.
7. **Check it in the app:** open a voice interview with Aria. In the browser console, `window.__avatar3d` should show `model: "/avatars/hd/aria.glb"`, `rig: "arkit"` and `arkit: 52`. Also run the browser checks in `backend/tests_e2e/` (`avatar_snapshot.py`, `interviewers_browser.py`).

## What to expect

**Better than Rocketbox:**
- face shape and skin texture
- teeth, tongue and the inside of the mouth
- eye detail and eyelashes

**Still below the Unreal cinematic look:**
- **Hair:** the browser uses hair cards instead of real strands.
- **Skin:** light scattering through the skin is approximated in the browser, not simulated.
- **Lighting:** no film-grade bounced light.

Getting fully to film quality would need Unreal **Pixel Streaming** on a desktop GPU with about 8 GB or more of
video memory, separate from the machine running the AI models.
