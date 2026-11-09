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

