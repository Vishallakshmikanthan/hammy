# HAMMY — Realistic Design Specification

*Hamster and cage design brief for a near-photoreal result. Numbers below are typical ranges from common husbandry and anatomy references, written from general knowledge. Verify every dimension against your own reference photos and measurements before modelling.*

## 1. The standard we are aiming at

The goal is that a viewer cannot tell the virtual hamster and cage from real footage. Honest framing:

- **Cinematic moments (Blender Cycles):** realistic target. Hair curves, subsurface scattering, real camera optics.
- **Live browser view:** convincing at normal distance. Macro close-ups will show the limits of real-time fur and lighting.

Realism comes from getting many small things right at once. The most common giveaways, in order, are: **motion**, **eyes and nose**, **fur behaviour (clumping, translucency, flow)**, **contact and weight**, **lighting and camera imperfections**, **cage clutter and wear**. This spec covers all six.

## 2. Reference capture (do this before modelling)

A model built from memory looks generic. Build a reference library first.

| Reference type | Minimum | Notes |
| --- | --- | --- |
| Still photos of one hamster | 150+ | Front, side, three-quarter, top, belly, paws, face close-ups, ears, teeth, eyes with reflections |
| Video, free-moving | 2–3 hours | Walking, running, sniffing, standing, grooming, stuffing, digging, wheel, sleeping |
| Video, 120 fps slow motion | 15–30 min | Gait cycles, whisker movement, face wash. Many phones can record this. |
| Macro fur shots | 30+ | Fur at 5–10 cm, backlit and front-lit, wet and dry |
| Cage photos | 100+ | The exact cage type you will replicate, plus used cages showing wear |
| Scale shots | 10+ | Hamster beside a ruler, weighed on a scale |
| Audio | 20 min | Wheel, bedding, seeds, footsteps, squeaks, in a quiet room |

If you can borrow or care for a real hamster, you can film your own reference with full rights. If using web footage, record source and licence for each clip. Do not use footage you are not licensed to use.

Colour-match with a grey card and colour checker in at least some shots, so your albedo is calibrated.

## 3. Hamster design

### 3.1 Species and variant

**Syrian (golden) hamster, shorthair, adult, one chosen colour morph.** Pick one morph and stay consistent (for example, the classic golden-agouti or a cream). Different morphs have different guard-hair colour, undercoat and belly tones, so model one well.

### 3.2 Proportions (typical, verify against references)

| Feature | Typical |
| --- | --- |
| Body length (nose to rump) | about 13–18 cm (females tend to be larger) |
| Weight | about 100–150 g |
| Body shape | Stout, pear-like, wide hips, little visible neck |
| Tail | Very short stub, about 1 cm, mostly hidden by fur |
| Ears | Rounded, thin, lightly furred outside, slightly pinkish inside |
| Eyes | Large, dark, glossy, set on the side of a blunt face |
| Whiskers | Roughly 2–3 cm, bright pink-dark skin pads at roots |
| Front paws | 4 toes plus a tiny vestigial thumb |
| Hind paws | 5 toes |
| Incisors | Visible when mouth opens, orange-yellow enamel on the front surface |
| Cheek pouches | Extend back past the shoulders when full, visibly distort the face |
| Skin | Loose, especially around the neck and flanks |

Build the sculpt from your side-profile and top-view photos using image planes in Blender, then compare overlays in the viewport.

### 3.3 Anatomy details that sell realism

- **Face:** a slightly pointed muzzle that is broad at the cheeks. The nose is small, pink, moist, with a visible philtrum split and a subtle highlight line of wetness.
- **Eyes:** a near-black cornea with strong, small, soft window reflections. Add a thin wet rim (tear film) and slight eyelid thickness. Include a faint dark ring around the eye. Eyes must have blink and partial blink (squint when sleepy).
- **Teeth and mouth:** pink gums, hidden tongue, a small amount of wetness when chewing.
- **Paws:** pink skin, small dark claws, finely creased pads, a tiny bit of bedding stuck to them.
- **Belly and chest:** paler, finer fur, and sometimes visibly thinner coat.
- **Flank glands:** on Syrians, darker, slightly oily patches on the hips, visible as a subtle texture change.
- **Asymmetry:** no animal is perfectly symmetric. Add subtle left/right differences in fur flow and markings.
- **Imperfections:** flat patches from lying down, a few misplaced hairs, damp fur after drinking, bedding fragments, a slightly dusty coat.

### 3.4 Fur design (the hard part)

Build the groom with Blender hair curves and geometry nodes.

| Layer | Role | Guidance |
| --- | --- | --- |
| Undercoat | Density, soft colour base | Short, very dense, paler, slightly curly |
| Guard hairs | Silhouette, direction, sheen | Longer, straighter, tapered tips, slightly darker tips |
| Face fur | Very short, fine, follows muzzle contours | Direction radiates from the nose |
| Ear fur | Sparse, short | Skin shows through |
| Whiskers | Separate geometry | Tapered, translucent, with a tiny curve |

Typical working lengths are roughly 8–15 mm for body fur and under 4 mm on the face. Check against your macro photos and adjust.

**Fur behaviours to reproduce**

- Flow direction maps (head to rump on the back, outward on the cheeks, flat on the belly).
- **Clumping:** hairs gather into tufts, more when damp or oily.
- **Part lines:** where skin folds, the coat parts.
- **Translucency:** backlit fur glows; thin fur on ears shows pink skin.
- **Compression:** fur flattens against surfaces the animal lies on.
- **Movement:** guard hairs lag slightly behind the body, with secondary jiggle on loose skin.
- **Dust and static:** a few stray hairs lifted, especially after grooming.

**Real-time translation**

- Bake the groom to shells plus silhouette fins for the browser, using the same flow, length and colour maps.
- Keep the full groom for Cycles moments.
- Provide LOD levels (close, mid, far) with automatic switching.

### 3.5 Skin and materials

| Surface | Material notes |
| --- | --- |
| Nose | Moist, strong small specular, slight subsurface |
| Ears | Strong subsurface, thin-transmission glow when backlit |
| Paw pads | Pink, matte-to-satin, fine creases |
| Claws | Dark translucent keratin |
| Eyes | Glossy cornea, soft reflection of environment, slight wetness |
| Teeth | Subtle subsurface, orange-yellow enamel on the front |
| Fur | Anisotropic highlight, rim light, subsurface in the undercoat |

Use real-world HDRIs so reflections in the eyes match the cage environment.

### 3.6 Rig and deformation

**Visual skeleton (about 60–100 bones):**

- Spine chain (at least 5 bones), neck, skull, jaw.
- Shoulders and hips, front and hind limbs with distinct toe bones.
- Ears (2–3 bones each), whiskers (grouped chains or blend shapes), tail stub.
- Spring bones for fur and skin jiggle.

**Blend shapes**

- `cheek_pouch_left/right` (0 empty to 1 packed), `blink`, `squint`, `mouth_open`, `chew`, `nose_wrinkle`, `ear_fold`, `whisker_forward`, `breath_in`.

**Deformation quality**

- Loose skin: use corrective shapes at the shoulders and hips so the skin slides over the body.
- Cheek pouches must displace the face and neck smoothly, not just scale.

### 3.7 Motion design

Motion is the largest realism lever.

| Behaviour | Visual signatures to capture |
| --- | --- |
| Walking | Low, waddling gait, flexible spine, head bobbing, hind feet placed near front prints |
| Running | Rapid bounding, spine arch, short flight phases |
| Sniffing | Fast nose twitch (about 5–10 Hz), whiskers sweep forward, head sweeps low |
| Standing up | Hind-leg stance, front paws tucked, head scanning, whiskers active |
| Grooming | Face wash with both paws, side lick, hind-leg scratch, sitting posture |
| Cheek stuffing | Paws push seeds into the mouth, pouches fill visibly, chewing is minimal |
| Digging | Alternating front-paw scoops, bedding thrown backwards, hind-paw kicks |
| Wheel | Steady trot, body angle changes with speed, occasional stop-and-drift |
| Sleeping | Curled posture, slow breathing, occasional twitch, ears flat |
| Startle | Freeze, flat ears, wide eyes, sudden bolt to cover |
| Drinking | Short licks at the spout, head tilted up, droplets on whiskers |

**Timing and variability:** real animals vary. Randomise timing, pause length, and gait phase slightly. Add idle micro-motion at all times (breathing, whisker drift, ear flicks, blinks every few seconds), because a perfectly still hamster looks like a statue.

**Weight:** the animal should look 100–150 g. Footfalls need soft contact, paws compress fur and bedding, and the body should settle rather than float.

## 4. Cage design

Choose one real cage type and replicate it exactly, because mixed styles look wrong. Two options:

| Option | Look | Notes |
| --- | --- | --- |
| Large bin or glass tank | Clean, easy to render with realistic glass | Good for the first version; glass reflections add realism but need care |
| Wire-top cage with plastic base | Bars give strong photographic cues | More complex geometry, bar shadows over the scene |

### 4.1 Size and layout

Commonly cited welfare guidance recommends a large floor area (often 450 sq in or about 2900 cm² or more of unbroken floor) and deep bedding for burrowing (roughly 15–20 cm or deeper). Use a layout that fits those numbers, which also makes the cage look like a properly kept real habitat.

### 4.2 Contents

| Item | Realism notes |
| --- | --- |
| Bedding | Paper or aspen shavings in mixed sizes, uneven surface, tunnel collapses, compressed areas where the hamster sleeps |
| Wheel | Syrian hamsters need a large wheel (commonly 11–12 inch or about 28–30 cm); solid running surface, slight wobble, bearing hum, scuffed plastic |
| Hideout | Wood or ceramic, bedding spilling in and out |
| Food bowl | Ceramic with a few seeds, spilled seeds nearby |
| Water | Bottle with a metal spout, droplets, slight condensation |
| Tunnels | Cardboard or wood, chewed edges, bedding at the openings |
| Chew items | Wood blocks with visible bite marks |
| Sand bath | Fine sand with tracks |
| Nest | Torn tissue or paper, messy and layered |
| Cardboard and toys | Slightly crumpled, chewed corners |

### 4.3 Wear and clutter (what makes it look real)

- Bedding mounds and trails along walls.
- Scattered seeds and hoarded stashes in corners.
- Dust on surfaces and small smudges on the glass or plastic.
- Scratches on the wheel and bowl.
- Slightly uneven placement of everything. Perfectly arranged objects look rendered.
- A day/night cycle where the cage becomes visibly messier over days and resets when the parent cleans it. That is gameplay and realism at once.

### 4.4 Materials

| Surface | Notes |
| --- | --- |
| Glass or clear plastic | Fresnel reflections, fingerprint smudges, edge tint, subtle refraction |
| Metal bars | Brushed or coated steel, slight imperfections |
| Plastic base | Soft specular, scuffs and tiny scratches |
| Wood | Real grain, chewed edges, slight discolouration |
| Ceramic | Glazed, uneven, small chips |
| Paper bedding | Translucent fibres, light bleeding through thin pieces |

Use PBR with roughness variation maps, not a single flat value.

## 5. Lighting and camera

- **Light sources:** one window-like soft key, a ceiling room light, and a warm lamp for night. Use HDRIs captured in a room similar to the setting.
- **Shadows:** soft, with contact shadows under objects and under the hamster.
- **Global illumination:** bounce light from bedding is subtle but strongly improves realism. Use baked or screen-space approximations in real time, full GI in Cycles.
- **Camera imperfections:** shallow depth of field, slight lens vignette, tiny motion blur, subtle noise and grain, and occasional focus hunting in cinematic moments.
- **Camera behaviour:** use real filming conventions (low angle, slow drift, handheld micro-motion on request). Avoid perfectly smooth CG camera moves.
- **Night view:** a dim warm light with a visible noise floor, as if shot on a phone.

## 6. Audio design

| Sound | Notes |
| --- | --- |
| Wheel | Rhythmic whirr tied to the actual wheel speed, with a slight squeak |
| Footsteps and rustle | Tied to contact events and bedding depth |
| Seed crack and chew | Tied to eating events |
| Sniffing and breathing | Subtle, closer when the camera is near |
| Squeaks | Rare, context-based |
| Room tone | Low ambient hum |

Drive audio from physics contact events and skill states so it stays synchronised.

## 7. Asset production pipeline

1. **Reference library** (Section 2).
2. **Sculpt** high-poly hamster in Blender or ZBrush.
3. **Retopologise** to about 30–60k triangles (body) and create LODs.
4. **UV and texture** (albedo, roughness, subsurface, normal, flow, length and density maps).
5. **Groom** with hair curves, then bake to shells and fins.
6. **Rig** and weight-paint, add blend shapes and corrective shapes.
7. **Animate** a base set of clips, then add procedural layers.
8. **Cage modelling** with real measurements, then PBR textures and wear passes.
9. **Export** glTF for the browser (with Draco or meshopt compression) and keep .blend files for Cycles.
10. **Test** in-engine against the reference footage side by side.

**Budgets (starting targets, adjust after benchmarking)**

| Item | Target |
| --- | --- |
| Hamster body (high LOD) | 30–60k triangles |
| Hamster body (low LOD) | 5–10k triangles |
| Texture sets | 2K–4K for the hamster, 2K for major cage items |
| Total scene (high preset) | Measured on your laptop, then fixed as a budget |
| Total scene (mobile preset) | Measured on a mid-range phone, then fixed as a budget |

## 8. Quality presets

| Preset | Fur | Shadows | Post effects | Target device |
| --- | --- | --- | --- | --- |
| Ultra | Highest shell count plus fins, strand if feasible | Soft, high resolution | DoF, AO, subtle grain | Your RTX laptop |
| High | Shells plus fins | Soft | AO | Recent laptops |
| Medium | Fewer shells | Standard | Light AO | Older laptops |
| Low | Minimal shells, fur colour only at distance | Basic | None | Phones |
| Cinematic (offline) | Full strand groom | Path-traced | Full film look | Rendered video |

## 9. Realism QA checklist

Review every asset and animation against this list.

**Hamster**

- Proportions match reference overlays in side and top views.
- Eyes show correct reflections and wet rim; blinks occur.
- Nose looks moist, with small movement at rest.
- Fur flows correctly, shows clumps, has translucency at ears and rim.
- Cheek pouches deform believably.
- Idle micro-motion never stops.
- Gait matches reference stride timing, with variability.
- Paws compress bedding and leave marks.
- Weight reads as about 100–150 g.

**Cage**

- Dimensions match the chosen real cage.
- Bedding is uneven, compressed and has trails.
- Objects are scuffed, chewed and not perfectly placed.
- Glass or plastic has fingerprints and edge tint.
- Lighting has bounce, soft shadows and a believable colour temperature.

**Scene**

- Camera has depth of field, grain and tiny imperfections.
- Audio is synchronised with events.
- No pixel-perfect symmetry or perfect tidiness.

## 10. Blind test protocol (how you prove it)

1. Prepare 20 short clips (5–10 s each): 10 real hamster, 10 HAMMY, matched for framing, lighting and behaviour.
2. Strip watermarks and metadata, randomise order.
3. Show them to 15–30 people who are not in the project and ask "real or generated?" with a confidence rating.
4. Run separate tests for **stills**, **live-view clips**, and **cinematic moments**.
5. Record accuracy per tier. The target is accuracy near 50% (chance) for cinematic moments. For the live view, track the percentage fooled at normal distance and report it honestly.
6. Keep a list of what people say gave it away (eyes, motion, fur, lighting) and fix those in order.

Repeat the test after each major asset or animation upgrade.

## 11. Known limits to accept

- Per-hair lighting and wetness in real time at macro scale is not currently practical on a laptop browser.
- Real-time deformable bedding is an approximation, not true granular simulation.
- Digging and burrow collapse will be visually authored or lightly simulated, not fully physical.
- Some viewers will always spot CG in motion if the behaviour timing is off, which is why the behaviour work and the blind tests matter as much as the textures.

## 12. Suggested build order for the art

1. Reference library and cage choice (weeks 1–2).
2. Hamster sculpt and proportions check (weeks 3–5).
3. Eyes, nose and face detail (they sell the illusion; weeks 5–6).
4. Groom and fur materials, then browser bake (weeks 6–10).
5. Rig, blend shapes, idle animation (weeks 9–12).
6. Cage model, materials and wear (parallel, weeks 8–12).
7. Core animations: walk, sniff, groom, sleep, then stuffing, standing, wheel, digging.
8. First blind test on stills, then on short clips.

Time estimates are planning guesses for a solo artist-engineer; re-baseline after the first sculpt.

## Appendix A. Internet-only reference collection

*This appendix replaces the filming assumptions in Section 2 when you cannot film a real hamster. Everything here is collected from online sources. Licence terms change, so confirm each site's current terms and each file's licence before you rely on it. This is not legal advice.*

### A.1 What changes

- You lose controlled angles, scale references, and 120 fps slow motion.
- You keep most of what matters for realism: proportions, fur look, eyes, gait style, behaviour sequences, cage appearance.
- Any parameter you cannot measure directly (whisker frequency, stride timing, fur length) is recorded as **estimated** with a confidence rating, and the design is reviewed again if better footage appears.

### A.2 Sources

| Source | Content | Licence notes | Best for |
| --- | --- | --- | --- |
| Pexels | Photos and videos | Pexels licence: free for personal and commercial use, no attribution required | Clean footage, close-ups |
| Pixabay | Photos and videos | Pixabay licence: free use, no attribution required | Volume, variety |
| Mixkit, Videvo | Stock video | Own licences; Videvo may require attribution | Extra clips |
| Videezy | Stock video | Attribution may be required for commercial use | Extra clips |
| Wikimedia Commons | Photos, some video | Varies per file; some are CC BY-SA, which requires attribution and share-alike | Anatomy and proportion photos |
| YouTube (Creative Commons filter) | Long natural behaviour videos | Check each video's licence and YouTube's terms before downloading | Grooming, wheel, burrowing, sleeping |
| Internet Archive | Older footage and documentaries | Varies per item | Occasional unique material |
| Scientific papers | Supplementary videos and figures | Varies per publisher | Locomotion and anatomy detail |
| Paid stock (Getty, Adobe Stock) | High quality, many angles | Paid; check whether the licence allows use as modelling or machine-learning reference | Optional, only for key clips |

Prioritise the free sources first. Skip anything whose licence you cannot read.

### A.3 Target collection

| Category | Target | Notes |
| --- | --- | --- |
| Syrian hamster photos | 150+ | Side, top, front, three-quarter, face close-ups, paws, ears, eyes, belly |
| Behaviour clips | 5–10 per behaviour | Walk, run, sniff, stand, groom, stuff, dig, wheel, sleep, startle, drink, eat |
| Long clips (30 s or more) | 10+ | Best for gait cycles and idle micro-motion |
| Cage and bedding photos | 100+ | New and well-used cages, one consistent cage type |
| Wheel footage | 10+ clips | Wheel size, speed, scuffs, gait on the wheel |
| Macro fur photos | 30+ | Backlit, front-lit, damp, groomed |
| Audio | 10+ clips | Wheel, bedding, seeds, footsteps (check licence) |

### A.4 Search terms

| Goal | Search terms |
| --- | --- |
| Body proportions | Syrian hamster side view, golden hamster full body, hamster on white background |
| Face detail | hamster face close up, hamster eyes macro, hamster nose |
| Fur | hamster fur macro, hamster backlit fur, wet hamster |
| Walking and running | hamster walking, hamster running, hamster exploring |
| Standing | hamster standing up, hamster on hind legs |
| Grooming | hamster grooming, hamster face washing |
| Cheek stuffing | hamster cheeks stuffed, hamster hoarding food |
| Digging | hamster digging, hamster burrow |
| Wheel | hamster wheel running, hamster wheel slow motion |
| Sleeping | hamster sleeping, hamster waking up |
| Cage | hamster cage setup, hamster bin cage, hamster deep bedding |

Also try the Latin name *Mesocricetus auratus* and the terms "golden hamster" and "teddy bear hamster" for different morphs.

### A.5 Clip selection checklist

Keep a clip only if it passes most of these:

- Syrian hamster (not a dwarf species or a different rodent).
- Camera is mostly fixed or steady.
- No fast cuts, filters, or heavy colour grading.
- Full body visible for gait clips; face visible for facial clips.
- Frame rate is at least 24 fps, and ideally 50 or 60.
- Natural behaviour, not a hamster being held or posed (unless you need it for scale).
- Licence is clear and recorded.

Discard clips with obvious speed-ramping, because they will corrupt your timing estimates.

### A.6 Folder structure

```text
reference/
  photos/
    body/  face/  paws/  fur/  cage/
  video/
    walk/  run/  sniff/  stand/  groom/  stuff/  dig/  wheel/  sleep/  startle/  drink/  eat/
  audio/
  papers/
  licence_log.csv
  parameter_estimates.md
```

### A.7 Licence log (one row per file)

| Column | Example |
| --- | --- |
| file\_name | pexels\_hamster\_wheel\_01.mp4 |
| source\_site | Pexels |
| source\_url | link to the page |
| creator | name shown on the page |
| licence | Pexels licence |
| date\_accessed | the day you downloaded it |
| behaviour | wheel |
| quality (1–5) | 4 |
| used\_for | gait reference |
| notes | slight camera movement |

If you later publish the project, credit anyone whose licence requires it, and remove any file whose licence you cannot confirm.

### A.8 Extracting numbers from online footage

1. **Frame rate:** read it from the file metadata, and note whether the clip was edited. Do not assume.
2. **Scale:** estimate from known objects, such as a wheel of known diameter or a food bowl. Mark scale as **estimated**.
3. **Gait:** step through frames and mark footfalls. Record stride frequency, duty factor, and speed relative to body length.
4. **Pose:** run a pose-estimation tool (such as DeepLabCut or SLEAP) on a small set of labelled frames per behaviour. Expect noisy results from variable footage.
5. **Motion style:** use relative measurements (body lengths per second, cycles per second) rather than absolute metres.
6. **Record everything** in `parameter_estimates.md` with the clip names used, the method, and a confidence rating (low, medium, high).

### A.9 Parameter confidence table

| Parameter | Source | Confidence | Review trigger |
| --- | --- | --- | --- |
| Body proportions | Photo overlays | Medium to high | When a new reference photo contradicts the model |
| Fur length and density | Macro photos | Medium | When better macro photos are found |
| Eye and nose appearance | Close-up photos | High | Rarely |
| Walk and run stride timing | Frame-by-frame in clips | Low to medium | Better footage becomes available |
| Whisker and nose twitch rates | Clip analysis | Low | Slow-motion footage becomes available |
| Grooming sequences | Long clips | Medium | New clips with different sequences |
| Cage dimensions | Product specs and photos | High | Rarely |

### A.10 Quality limits to accept

- Without controlled capture, the gait style will be believable but not measured. The blind test (Section 10) is your check.
- Some hamsters in stock footage are tame, being handled, or in unusual environments. Prefer free-roaming behaviour in a cage.
- If your motion still reads as fake in the blind test, the cheapest improvement is a short slow-motion clip from anyone who has a hamster and a phone. That does not have to be you.

### A.11 First week checklist

1. Set up the folder structure and licence log.
2. Collect 50 photos and 20 behaviour clips from Pexels and Pixabay.
3. Collect 10 long clips from YouTube Creative Commons.
4. Sort clips by behaviour and score quality.
5. Choose one cage type and gather product and measurement references.
6. Write the first draft of `parameter_estimates.md` with confidence ratings.
7. Start the body proportion overlays in Blender.
