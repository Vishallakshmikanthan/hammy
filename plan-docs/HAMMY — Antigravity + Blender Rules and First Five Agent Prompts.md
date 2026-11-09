# HAMMY — Antigravity + Blender Rules and First Five Agent Prompts

*Free tools only: Blender, Cycles, the Blender MCP server, and free CC0 assets. Numbers are starting values; verify them against your own reference photos. Confirm Antigravity's current quota and your Blender version before you start.*

## 1. How to use this file

1. Create the project folder from Section 2.
2. Save Section 3 as `rules.md` in the project root.
3. Run the prompts in Section 4 **in order, one per session**. Review the result and render before moving on.
4. After each prompt, commit the scripts and the `.blend` file (or a dated copy of it).
5. If a prompt goes wrong, use the repair prompt in Section 5.

## 2. Project folder

```text
hammy-art/
  rules.md
  reference/
    photos/  video/  licence_log.csv  parameter_estimates.md
  blender/
    scripts/
      00_check_env.py
      10_cage.py
      20_clutter.py
      30_materials.py
      40_lighting_camera.py
      50_fur_setup.py
      common.py
    hamster.blend
    cage.blend
    scene.blend
  renders/
    tests/  compare/  final/
  docs/
    decisions.md
```

Two working modes:

- **Live mode (MCP):** the agent edits the open Blender scene and checks viewport screenshots.
- **Batch mode (scripts):** the agent writes a `bpy` script and runs Blender headless from the terminal. Prefer this for anything that must be reproducible.

Headless pattern:

```text
blender -b blender/scene.blend -P blender/scripts/10_cage.py
```

## 3. `rules.md` (paste into the project root)

```text
PROJECT: HAMMY art pipeline. Goal: a near-photoreal Syrian hamster and cage, rendered in Blender Cycles, for cinematic moments, plus assets exported to glTF for a real-time Three.js viewer later.

GENERAL RULES
1. Work in metric units. Scene unit scale 1.0, lengths in metres. A hamster body is about 0.13-0.18 m long.
2. Never delete or overwrite a .blend file I did not ask you to change. Save a dated copy first (scene_YYYYMMDD_HHMM.blend).
3. Every change must be done by a script in blender/scripts/ so the scene can be rebuilt. Scripts must be idempotent: running twice must not duplicate objects.
4. Use named collections: CAGE, BEDDING, PROPS, HAMSTER, LIGHTS, CAMERAS. Name every object with a clear prefix (cage_, bedding_, prop_, ham_).
5. Do not invent measurements. If a dimension is not in reference/parameter_estimates.md or in my message, ask me or use the default in this file and say you did.
6. After each task, render a test image to renders/tests/ and tell me exactly what to look at.
7. When you compare against reference, build a side-by-side image in renders/compare/ and list concrete differences (colour, proportions, scale, light direction, texture detail). Do not claim it looks realistic. Say what is still wrong.
8. Only use free assets with clear licences (Poly Haven, ambientCG, my own). Record each asset in reference/licence_log.csv with source URL and licence.
9. Do not use paid add-ons or paid web services.
10. Keep polygon counts reasonable: cage props under 20k triangles each, hamster body under 60k at the high level of detail.
11. Report honestly: say what you could not verify (for example, a Blender API that changed between versions).

REALISM RULES
- Nothing is perfectly straight, clean, or symmetric. Add small variation to placement, scale, and rotation.
- Every material needs roughness variation and fine surface detail, not a single flat value.
- Use real-world scale cues (bedding fibre size, seed size, bottle spout size).
- Lighting must have soft shadows, bounce light, and a believable colour temperature.
- Camera: shallow depth of field, slight vignette, subtle grain. Focal length 35-85 mm equivalent.

DEFAULT DIMENSIONS (verify against reference)
- Cage floor: 1.00 m x 0.50 m (0.5 m2), walls 0.40 m high, glass or clear plastic front and sides.
- Bedding depth: 0.15-0.20 m, uneven.
- Wheel: 0.28-0.30 m diameter, solid running surface, wall-mounted or free-standing.
- Bowl: ceramic, about 0.08 m diameter.
- Water bottle: about 0.15 m body with a metal spout, mounted on one wall.
- Hideout: about 0.15 x 0.12 x 0.10 m, wood or ceramic.
- Tunnel: about 0.06-0.08 m inner diameter.

RENDER SETTINGS (test)
- Cycles, GPU (OptiX if available), 128 samples, denoise on, 1920x1080, filmic or AgX view transform.
- Final: 512+ samples, 4K, as time allows.

WORKFLOW
Start each session by restating the task and listing assumptions. End each session with: what changed, how to re-run the script, what to review in the render, and what you did not verify.
```

## 4. The first five prompts

### Prompt 0 — Environment check (run first)

```text
Task: Verify the Blender and MCP setup. Do not change the scene.

Do:
1. Using the Blender MCP connection, report Blender version, Python version, the render engine, and whether a GPU compute device (OptiX or CUDA) is enabled for Cycles.
2. Create blender/scripts/common.py with helper functions: get_or_create_collection(name), clear_collection(name), make_material(name), set_unit_scale_metric(), save_dated_copy(). Make them idempotent.
3. Write blender/scripts/00_check_env.py that can be run headless (blender -b -P) and prints the same information.
4. Run it headless and report the output.
5. Tell me if headless Blender runs on this machine, and give the exact command I should use.

Acceptance: both the MCP check and the headless check succeed, or you give me clear error messages and the likely cause.
```

### Prompt 1 — Cage geometry

```text
Task: Build the cage geometry in blender/scripts/10_cage.py. Read rules.md first.

Do:
1. Create the cage base (rounded-corner plastic tub), clear front and side panels, and a top rim, using the default dimensions in rules.md unless I give others. Put everything in the CAGE collection.
2. Add real-world detail: bevelled edges, a lip where the lid would sit, corner radius, slight wall thickness, small ventilation slots on one wall.
3. Build these props as separate objects in PROPS, each with a sensible origin and name: a solid-surface exercise wheel on a stand (0.28 m diameter), a ceramic food bowl, a wall-mounted water bottle with a metal spout, a wooden hideout with an arched doorway, and a tunnel made of two straight sections and one curved section.
4. Place them with small, deliberate imperfections (not perfectly aligned), leaving a clear path for the hamster.
5. Make the script idempotent: re-running clears and rebuilds only the CAGE and PROPS collections.
6. Render a three-quarter view and a top view to renders/tests/.

Acceptance: dimensions match rules.md, objects are named and in the right collections, the script runs headless, and you list anything that looks wrong or artificial in the render.
```

### Prompt 2 — Bedding, seeds, and clutter

```text
Task: Build bedding and clutter in blender/scripts/20_clutter.py. Read rules.md first.

Do:
1. Create an uneven bedding surface 0.15-0.20 m deep using a displaced subdivided mesh with layered noise (large mounds plus small ripples). Add a shallow depression where a nest would be, and a compressed trail along one wall.
2. Scatter bedding detail on top: small curved shavings or paper strips as instanced geometry (use geometry nodes or particle instancing), with random scale, rotation, and density variation. Keep triangle counts under control by using a few base pieces.
3. Add seeds, pellets, and a small hoard in a corner, scattered with a physics-free random distribution (small clusters plus loose strays).
4. Add a few chewed edges to the wooden hideout and tunnel using a procedural displacement or small boolean cuts.
5. Put bedding in BEDDING and seeds and chews in PROPS. Use a fixed random seed variable at the top of the script so the layout is reproducible, and let me change it.
6. Render a close-up of a bedding corner and a wide shot to renders/tests/.

Acceptance: the bedding looks uneven and natural rather than a flat plane, the script is idempotent, and you describe where the scatter looks repetitive or too regular.
```

### Prompt 3 — Materials

```text
Task: Create materials in blender/scripts/30_materials.py. Read rules.md first.

Do:
1. Download or use free CC0 textures from Poly Haven or ambientCG for: wood grain (hideout, tunnel, chew blocks), ceramic (bowl), paper or aspen bedding, and plastic base. If you cannot download them from this environment, tell me which exact assets I should download and where to put them, then wait.
2. Build PBR shader node setups with: roughness variation maps, a subtle bump or normal map, and procedural wear (edge scratches, dust in crevices, fingerprint-like smudges on the clear panels).
3. Glass or clear plastic: use a physically plausible shader with a small thickness, slight edge tint, and faint smudge roughness. Avoid fully clear, perfect glass.
4. Metal: brushed steel for the water-bottle spout and wheel axle, with micro-scratches.
5. Paper bedding: translucent with a subtle subsurface or transmission setting so thin pieces glow slightly when backlit.
6. Assign materials by object name prefix, so re-running the script is safe.
7. Log every texture's source URL and licence in reference/licence_log.csv.
8. Render material test spheres and the cage with the new materials to renders/tests/.

Acceptance: no flat single-value roughness anywhere, licences logged, and you list which materials still look CG and why.
```

### Prompt 4 — Lighting and camera

```text
Task: Build lighting and camera rigs in blender/scripts/40_lighting_camera.py. Read rules.md first.

Do:
1. Use a free Poly Haven HDRI of a plain indoor room for world lighting. Record it in licence_log.csv. If you cannot download it, tell me the exact HDRI name to download and where to put it.
2. Add a large soft window-like area light as a key, a weak ceiling fill, and a warm low-intensity lamp for a night preset. Make three lighting presets (day, evening, night) switchable by a variable at the top of the script.
3. Create three cameras in CAMERAS: a low macro (about 85 mm, shallow depth of field), a three-quarter (50 mm), and a wide (35 mm). Enable depth of field and set focus distances. Name them clearly.
4. Add subtle imperfections in the render settings: slight vignette and grain through the compositor, mild bloom only on bright highlights.
5. Set Cycles to the test render settings in rules.md. Add a function to switch to final settings.
6. Render each camera under each preset at low samples to renders/tests/ and build a contact sheet.

Acceptance: contact sheet exists, soft shadows and bounce light are visible, and you list what still looks synthetic (for example, shadows too clean or highlights too even).
```

### Prompt 5 — Fur setup (on a placeholder body)

```text
Task: Build a fur system in blender/scripts/50_fur_setup.py on the hamster base mesh. Read rules.md and reference/parameter_estimates.md first.

Context: hamster.blend contains a base body mesh named ham_body (or a simple placeholder if I have not sculpted it yet). If no mesh exists, create a clearly labelled placeholder capsule body at hamster scale and tell me to replace it later.

Do:
1. Use Blender's modern hair curves with geometry nodes (not the legacy particle system) if this Blender version supports it. Tell me the version you detected and the nodes or modifiers you used.
2. Build three layers: undercoat (very dense, short, slightly curly, paler), guard hairs (longer, straighter, tapered, slightly darker tips), and face fur (very short, radiating from the nose). Expose these as named parameters at the top of the script: length, density, thickness, clump amount, curl, and random seed.
3. Drive direction with a flow map or vertex-group-based flow (head to rump on the back, outward on the cheeks, flat on the belly). Use a placeholder flow and tell me how to repaint it.
4. Add clumping and a small amount of random length and thickness variation. Add a hair shader with anisotropic highlight, colour variation along the strand, and translucency for backlight.
5. Keep ears and nose with sparse or no fur so skin shows through.
6. Render three macro views (side lit, back lit, front lit) to renders/tests/ at modest samples. Report render time per frame.
7. Create a lower-density preview setting so the viewport stays usable on this machine.

Acceptance: three layers exist and are tunable from one place, the fur has visible clumping and flow, render times are reported, and you list what does not look like real fur yet. Do not claim photorealism.
```

## 5. Repair and review prompts

**Repair:**

```text
The last task did not meet its acceptance criteria.
Problem: <describe what looks wrong or paste the error>.
Do not rebuild the scene. Diagnose first: tell me the likely cause. Then make the smallest change in the relevant script, re-run it headless, render a new test, and show what changed.
```

**Reference comparison:**

```text
Task: Compare renders/tests/<image> with reference/photos/<file>.
Build a side-by-side image in renders/compare/. List differences in: proportions, colour and tone, texture detail, light direction and softness, scale cues, and wear. Rank the three most important fixes. Do not apply them yet.
```

**Weekly review:**

```text
Task: Review the repository against rules.md.
Check: scripts are idempotent, collections and names follow the rules, licences are logged, no paid assets, no unverified measurements. List problems by severity.
```

## 6. Expectations and limits

- These prompts will give you a solid, realistic **cage and environment** and a well-structured **fur system**. The hamster's face, eyes, and body shape still need your sculpting and reference work (see the Design Specification).
- Fur render times can be long, so keep the preview setting low while you work.
- The agent may be confident about Blender API details that changed between versions. Always ask it to state the Blender version it used and to test headless.
- If Antigravity's free quota runs out mid-session, copy `rules.md` and the current prompt into another MCP-enabled editor and continue.

## 7. What comes next

Once the cage and the fur system render convincingly:

1. Sculpt or adapt the hamster body and replace the placeholder.
2. Rig and add blend shapes (cheek pouches, blink, mouth, ears).
3. Add the procedural animation layers and a first walk cycle.
4. Run the first blind test on stills.
