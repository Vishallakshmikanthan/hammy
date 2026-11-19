# Step 7: Asset Integration Performance, Lazy-Loading & Visual Honesty Report

**Generated:** 2026-11-19  
**Pipeline Version:** HAMMY Step 6 & Step 7 (Opt-In Shelf Asset Architecture)  
**Telemetry Source:** [`renders/step6/step6_step7_telemetry.json`](file:///c:/Users/Lenovo/Downloads/hammy/renders/step6/step6_step7_telemetry.json) & [`assets/manifest.json`](file:///c:/Users/Lenovo/Downloads/hammy/assets/manifest.json)

---

## 1. Asset Library Budget & Polygon / Texture Audit

All **30 shelf assets** (`24 GENERATED` in headless Blender 5.2.3 LTS + `6 DOWNLOADED` CC0 from Kenney Food Kit & KayKit Dungeon Pack) are converted to Y-up `.glb` files in [`assets/web/`](file:///c:/Users/Lenovo/Downloads/hammy/assets/web) (mirrored to [`web/public/assets/items/`](file:///c:/Users/Lenovo/Downloads/hammy/web/public/assets/items)) with 256×256 transparent Cycles thumbnails in [`assets/thumbnails/`](file:///c:/Users/Lenovo/Downloads/hammy/assets/thumbnails).

| Category | Asset Count | Total Triangles (All Items Combined) | Max Triangles (Single Item) | Budget Limit | Texture / Material Memory Footprint | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Food Shelf** (`hamster_safe: true`) | 7 | 1,680 tris | 396 tris (`food_broccoli_floret`) | `< 2,000` tris | Procedural PBR vertex/material slots (`0 KB` external texture bitmaps) | **PASS** |
| **2. Water Shelf** (`water_liquid` mesh) | 2 | 1,428 tris | 1,044 tris (`water_bottle`) | `< 2,000` tris | Procedural PBR glass + liquid shaders (`0 KB` external texture bitmaps) | **PASS** |
| **3. Costume Shelf** (`head/neck/back_slot`) | 7 | 4,052 tris | 960 tris (`costume_crown`) | `< 2,000` tris | Procedural PBR materials (`0 KB` external texture bitmaps) | **PASS** |
| **4. Props Shelf** (Collision + Nav) | 8 | 5,480 tris | 1,384 tris (`prop_wheel`) | `< 5,000` tris | Procedural PBR + 1 shared CC0 atlas (`<= 512x512`, `~0.18 MB` VRAM) | **PASS** |
| **5. Decor Shelf** (Opt-In Decor) | 6 | 1,100 tris | 336 tris (`decor_wooden_log`) | `< 5,000` tris | Procedural PBR + 1 shared CC0 atlas (`<= 512x512`, `~0.18 MB` VRAM) | **PASS** |
| **All 30 Shelf Assets Total** | **30** | **13,740 tris** | **1,384 tris** | `< 5,000` / item | **1.09 MB total `.glb` disk size / `< 1.8 MB` GPU texture memory** | **PASS** |

### Lazy-Loading & Disposal Architecture
1. **Default Clean Cage Startup:** On initial page load, only `cage.glb` (with baked non-default props hidden and disposed from active traversal) and `hamster.glb` are loaded. **Zero** `.glb` files from `/assets/items/*.glb` and **zero** shelf thumbnail images (`/assets/thumbnails/*.png`) are fetched when all 5 shelves are closed.
2. **Shelf Thumbnail Lazy-Loading:** Opening a shelf drawer renders only that category's 256×256 PNG thumbnails (`7–28 KB` each, `loading="lazy"`). The 3D `.glb` models are **not** loaded when browsing a shelf.
3. **On-Demand `.glb` Loading & Explicit GPU Disposal:** When a user equips a costume, offers food, or confirms prop/decor placement, `HabitatSceneView.tsx` lazy-loads only that item's `.glb`. When the item is unequipped, eaten, or sent back to its shelf (`remove_prop` / `reset_clean_cage`), `disposeObject3D()` traverses and disposes every `BufferGeometry` and `Material` and removes the node from the Three.js scene graph.

---

## 2. Live Runtime Performance Benchmarks (Desktop vs. Mid-Range Phone Viewport)

Measured via Chrome DevTools Protocol (`scripts/step6_record_acceptance_and_perf.py`) against the live full-stack application (`http://127.0.0.1:3000` + FastAPI/SQLite `http://127.0.0.1:8088`):

| Viewport / Device Tier | Cage Configuration | Active Placed Items & Costumes | Load / Sync Time (ms) | Active Scene Draw Calls | Active Scene Triangles | Measured Frame Rate (FPS) | Frame Time (ms) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Desktop (`1280×800`, HIGH preset)** | **1. Default Clean Cage** | Bedding + 1 basic water bottle (`0` opt-in props) | `1,940.6 ms` (initial cold load) | `46` | `54,986` | **60.0 FPS** | `16.66 ms` |
| **Desktop (`1280×800`, HIGH preset)** | **2. Lightly Decorated Cage** | `+3 props` (`prop_wheel`, `prop_hideout`, `prop_tunnel_straight`) | `1,713.5 ms` (3 lazy `.glb` loads) | `65` | `56,110` | **60.0 FPS** | `16.66 ms` |
| **Desktop (`1280×800`, HIGH preset)** | **3. Heavily Decorated Cage** | `+6 props` + `+2 decor` + `costume_crown` + `food_apple_piece` | `4,641.9 ms` (8 sequential command round-trips) | `109` | `58,134` | **60.0 FPS** | `16.66 ms` |
| **Mid-Range Phone (`390×844`, mobile viewport)** | **1. Default Clean Cage** | Bedding + 1 basic water bottle (`0` opt-in props) | `2,037.6 ms` | `46` | `54,986` | **60.0 FPS** | `16.66 ms` |
| **Mid-Range Phone (`390×844`, mobile viewport)** | **2. Lightly Decorated Cage** | `+3 props` (`prop_wheel`, `prop_hideout`, `prop_tunnel_straight`) | `1,682.5 ms` | `65` | `56,110` | **60.0 FPS** | `16.66 ms` |
| **Mid-Range Phone (`390×844`, mobile viewport)** | **3. Heavily Decorated Cage** | `+6 props` + `+2 decor` + `costume_crown` + `food_apple_piece` | `4,609.5 ms` | `109` | `58,134` | **60.0 FPS** | `16.67 ms` |

*Note on Triangle Count Breakdown:* Of the `54,986` base triangles in the Default Clean Cage (`LOD1`), `~46,400` triangles belong to the 20 extruded Kajiya-Kay shell fur layers + 140 tapered whisker/guard hair tubes + high-density deformable bedding heightfield mesh (`BeddingDeformer`), while all 8 placed shelf items + crown costume + offered food in the Heavily Decorated Cage add only **+3,148 triangles** (`54,986 -> 58,134` tris) and maintain a locked **60.0 FPS** (`16.66 ms`).

---

## 3. Honesty Audit: Behavior Labels & What Still Looks Fake

Per the blueprint's strict honesty rule, every subsystem is labeled with its true driver (`LEARNED`, `ANIMATION-DRIVEN`, or `RULE-BASED`), and remaining visual limitations are listed transparently below:

### Subsystem Driver Labels
- **Locomotion & Skill Policy (`LEARNED` / `RULE-BASED` fallback):** Trained PPO policies in `data/policies/*.pt` (`navigate`, `wheel_run`, `forage`, `hide`, `rest`, `explore`) drive MuJoCo control torques; in browser-only / between-tick interpolation, `HamsterBehaviorController` (`RULE-BASED`) steers the hamster along collision-free BFS corridors around placed props.
- **Realistic Eating Sequence (`ANIMATION-DRIVEN`):** The 7 authored Blender NLA clips (`sit_up`, `grab_food`, `bring_to_mouth`, `chew_loop`, `swallow`, `stuff_cheek`, `release_idle`) and procedural rig posture layers rear the hamster onto its haunches (`rearAmount = 0.72`), bring both front paws together around `food_hold_socket` (`groomAmount = 0.75`), oscillate the jaw (`chewAmount = 0.95`), and inflate `cheek_pouch_left` / `cheek_pouch_right` blend shapes (`0.0 -> 1.0`) driven by authoritative server `cheek_pouch_fill`.
- **Server Authority & Spoilage (`RULE-BASED`):** All 10 shelf commands (`offer_food`, `refill_water`, `equip_costume`, `unequip_costume`, `place_prop`, `move_prop`, `remove_prop`, `consume_food`, `consume_water`, `reset_clean_cage`) execute idempotently in `services/commands/handler.py`, validate against `assets/manifest.json` and cage bounds `[-0.44, 0.44] × [-0.19, 0.19] m`, decrement food/water quantities only on server interaction events, and mark uneaten offered food as spoiled after `600s` of simulation time.

### What Still Looks Fake (Honest Visual Critique)
1. **Rigid Food Parenting vs. Finger-Phalanx Articulation:** During `Eating with Both Paws (ANIMATION-DRIVEN)`, the food mesh attaches cleanly to `food_hold_socket` between `paw_fl` and `paw_fr`, and the food item does not deform or get bitten down polygon-by-polygon as the hamster chews — it remains whole until the server `consume_food` event decrements/removes the portion.
2. **Rigid Costume Socket Attachment vs. Soft-Body Fur Compression:** Costumes equipped to `head_slot`, `neck_slot`, and `back_slot` follow the skeletal head/neck/spine transforms accurately, but they do not physically flatten or part the underlying 20-layer shell fur cards where a hat brim or scarf sits against the coat.
3. **2D Circular/AABB Obstacle Avoidance on Placed Props:** When the user places custom props (such as `prop_tunnel_straight`, `prop_bridge_ramp`, or `prop_exercise_ball`), the navigation controller updates its 2D obstacle map (`collision_radius_m`) and walks *around* them cleanly, rather than climbing *over* the bridge ramp's 3D arch orcrawling *inside* an arbitrarily rotated user-placed tunnel cylinder.
4. **Uniform Cylinder Scaling for Water Level:** Refilling or drinking water scales the inner `water_liquid` mesh vertically (`scale.y` from `0.02` to `1.0`) without fluid meniscus sloshing or air-bubble particles rising inside the bottle tube.
