# HAMMY — Step 1 & Step 2: Downloaded Asset Audit & Gap Analysis

## 1. Executive Summary of Downloaded Archives (`assets/raw/`)

All four archive packages downloaded by the user into `props/` were copied into `assets/raw/` and unpacked for full inspection. Every single file (`2,766` unpacked files representing `524` unique 3D models plus `255` texture/preview `.png` files) was audited for format, byte size, vertex/polygon/triangle count, bounding-box scale in meters, textures present, author, source URL, and license compliance.

| Archive Name | Unpacked Files | Unique 3D Models | Formats Present | Textures Present | Author & Source URL | Licence | Audit Verdict |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| `kenney_food-kit.zip` | `1,009` | `200` | `.glb` (200), `.fbx` (200), `.obj/.mtl` (200) | `colormap.png` (`512×512` shared atlas) + `200` UI preview `.png`s | **Kenney** (`www.kenney.nl`) — `https://kenney.nl/assets/food-kit` | **CC0 1.0 Universal** (`License.txt` verified in archive) | **APPROVED** (Filter foods by hamster safety + rescale from ~0.13–0.33 m to 1–3 cm hamster scale) |
| `KayKit_Dungeon_Pack_1.1_FREE.zip` | `1,303` | `211` | `.gltf/.bin` (211), `.fbx` (422), `.obj/.mtl` (216) | `dungeon_texture.png` (`1024×1024` shared palette) + `22` sample `.png`s | **Kay Lousberg** (`www.kaylousberg.com`) — `https://kaylousberg.itch.io/kaykit-dungeon` | **CC0 1.0 Universal** (`License.txt` verified in archive) | **APPROVED** (Selective reuse of shelf, banners/flags, and small wooden items rescaled to hamster scale) |
| `drive-download-20261119T082111Z-1-001.zip` | `412` | `103` | `.blend` (103), `.fbx` (103), `.obj/.mtl` (103) | **Missing external file** (`//Blender/DavidThorn/Library/Large/Texture.png` referenced inside `.blend`s; flat `.mtl` colors only) | Unknown in archive (internal path references `DavidThorn`; topology matches Quaternius Ultimate Food Pack) | **UNCLEAR** (No `LICENSE` or `README` included in `.zip`) | **REJECTED** (Rule: *Never use an asset with an unclear licence*; also missing referenced texture file) |
| `Food&DrinksPack.rar` | `38` | `10` | `.fbx` (10) | `28` PBR `.png` textures (`Base_Color`, `Normal`, `Roughness`, `Height`) | Unknown (no author or README in `.rar`) | **UNCLEAR** (No `LICENSE` or `README` included in `.rar`) | **REJECTED** (Rule: *Never use an asset with an unclear licence*; also 100% processed human junk foods unsafe for hamsters) |

### Existing Procedural & CC0 Assets Already in Repository (`blender/` & `reference/licence_log.csv`)
In addition to `assets/raw/`, the repository already contains verified **CC0** textures from Poly Haven (`fine_grained_wood`, `plywood`, `bark_brown_02`, `concrete_floor_worn_001`, `brown_photostudio_02_1k.hdr`) and our metric SI Blender scripts (`blender/scripts/10_cage.py`, `20_clutter.py`, `60_rig_and_export_glb.py`) which procedurally construct the `0.28 m` exercise wheel, `0.08 m` ceramic food bowl, `0.15 m` wall-mounted water bottle, arched wooden hideout, straight/curved burrow tunnels, and chew sticks.

---

## 2. Classification Breakdown Across All 524 Audited Models

| Category | Total Audited Models | From Approved CC0 Packs (`Kenney` + `KayKit`) | From Rejected Unclear-Licence Packs (`drive-download` + `Food&DrinksPack`) | Approved & Hamster-Safe / Habitat-Ready Count |
| :--- | :---: | :---: | :---: | :---: |
| **`food`** | `217` | `125` | `92` | **`13`** |
| **`water`** | `0` | `0` | `0` | **`0`** |
| **`costume`** | `0` | `0` | `0` | **`0`** |
| **`prop`** | `21` | `21` | `0` | **`3`** |
| **`decor`** | `111` | `111` | `0` | **`9`** |
| **`other`** | `175` | `154` | `21` | **`0`** |

> **Note on `texture` category:** All `255` standalone `.png` texture/preview files in `assets/raw/` (`204` in `kenney_food-kit`, `23` in `KayKit_Dungeon_Pack_1.1_FREE`, `28` in `Food&DrinksPack.rar`) plus the `13` Poly Haven CC0 PBR texture maps in `blender/textures/` are audited in Section 3.5 below.

---

## 3. Veterinary Hamster-Safety Audit of Downloaded Food Models

Per Step 2 instructions (*"Check hamster safety against a reliable pet-care source and exclude anything unsafe or doubtful"*), every food item in `kenney_food-kit.zip` (`CC0`) was cross-checked against veterinary husbandry guidelines (**RSPCA**, **PDSA**, ** Merck Veterinary Manual**, and **California Hamster Association** safe food lists for Syrian hamsters, *Mesocricetus auratus*):

### 3.1 Approved Hamster-Safe Foods in `kenney_food-kit.zip` (CC0)
| Model ID | File Name (`.glb` / `.fbx` / `.obj`) | Size (GLB) | Polygons / Tris | Raw Scale `(X, Y, Z)` m | Target Hamster Scale | Veterinary Safety Assessment |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `kenney_apple_half` | `apple-half.glb` | `10,948 B` | `248 / 248` | `0.098 × 0.191 × 0.196` | `0.012–0.025 m` | SAFE (seedless piece only): Must remove apple seeds/core before offering to hamster. |
| `kenney_apple` | `apple.glb` | `14,376 B` | `272 / 272` | `0.196 × 0.191 × 0.196` | `0.012–0.025 m` | SAFE (in moderation, seedless piece): Apples are safe for Syrian hamsters when seeds/core are removed (cyanogenic glycosides in seeds). |
| `kenney_banana` | `banana.glb` | `12,348 B` | `208 / 208` | `0.138 × 0.196 × 0.630` | `0.012–0.025 m` | SAFE (in tiny portions): Fresh or dried banana chip is safe in very small amounts (high sugar). |
| `kenney_broccoli` | `broccoli.glb` | `20,452 B` | `440 / 440` | `0.375 × 0.422 × 0.375` | `0.012–0.025 m` | SAFE: Broccoli florets are an excellent hamster-safe dark green vegetable. |
| `kenney_carrot` | `carrot.glb` | `16,364 B` | `296 / 296` | `0.343 × 0.716 × 0.343` | `0.012–0.025 m` | SAFE (in moderation): Carrots are hamster-safe root vegetables (high natural sugar; offer as small piece). |
| `kenney_cauliflower` | `cauliflower.glb` | `16,592 B` | `304 / 304` | `0.380 × 0.307 × 0.404` | `0.012–0.025 m` | SAFE: Raw cauliflower florets are hamster-safe in small pieces. |
| `kenney_celery_stick` | `celery-stick.glb` | `5,964 B` | `104 / 104` | `0.046 × 0.540 × 0.088` | `0.012–0.025 m` | SAFE: Celery is hamster-safe if cut into tiny pieces to remove stringy fibers. |
| `kenney_corn` | `corn.glb` | `14,284 B` | `256 / 256` | `0.343 × 0.316 × 0.300` | `0.012–0.025 m` | SAFE: Plain sweetcorn kernels are a standard hamster-safe ingredient in seed mixes. |
| `kenney_pear_half` | `pear-half.glb` | `11,336 B` | `252 / 252` | `0.098 × 0.271 × 0.196` | `0.012–0.025 m` | SAFE (seedless piece): Pear flesh without seeds is safe in tiny cubes. |
| `kenney_pear` | `pear.glb` | `15,556 B` | `272 / 272` | `0.196 × 0.271 × 0.196` | `0.012–0.025 m` | SAFE (seedless piece): Pear flesh without seeds is safe in tiny cubes. |
| `kenney_pumpkin_basic` | `pumpkin-basic.glb` | `8,484 B` | `160 / 160` | `0.420 × 0.299 × 0.364` | `0.012–0.025 m` | SAFE: Pumpkin flesh and seeds are hamster-safe. |
| `kenney_pumpkin` | `pumpkin.glb` | `20,436 B` | `376 / 376` | `0.419 × 0.229 × 0.419` | `0.012–0.025 m` | SAFE: Pumpkin flesh and raw pumpkin seeds are hamster-safe and nutritious. |
| `kenney_strawberry` | `strawberry.glb` | `16,620 B` | `312 / 312` | `0.120 × 0.182 × 0.120` | `0.012–0.025 m` | SAFE (in moderation): Fresh strawberry piece is safe as an occasional hamster treat. |

### 3.2 Excluded Unsafe or Doubtful Foods in `kenney_food-kit.zip`
- **Avocado (`avocado`, `advocado-half`):** **UNSAFE (TOXIC)** — Contains persin, causing myocardial necrosis and respiratory distress in rodents.
- **Citrus (`orange`, `lemon`, `lemon-half`):** **UNSAFE (TOXIC)** — High citric acid causes stomach ulceration and diarrhea in hamsters.
- **Alliums (`onion`, `onion-half`, `leek`):** **UNSAFE (TOXIC)** — Organosulfoxides cause oxidative hemolysis of red blood cells (hemolytic anemia).
- **Sticky Peanut Butter (`peanut-butter` jar):** **UNSAFE (POUCH IMPACTION)** — Sticky paste adheres inside the cheek pouches, causing impaction and infection. *(Note: dry unsalted whole/shelled peanuts are safe, but a peanut model is missing from Kenney and must be generated in Step 3).*
- **Nightshades & Pungent Produce (`tomato`, `tomato-slice`, `eggplant`, `mushroom`, `mushroom-half`, `pepper`, `paprika`, `paprika-slice`, `radish`, `beet`, `pineapple`):** **UNSAFE / DOUBTFUL (EXCLUDED)** — Solanine, high acidity, or digestive irritants.
- **High-Water / Pit Fruits (`watermelon`, `grapes`, `cherries`):** **DOUBTFUL (EXCLUDED)** — Risk of wet-tail/diarrhea (`watermelon`), renal toxicity concerns (`grapes`), or cyanogenic pits (`cherries`).
- **Chocolate, Sweets & Pastries (`chocolate`, `candy-bar`, `donut*`, `cake*`, `cupcake`, `cookie*`, `ice-cream*`, `popsicle*`, `lollypop`, `sundae`, `pudding`, `waffle`, `pancakes`, `muffin`, `croissant`, `ginger-bread`, `honey`, `whipped-cream`):** **UNSAFE (TOXIC)** — Theobromine toxicity and high sugar/dairy.
- **Processed Fast Food, Meat, Fish, Dairy & Beverages (`burger*`, `hot-dog*`, `pizza*`, `fries*`, `bacon*`, `sausage*`, `meat*`, `whole-ham`, `turkey`, `corn-dog`, `taco`, `sub`, `sandwich`, `sushi*`, `maki*`, `fish*`, `mussel*`, `cheese*`, `bread*`, `loaf*`, `egg*`, `soda*`, `wine*`, `cocktail`, `frappe`):** **UNSAFE (EXCLUDED)** — Salt, spices, fat, alcohol, caffeine, and spoilage risks.

---

## 4. Step 2: Gap Analysis Against Minimum Required Set

Comparing our audited, license-approved (`CC0`) assets against the mandatory feature list in Step 2 and the Shelf-Based Override:

### 4.1 Food Shelf (Hamster-Safe Only)
| Required Item | Audit Status in `assets/raw/` | Action for Step 3 (Blender Generation / Adaptation) |
| :--- | :--- | :--- |
| **1. Seed mix** (`food_seed_mix`) | **MISSING** as standalone pickupable/offerable `.glb` in `assets/raw/` (exists in `blender/scripts/20_clutter.py` as multi-mesh bowl scatter) | **GENERATE in Step 3**: Build low-poly hamster-scale seed mix cluster (`0.024 m` cluster of sunflower seeds, golden millet, kibble pellet, corn kernel) with paw pickup pivot (`< 800` tris). |
| **2. Sunflower seed** (`food_sunflower_seed`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build striped black-and-white striped Syrian hamster sunflower seed (`0.011 m × 0.005 m × 0.003 m`) with paw pickup pivot (`< 250` tris). |
| **3. Peanut** (`food_peanut`) | **MISSING** in `assets/raw/` (`kenney_food-kit` only has a `peanut-butter` jar, which is unsafe) | **GENERATE in Step 3**: Build natural double-lobed unsalted peanut in shell/half-shell (`0.022 m × 0.009 m × 0.009 m`) with textured hull & paw pickup pivot (`< 400` tris). |
| **4. Carrot piece** (`food_carrot_piece`) | **PARTIAL (`DOWNLOADED` whole carrot)** in `kenney_food-kit` (`carrot.glb`, `184` tris, `0.068 × 0.068 × 0.193 m` human scale) | **ADAPT & GENERATE in Step 3**: Rescale/slice Kenney CC0 carrot & build a bite-sized diced/coin carrot piece (`0.014 m`) with paw pickup pivot (`< 300` tris). |
| **5. Broccoli floret** (`food_broccoli_floret`) | **PRESENT (`DOWNLOADED`)** in `kenney_food-kit` (`broccoli.glb`, `332` tris, `0.159 × 0.157 × 0.165 m` human scale) | **ADAPT in Step 3/4**: Rescale to hamster floret size (`0.018 m`), set origin to stem pickup pivot, bake/verify PBR material (`< 400` tris). |
| **6. Apple piece** (`food_apple_piece`) | **PARTIAL (`DOWNLOADED` whole/half apple)** in `kenney_food-kit` (`apple.glb` `220` tris, `apple-half.glb` `168` tris, ~`0.14 m` human scale with seeds visible) | **GENERATE in Step 3**: Build a seedless fresh apple wedge/cube piece (`0.015 m`, cream flesh + red skin, zero toxic seeds) with paw pickup pivot (`< 300` tris). |
| **7. Blueberry** (`food_blueberry`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build low-poly blueberry (`0.010 m` diameter) with star calyx crown, dusty indigo bloom PBR shader, and center pickup pivot (`< 350` tris). |

### 4.2 Water Shelf & Food Shelf Containers
| Required Item | Audit Status in `assets/raw/` | Action for Step 3 (Blender Generation / Adaptation) |
| :--- | :--- | :--- |
| **1. Water bottle with visible level** (`water_bottle`) | **MISSING** in `assets/raw/` (`kenney` has condiment bottles; `KayKit` has opaque potion bottles; `blender/scripts/10_cage.py` has wall-mounted bottle without separate inner liquid mesh) | **GENERATE in Step 3**: Build hamster-scale `0.15 m` clear water bottle with a **separate named mesh `water_liquid`** (so the water level `0..1` scales smoothly along Y/Z), blue cap, wall bracket, and `45°` stainless-steel ball-valve spout (`< 1,200` tris). |
| **2. Small water bowl** (`water_bowl`) | **MISSING** as water-level bowl in `assets/raw/` | **GENERATE in Step 3**: Build small glazed ceramic water dish (`0.065 m` diameter, `0.026 m` height) with a **separate named mesh `water_liquid`** inside for dynamic water level scaling (`< 800` tris). |
| **3. Food bowl** (`prop_food_bowl`) | **PRESENT (`DOWNLOADED` + `GENERATED`)** (`kenney_food-kit/bowl.glb` `192` tris at `0.28 m`; `10_cage.py` `prop_bowl` at `0.084 m`) | **ADAPT & EXPORT in Step 3/4**: Export both the clean hamster-scale ceramic food bowl (`0.08 m` diameter, base-center pivot) and rescaled Kenney bowl (`< 800` tris). |
| **4. Shelf (for food-selection UI / cage shelf)** (`prop_shelf`) | **PRESENT (`DOWNLOADED`)** in `KayKit_Dungeon_Pack_1.1_FREE` (`shelf_small.gltf` `76` tris, `shelves.gltf` `596` tris, dungeon scale `2.1 × 0.8 × 2.1 m`) | **ADAPT in Step 3/4**: Rescale KayKit CC0 wooden shelf to hamster cage platform/shelf scale (`0.22 m × 0.12 m × 0.14 m`), base-center pivot, clean UVs (`< 600` tris). |

### 4.3 Costume Shelf (`head_slot`, `neck_slot`, `back_slot`)
*(Zero costumes exist in `assets/raw/`. Every costume is a **100% GAP** and must be generated in Step 3 at Syrian hamster scale (~15 cm body, ~3.8 cm head width) with named attachment sockets `head_slot`, `neck_slot`, `back_slot` matching `HamsterRig` bones `head`, `neck`, `spine_2`)*:

| Required Costume | Attachment Slot | Target Hamster Dimensions | Status & Action for Step 3 |
| :--- | :---: | :---: | :--- |
| **1. Party hat** (`costume_party_hat`) | `head_slot` | `0.026 m` base diam × `0.036 m` cone height + pom-pom | **MISSING → GENERATE in Step 3** (`< 600` tris, origin at `head_slot` attachment point between ears) |
| **2. Top hat** (`costume_top_hat`) | `head_slot` | `0.032 m` brim diam × `0.028 m` crown height + satin band | **MISSING → GENERATE in Step 3** (`< 700` tris, origin at `head_slot`) |
| **3. Bow tie** (`costume_bow_tie`) | `neck_slot` | `0.028 m` width × `0.014 m` height × `0.008 m` depth | **MISSING → GENERATE in Step 3** (`< 500` tris, origin at `neck_slot` under chin/chest) |
| **4. Scarf** (`costume_scarf`) | `neck_slot` | `0.044 m` collar ring diameter + draped knit tail | **MISSING → GENERATE in Step 3** (`< 900` tris, origin at `neck_slot`) |
| **5. Crown** (`costume_crown`) | `head_slot` | `0.026 m` diameter × `0.018 m` height, 5 jewel points | **MISSING → GENERATE in Step 3** (`< 800` tris, gold PBR + gem accents, origin at `head_slot`) |
| **6. Tiny glasses** (`costume_tiny_glasses`) | `head_slot` | `0.034 m` frame width, twin round wire rims + temples | **MISSING → GENERATE in Step 3** (`< 800` tris, origin at `head_slot` aligned with `ham_eye_L/R`) |
| **7. Royal cape / mini backpack** (`costume_cape_back`) | `back_slot` | `0.055 m` length × `0.042 m` width draped over `spine_2` | **MISSING → GENERATE in Step 3** (Ensures all 3 required slots `head_slot`, `neck_slot`, `back_slot` have dedicated testable items; `< 700` tris) |

### 4.4 Props Shelf
| Required Prop | Audit Status in `assets/raw/` & `blender/` | Action for Step 3 (Blender Generation / Export) |
| :--- | :--- | :--- |
| **1. Wheel** (`prop_wheel`) | **MISSING** in `assets/raw/`; **PRESENT** in `blender/scripts/10_cage.py` (`0.28 m` diameter wheel on stand) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export clean standalone `prop_wheel.glb` (`0.28 m` diameter, solid running surface + grip rungs, base-center pivot, `< 3,500` tris). |
| **2. Tunnel — Straight** (`prop_tunnel_straight`) | **MISSING** in `assets/raw/`; **PRESENT** in `10_cage.py` (`0.14 m` length, `0.072 m` diameter) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export standalone hollow bark/cork straight tunnel (`0.16 m` long, `0.072 m` inner diam, base-center pivot, `< 1,200` tris). |
| **3. Tunnel — Curved** (`prop_tunnel_curved`) | **MISSING** in `assets/raw/`; **PRESENT** in `10_cage.py` (`90°` elbow tunnel) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export standalone `90°` curved hollow tunnel (`0.08 m` bend radius, `0.072 m` diam, base-center pivot, `< 1,500` tris). |
| **4. Hideout** (`prop_hideout`) | **MISSING** in `assets/raw/`; **PRESENT** in `10_cage.py` (`0.16 × 0.13 × 0.105 m` arched cabin) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export standalone wooden hideout with arched doorway & overhanging roof (`< 1,500` tris, base-center pivot). |
| **5. Bridge / Ramp** (`prop_bridge_ramp`) | **MISSING** in `assets/raw/` (`KayKit` only has heavy stone dungeon stairs) | **GENERATE in Step 3**: Build arched bendy wooden log bridge / climbing ramp (`0.18 m` length × `0.09 m` width × `0.055 m` arch height, 11 tied wooden dowel logs, base-center pivot, `< 1,600` tris). |
| **6. Chew toy** (`prop_chew_toy`) | **MISSING** in `assets/raw/`; basic stick/block in `20_clutter.py` | **GENERATE in Step 3**: Build composite applewood dumbell/block chew toy (`0.075 m` length × `0.028 m` diam, natural bark + gnawed wood notches, base-center pivot, `< 1,000` tris). |
| **7. Small ball** (`prop_small_ball`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build woven willow/rattan play ball (`0.045 m` diameter, natural wicker bands, base-center pivot, `< 1,200` tris). |

### 4.5 Decor Shelf
| Required Decor | Audit Status in `assets/raw/` | Action for Step 3 (Blender Generation / Adaptation) |
| :--- | :--- | :--- |
| **1. Plants** (`decor_plant`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build hamster-safe spider-plant / millet-spray terracotta pot (`0.075 m` height, terracotta base + arching green leaves, base-center pivot, `< 1,200` tris). |
| **2. Small wooden items** (`decor_wooden_item`) | **PARTIAL (`DOWNLOADED`)** in `KayKit_Dungeon_Pack_1.1_FREE` (`barrel_small.gltf` `332` tris, `box_small.gltf` `172` tris, `stool.gltf` `116` tris at dungeon scale) | **ADAPT & GENERATE in Step 3**: Rescale KayKit CC0 wooden barrel/crate to hamster scale (`0.055 m`) AND generate a natural birch log stepping stool (`0.06 m × 0.06 m × 0.045 m`, `< 800` tris). |
| **3. Bedding patches** (`decor_bedding_patch`) | **MISSING** in `assets/raw/` (`KayKit` `floor_dirt_small_A` is dungeon dirt/stone) | **GENERATE in Step 3**: Build soft mounded paper/aspen/moss bedding patch (`0.14 m × 0.12 m × 0.022 m`, organic feathered rim, base-center pivot, `< 1,000` tris). |
| **4. Flag** (`decor_flag`) | **PRESENT (`DOWNLOADED`)** in `KayKit_Dungeon_Pack_1.1_FREE` (`banner_blue.gltf`, `banner_red.gltf` `310` tris, `2.6 m` tall) + **GENERATE** | **ADAPT & GENERATE in Step 3**: Rescale KayKit CC0 banner to mini cage corner flag (`0.11 m` tall on wooden dowel post) AND generate a cute HAMMY pennant flag (`0.10 m` tall, `< 600` tris). |
| **5. Picture frame** (`decor_picture_frame`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build miniature wooden tabletop/wall picture frame (`0.075 m × 0.060 m × 0.012 m`) with easel stand and warm hamster portrait canvas (`< 600` tris). |

---

## 5. Complete Per-File Audit Table (`524` Unique 3D Models + `255` Texture Files)

### 5.1 Pack: `kenney_food-kit.zip` (`200` unique models)

| Asset ID | Name | Formats | Primary File Size (B) | Total Pack Bytes | Verts | Polys | Tris | Scale `(X, Y, Z)` m | Category | Hamster Safe | Licence & Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `kenney_advocado_half` | `advocado-half` | `.glb, .fbx, .obj/.mtl` | `11,240` | `54,876` | `64` | `152` | `152` | `0.104×0.214×0.173` | `food` | `NO` | APPROVED (CC0) |
| `kenney_apple_half` | `apple-half` | `.glb, .fbx, .obj/.mtl` | `10,948` | `51,217` | `73` | `248` | `248` | `0.098×0.191×0.196` | `food` | `YES` | APPROVED (CC0) |
| `kenney_apple` | `apple` | `.glb, .fbx, .obj/.mtl` | `14,376` | `58,276` | `71` | `272` | `272` | `0.196×0.191×0.196` | `food` | `YES` | APPROVED (CC0) |
| `kenney_avocado` | `avocado` | `.glb, .fbx, .obj/.mtl` | `6,076` | `37,467` | `24` | `88` | `88` | `0.150×0.214×0.173` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bacon_raw` | `bacon-raw` | `.glb, .fbx, .obj/.mtl` | `5,708` | `36,882` | `30` | `80` | `80` | `0.130×0.030×0.520` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bacon` | `bacon` | `.glb, .fbx, .obj/.mtl` | `5,696` | `36,832` | `30` | `80` | `80` | `0.130×0.030×0.520` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bag_flat` | `bag-flat` | `.glb, .fbx, .obj/.mtl` | `11,280` | `49,276` | `59` | `228` | `228` | `0.650×0.191×0.468` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_bag` | `bag` | `.glb, .fbx, .obj/.mtl` | `6,408` | `38,136` | `24` | `92` | `92` | `0.220×0.600×0.412` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_banana` | `banana` | `.glb, .fbx, .obj/.mtl` | `12,348` | `55,109` | `54` | `208` | `208` | `0.138×0.196×0.630` | `food` | `YES` | APPROVED (CC0) |
| `kenney_barrel` | `barrel` | `.glb, .fbx, .obj/.mtl` | `26,812` | `81,518` | `156` | `616` | `616` | `0.760×0.679×0.679` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_beet` | `beet` | `.glb, .fbx, .obj/.mtl` | `10,372` | `47,162` | `56` | `200` | `200` | `0.098×0.265×0.098` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bottle_ketchup` | `bottle-ketchup` | `.glb, .fbx, .obj/.mtl` | `9,620` | `43,366` | `50` | `192` | `192` | `0.144×0.393×0.166` | `other` | `NO` | APPROVED (CC0) |
| `kenney_bottle_musterd` | `bottle-musterd` | `.glb, .fbx, .obj/.mtl` | `9,620` | `43,366` | `50` | `192` | `192` | `0.144×0.393×0.166` | `other` | `NO` | APPROVED (CC0) |
| `kenney_bottle_oil` | `bottle-oil` | `.glb, .fbx, .obj/.mtl` | `10,500` | `45,621` | `56` | `192` | `192` | `0.140×0.622×0.140` | `other` | `NO` | APPROVED (CC0) |
| `kenney_bowl_broth` | `bowl-broth` | `.glb, .fbx, .obj/.mtl` | `16,628` | `74,221` | `148` | `404` | `404` | `0.526×0.290×0.580` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bowl_cereal` | `bowl-cereal` | `.glb, .fbx, .obj/.mtl` | `12,468` | `53,073` | `77` | `240` | `240` | `0.502×0.419×0.635` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bowl_soup` | `bowl-soup` | `.glb, .fbx, .obj/.mtl` | `11,188` | `52,108` | `96` | `264` | `264` | `0.502×0.214×0.580` | `food` | `NO` | APPROVED (CC0) |
| `kenney_bowl` | `bowl` | `.glb, .fbx, .obj/.mtl` | `6,340` | `41,130` | `42` | `168` | `168` | `0.502×0.214×0.580` | `prop` | `N/A` | APPROVED (CC0) |
| `kenney_bread` | `bread` | `.glb, .fbx, .obj/.mtl` | `9,468` | `45,361` | `77` | `232` | `232` | `0.442×0.040×0.366` | `food` | `NO` | APPROVED (CC0) |
| `kenney_broccoli` | `broccoli` | `.glb, .fbx, .obj/.mtl` | `20,452` | `78,850` | `125` | `440` | `440` | `0.375×0.422×0.375` | `food` | `YES` | APPROVED (CC0) |
| `kenney_burger_cheese_double` | `burger-cheese-double` | `.glb, .fbx, .obj/.mtl` | `44,420` | `134,880` | `126` | `392` | `392` | `0.378×0.320×0.378` | `food` | `NO` | APPROVED (CC0) |
| `kenney_burger_cheese` | `burger-cheese` | `.glb, .fbx, .obj/.mtl` | `25,900` | `87,287` | `78` | `226` | `226` | `0.378×0.220×0.378` | `food` | `NO` | APPROVED (CC0) |
| `kenney_burger_double` | `burger-double` | `.glb, .fbx, .obj/.mtl` | `55,692` | `173,885` | `186` | `468` | `468` | `0.404×0.360×0.404` | `food` | `NO` | APPROVED (CC0) |
| `kenney_burger` | `burger` | `.glb, .fbx, .obj/.mtl` | `34,536` | `115,335` | `125` | `294` | `294` | `0.404×0.290×0.404` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cabbage` | `cabbage` | `.glb, .fbx, .obj/.mtl` | `15,360` | `59,666` | `74` | `280` | `280` | `0.380×0.307×0.404` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cake_birthday` | `cake-birthday` | `.glb, .fbx, .obj/.mtl` | `115,324` | `297,960` | `842` | `1146` | `1146` | `0.639×0.364×0.639` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cake_slicer` | `cake-slicer` | `.glb, .fbx, .obj/.mtl` | `5,060` | `36,389` | `22` | `72` | `72` | `0.725×0.069×0.190` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cake` | `cake` | `.glb, .fbx, .obj/.mtl` | `72,884` | `223,204` | `566` | `750` | `750` | `0.639×0.273×0.639` | `food` | `NO` | APPROVED (CC0) |
| `kenney_can_open` | `can-open` | `.glb, .fbx, .obj/.mtl` | `18,428` | `65,762` | `107` | `432` | `432` | `0.300×0.407×0.300` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_can_small` | `can-small` | `.glb, .fbx, .obj/.mtl` | `15,964` | `62,804` | `79` | `278` | `278` | `0.300×0.161×0.300` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_can` | `can` | `.glb, .fbx, .obj/.mtl` | `13,708` | `51,930` | `80` | `312` | `312` | `0.300×0.320×0.300` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_candy_bar_wrapper` | `candy-bar-wrapper` | `.glb, .fbx, .obj/.mtl` | `6,120` | `36,213` | `24` | `96` | `96` | `0.292×0.081×0.117` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_candy_bar` | `candy-bar` | `.glb, .fbx, .obj/.mtl` | `7,504` | `40,348` | `38` | `144` | `144` | `0.292×0.065×0.074` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_carrot` | `carrot` | `.glb, .fbx, .obj/.mtl` | `16,364` | `59,822` | `78` | `296` | `296` | `0.343×0.716×0.343` | `food` | `YES` | APPROVED (CC0) |
| `kenney_carton_small` | `carton-small` | `.glb, .fbx, .obj/.mtl` | `8,352` | `41,877` | `46` | `148` | `148` | `0.230×0.391×0.230` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_carton` | `carton` | `.glb, .fbx, .obj/.mtl` | `9,352` | `43,598` | `58` | `188` | `188` | `0.230×0.591×0.230` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cauliflower` | `cauliflower` | `.glb, .fbx, .obj/.mtl` | `16,592` | `62,798` | `80` | `304` | `304` | `0.380×0.307×0.404` | `food` | `YES` | APPROVED (CC0) |
| `kenney_celery_stick` | `celery-stick` | `.glb, .fbx, .obj/.mtl` | `5,964` | `36,410` | `28` | `104` | `104` | `0.046×0.540×0.088` | `food` | `YES` | APPROVED (CC0) |
| `kenney_cheese_cut` | `cheese-cut` | `.glb, .fbx, .obj/.mtl` | `13,456` | `52,034` | `78` | `320` | `320` | `0.384×0.021×0.264` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cheese_slicer` | `cheese-slicer` | `.glb, .fbx, .obj/.mtl` | `5,496` | `35,787` | `24` | `88` | `88` | `0.618×0.029×0.192` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cheese` | `cheese` | `.glb, .fbx, .obj/.mtl` | `60,976` | `207,541` | `432` | `576` | `576` | `0.680×0.220×0.680` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cherries` | `cherries` | `.glb, .fbx, .obj/.mtl` | `13,516` | `54,736` | `69` | `268` | `268` | `0.088×0.171×0.162` | `food` | `NO` | APPROVED (CC0) |
| `kenney_chinese` | `chinese` | `.glb, .fbx, .obj/.mtl` | `19,384` | `79,118` | `72` | `300` | `300` | `0.454×0.567×0.557` | `food` | `NO` | APPROVED (CC0) |
| `kenney_chocolate_wrapper` | `chocolate-wrapper` | `.glb, .fbx, .obj/.mtl` | `11,720` | `48,513` | `68` | `236` | `236` | `0.292×0.065×0.202` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_chocolate` | `chocolate` | `.glb, .fbx, .obj/.mtl` | `12,652` | `50,077` | `72` | `280` | `280` | `0.292×0.034×0.146` | `food` | `NO` | APPROVED (CC0) |
| `kenney_chopstic_decorative` | `chopstic-decorative` | `.glb, .fbx, .obj/.mtl` | `5,416` | `36,850` | `26` | `72` | `72` | `0.020×0.020×0.450` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_chopstick` | `chopstick` | `.glb, .fbx, .obj/.mtl` | `3,008` | `31,653` | `8` | `24` | `24` | `0.020×0.020×0.450` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cocktail` | `cocktail` | `.glb, .fbx, .obj/.mtl` | `14,128` | `67,428` | `86` | `232` | `232` | `0.261×0.506×0.361` | `food` | `NO` | APPROVED (CC0) |
| `kenney_coconut_half` | `coconut-half` | `.glb, .fbx, .obj/.mtl` | `8,308` | `43,376` | `56` | `184` | `184` | `0.248×0.124×0.248` | `food` | `NO` | APPROVED (CC0) |
| `kenney_coconut` | `coconut` | `.glb, .fbx, .obj/.mtl` | `8,984` | `45,224` | `40` | `152` | `152` | `0.248×0.248×0.248` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cookie_chocolate` | `cookie-chocolate` | `.glb, .fbx, .obj/.mtl` | `12,344` | `53,378` | `78` | `272` | `272` | `0.121×0.065×0.140` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cookie` | `cookie` | `.glb, .fbx, .obj/.mtl` | `7,532` | `41,774` | `42` | `136` | `136` | `0.220×0.050×0.190` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cooking_fork` | `cooking-fork` | `.glb, .fbx, .obj/.mtl` | `4,872` | `36,982` | `22` | `72` | `72` | `0.683×0.072×0.075` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cooking_knife_chopping` | `cooking-knife-chopping` | `.glb, .fbx, .obj/.mtl` | `7,796` | `41,577` | `42` | `160` | `160` | `0.600×0.040×0.223` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cooking_knife` | `cooking-knife` | `.glb, .fbx, .obj/.mtl` | `5,380` | `37,066` | `23` | `78` | `78` | `0.716×0.040×0.133` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cooking_spatula` | `cooking-spatula` | `.glb, .fbx, .obj/.mtl` | `6,144` | `38,688` | `34` | `144` | `144` | `0.683×0.072×0.190` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cooking_spoon` | `cooking-spoon` | `.glb, .fbx, .obj/.mtl` | `6,796` | `39,285` | `22` | `112` | `112` | `0.666×0.024×0.173` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_corn_dog` | `corn-dog` | `.glb, .fbx, .obj/.mtl` | `9,152` | `47,912` | `36` | `84` | `84` | `0.604×0.094×0.108` | `food` | `NO` | APPROVED (CC0) |
| `kenney_corn` | `corn` | `.glb, .fbx, .obj/.mtl` | `14,284` | `56,893` | `66` | `256` | `256` | `0.343×0.316×0.300` | `food` | `YES` | APPROVED (CC0) |
| `kenney_croissant` | `croissant` | `.glb, .fbx, .obj/.mtl` | `14,352` | `61,989` | `83` | `324` | `324` | `0.346×0.194×0.478` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cup_coffee` | `cup-coffee` | `.glb, .fbx, .obj/.mtl` | `7,872` | `43,971` | `60` | `216` | `216` | `0.216×0.140×0.287` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cup_saucer` | `cup-saucer` | `.glb, .fbx, .obj/.mtl` | `7,848` | `43,046` | `60` | `232` | `232` | `0.357×0.038×0.357` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cup_tea` | `cup-tea` | `.glb, .fbx, .obj/.mtl` | `9,780` | `49,656` | `88` | `288` | `288` | `0.237×0.200×0.292` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cup` | `cup` | `.glb, .fbx, .obj/.mtl` | `8,008` | `43,577` | `62` | `224` | `224` | `0.230×0.200×0.292` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cupcake` | `cupcake` | `.glb, .fbx, .obj/.mtl` | `22,724` | `81,485` | `118` | `296` | `296` | `0.355×0.424×0.308` | `food` | `NO` | APPROVED (CC0) |
| `kenney_cutting_board_japanese` | `cutting-board-japanese` | `.glb, .fbx, .obj/.mtl` | `9,864` | `42,606` | `54` | `208` | `208` | `0.490×0.080×0.840` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cutting_board_round` | `cutting-board-round` | `.glb, .fbx, .obj/.mtl` | `12,608` | `51,875` | `80` | `312` | `312` | `0.800×0.060×0.800` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_cutting_board` | `cutting-board` | `.glb, .fbx, .obj/.mtl` | `10,652` | `45,964` | `62` | `240` | `240` | `0.580×0.060×0.820` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_dim_sum` | `dim-sum` | `.glb, .fbx, .obj/.mtl` | `7,180` | `39,332` | `30` | `112` | `112` | `0.161×0.120×0.186` | `food` | `NO` | APPROVED (CC0) |
| `kenney_donut_chocolate` | `donut-chocolate` | `.glb, .fbx, .obj/.mtl` | `12,568` | `54,698` | `68` | `240` | `240` | `0.245×0.089×0.283` | `food` | `NO` | APPROVED (CC0) |
| `kenney_donut_sprinkles` | `donut-sprinkles` | `.glb, .fbx, .obj/.mtl` | `20,008` | `72,671` | `128` | `360` | `360` | `0.245×0.095×0.283` | `food` | `NO` | APPROVED (CC0) |
| `kenney_donut` | `donut` | `.glb, .fbx, .obj/.mtl` | `11,360` | `50,263` | `54` | `216` | `216` | `0.245×0.089×0.283` | `food` | `NO` | APPROVED (CC0) |
| `kenney_egg_cooked` | `egg-cooked` | `.glb, .fbx, .obj/.mtl` | `6,752` | `41,711` | `48` | `184` | `184` | `0.414×0.028×0.382` | `food` | `NO` | APPROVED (CC0) |
| `kenney_egg_cup` | `egg-cup` | `.glb, .fbx, .obj/.mtl` | `6,992` | `41,872` | `42` | `168` | `168` | `0.158×0.150×0.183` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_egg_half` | `egg-half` | `.glb, .fbx, .obj/.mtl` | `8,256` | `42,993` | `36` | `160` | `160` | `0.116×0.106×0.134` | `food` | `NO` | APPROVED (CC0) |
| `kenney_egg` | `egg` | `.glb, .fbx, .obj/.mtl` | `6,044` | `37,092` | `24` | `88` | `88` | `0.116×0.165×0.134` | `food` | `NO` | APPROVED (CC0) |
| `kenney_eggplant` | `eggplant` | `.glb, .fbx, .obj/.mtl` | `13,416` | `58,670` | `79` | `248` | `248` | `0.204×0.405×0.216` | `food` | `NO` | APPROVED (CC0) |
| `kenney_fish_bones` | `fish-bones` | `.glb, .fbx, .obj/.mtl` | `34,068` | `109,159` | `194` | `768` | `768` | `0.311×0.073×0.636` | `food` | `NO` | APPROVED (CC0) |
| `kenney_fish` | `fish` | `.glb, .fbx, .obj/.mtl` | `31,672` | `107,513` | `147` | `466` | `466` | `0.198×0.322×0.621` | `food` | `NO` | APPROVED (CC0) |
| `kenney_frappe` | `frappe` | `.glb, .fbx, .obj/.mtl` | `22,548` | `87,090` | `168` | `640` | `640` | `0.254×0.499×0.254` | `food` | `NO` | APPROVED (CC0) |
| `kenney_fries_empty` | `fries-empty` | `.glb, .fbx, .obj/.mtl` | `11,376` | `48,142` | `52` | `232` | `232` | `0.164×0.236×0.265` | `food` | `NO` | APPROVED (CC0) |
| `kenney_fries` | `fries` | `.glb, .fbx, .obj/.mtl` | `59,228` | `143,302` | `228` | `648` | `648` | `0.183×0.398×0.265` | `food` | `NO` | APPROVED (CC0) |
| `kenney_frikandel_speciaal` | `frikandel-speciaal` | `.glb, .fbx, .obj/.mtl` | `25,532` | `89,735` | `192` | `394` | `394` | `0.636×0.109×0.166` | `food` | `NO` | APPROVED (CC0) |
| `kenney_frying_pan_lid` | `frying-pan-lid` | `.glb, .fbx, .obj/.mtl` | `13,856` | `60,404` | `72` | `296` | `296` | `0.577×0.108×0.606` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_frying_pan` | `frying-pan` | `.glb, .fbx, .obj/.mtl` | `19,216` | `67,219` | `102` | `400` | `400` | `0.657×0.121×1.022` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_ginger_bread_cutter` | `ginger-bread-cutter` | `.glb, .fbx, .obj/.mtl` | `11,972` | `48,153` | `51` | `272` | `272` | `0.292×0.042×0.269` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_ginger_bread` | `ginger-bread` | `.glb, .fbx, .obj/.mtl` | `7,756` | `41,910` | `46` | `160` | `160` | `0.260×0.030×0.236` | `food` | `NO` | APPROVED (CC0) |
| `kenney_glass_wine` | `glass-wine` | `.glb, .fbx, .obj/.mtl` | `23,984` | `74,690` | `60` | `464` | `464` | `0.227×0.500×0.197` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_glass` | `glass` | `.glb, .fbx, .obj/.mtl` | `4,216` | `34,098` | `24` | `88` | `88` | `0.160×0.285×0.184` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_grapes` | `grapes` | `.glb, .fbx, .obj/.mtl` | `58,992` | `168,439` | `350` | `1184` | `1184` | `0.279×0.423×0.239` | `food` | `NO` | APPROVED (CC0) |
| `kenney_honey` | `honey` | `.glb, .fbx, .obj/.mtl` | `14,888` | `56,556` | `72` | `280` | `280` | `0.326×0.316×0.326` | `food` | `NO` | APPROVED (CC0) |
| `kenney_hot_dog_raw` | `hot-dog-raw` | `.glb, .fbx, .obj/.mtl` | `9,568` | `44,632` | `48` | `184` | `184` | `0.586×0.097×0.112` | `food` | `NO` | APPROVED (CC0) |
| `kenney_hot_dog` | `hot-dog` | `.glb, .fbx, .obj/.mtl` | `27,700` | `94,410` | `155` | `354` | `354` | `0.586×0.152×0.203` | `food` | `NO` | APPROVED (CC0) |
| `kenney_ice_cream_cne` | `ice-cream-cne` | `.glb, .fbx, .obj/.mtl` | `5,460` | `35,243` | `24` | `88` | `88` | `0.184×0.298×0.213` | `food` | `NO` | APPROVED (CC0) |
| `kenney_ice_cream_cup` | `ice-cream-cup` | `.glb, .fbx, .obj/.mtl` | `7,796` | `40,992` | `36` | `136` | `136` | `0.201×0.180×0.232` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_ice_cream_scoop_chocolate` | `ice-cream-scoop-chocolate` | `.glb, .fbx, .obj/.mtl` | `9,016` | `46,836` | `42` | `160` | `160` | `0.235×0.165×0.272` | `food` | `NO` | APPROVED (CC0) |
| `kenney_ice_cream_scoop_mint` | `ice-cream-scoop-mint` | `.glb, .fbx, .obj/.mtl` | `7,256` | `40,529` | `30` | `112` | `112` | `0.235×0.165×0.272` | `food` | `NO` | APPROVED (CC0) |
| `kenney_ice_cream` | `ice-cream` | `.glb, .fbx, .obj/.mtl` | `10,124` | `50,982` | `44` | `96` | `96` | `0.235×0.463×0.272` | `food` | `NO` | APPROVED (CC0) |
| `kenney_knife_block` | `knife-block` | `.glb, .fbx, .obj/.mtl` | `20,204` | `85,925` | `91` | `197` | `197` | `0.636×0.662×0.222` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_leek` | `leek` | `.glb, .fbx, .obj/.mtl` | `16,648` | `63,440` | `88` | `344` | `344` | `0.273×0.847×0.273` | `food` | `NO` | APPROVED (CC0) |
| `kenney_lemon_half` | `lemon-half` | `.glb, .fbx, .obj/.mtl` | `10,280` | `47,469` | `60` | `232` | `232` | `0.173×0.112×0.200` | `food` | `NO` | APPROVED (CC0) |
| `kenney_lemon` | `lemon` | `.glb, .fbx, .obj/.mtl` | `11,924` | `50,509` | `54` | `208` | `208` | `0.173×0.224×0.200` | `food` | `NO` | APPROVED (CC0) |
| `kenney_loaf_baguette` | `loaf-baguette` | `.glb, .fbx, .obj/.mtl` | `12,824` | `53,445` | `63` | `244` | `244` | `0.830×0.250×0.250` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_loaf_round` | `loaf-round` | `.glb, .fbx, .obj/.mtl` | `11,112` | `50,243` | `60` | `232` | `232` | `0.772×0.293×0.514` | `food` | `NO` | APPROVED (CC0) |
| `kenney_loaf` | `loaf` | `.glb, .fbx, .obj/.mtl` | `9,464` | `45,369` | `64` | `232` | `232` | `0.580×0.442×0.366` | `food` | `NO` | APPROVED (CC0) |
| `kenney_lollypop` | `lollypop` | `.glb, .fbx, .obj/.mtl` | `8,544` | `44,076` | `68` | `216` | `216` | `0.038×0.380×0.188` | `food` | `NO` | APPROVED (CC0) |
| `kenney_maki_roe` | `maki-roe` | `.glb, .fbx, .obj/.mtl` | `6,568` | `38,471` | `30` | `112` | `112` | `0.120×0.090×0.104` | `food` | `NO` | APPROVED (CC0) |
| `kenney_maki_salmon` | `maki-salmon` | `.glb, .fbx, .obj/.mtl` | `6,004` | `36,708` | `30` | `112` | `112` | `0.120×0.070×0.104` | `food` | `NO` | APPROVED (CC0) |
| `kenney_maki_vegetable` | `maki-vegetable` | `.glb, .fbx, .obj/.mtl` | `6,108` | `37,221` | `32` | `112` | `112` | `0.120×0.070×0.104` | `food` | `NO` | APPROVED (CC0) |
| `kenney_meat_cooked` | `meat-cooked` | `.glb, .fbx, .obj/.mtl` | `10,540` | `49,226` | `74` | `232` | `232` | `0.478×0.065×0.575` | `food` | `NO` | APPROVED (CC0) |
| `kenney_meat_patty` | `meat-patty` | `.glb, .fbx, .obj/.mtl` | `9,092` | `44,723` | `54` | `208` | `208` | `0.299×0.062×0.345` | `food` | `NO` | APPROVED (CC0) |
| `kenney_meat_raw` | `meat-raw` | `.glb, .fbx, .obj/.mtl` | `9,936` | `47,522` | `62` | `220` | `220` | `0.478×0.065×0.575` | `food` | `NO` | APPROVED (CC0) |
| `kenney_meat_ribs` | `meat-ribs` | `.glb, .fbx, .obj/.mtl` | `14,364` | `56,802` | `84` | `328` | `328` | `0.535×0.060×0.383` | `food` | `NO` | APPROVED (CC0) |
| `kenney_meat_sausage` | `meat-sausage` | `.glb, .fbx, .obj/.mtl` | `47,096` | `131,630` | `162` | `640` | `640` | `0.151×0.073×0.392` | `food` | `NO` | APPROVED (CC0) |
| `kenney_meat_tenderizer` | `meat-tenderizer` | `.glb, .fbx, .obj/.mtl` | `31,372` | `92,367` | `168` | `644` | `644` | `0.541×0.118×0.276` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_mincemeat_pie` | `mincemeat-pie` | `.glb, .fbx, .obj/.mtl` | `12,700` | `55,740` | `84` | `328` | `328` | `0.531×0.167×0.613` | `food` | `NO` | APPROVED (CC0) |
| `kenney_mortar_pestle` | `mortar-pestle` | `.glb, .fbx, .obj/.mtl` | `7,232` | `39,977` | `30` | `112` | `112` | `0.114×0.340×0.132` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_mortar` | `mortar` | `.glb, .fbx, .obj/.mtl` | `10,200` | `46,218` | `48` | `184` | `184` | `0.396×0.210×0.457` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_muffin` | `muffin` | `.glb, .fbx, .obj/.mtl` | `10,252` | `47,608` | `44` | `168` | `168` | `0.305×0.249×0.264` | `food` | `NO` | APPROVED (CC0) |
| `kenney_mug` | `mug` | `.glb, .fbx, .obj/.mtl` | `20,236` | `67,061` | `116` | `464` | `464` | `0.344×0.273×0.285` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_mushroom_half` | `mushroom-half` | `.glb, .fbx, .obj/.mtl` | `7,024` | `39,997` | `36` | `136` | `136` | `0.062×0.139×0.144` | `food` | `NO` | APPROVED (CC0) |
| `kenney_mushroom` | `mushroom` | `.glb, .fbx, .obj/.mtl` | `8,440` | `43,631` | `42` | `160` | `160` | `0.125×0.139×0.144` | `food` | `NO` | APPROVED (CC0) |
| `kenney_mussel_open` | `mussel-open` | `.glb, .fbx, .obj/.mtl` | `10,216` | `47,721` | `33` | `180` | `180` | `0.096×0.080×0.155` | `food` | `NO` | APPROVED (CC0) |
| `kenney_mussel` | `mussel` | `.glb, .fbx, .obj/.mtl` | `5,328` | `37,998` | `21` | `76` | `76` | `0.092×0.042×0.155` | `food` | `NO` | APPROVED (CC0) |
| `kenney_onion_half` | `onion-half` | `.glb, .fbx, .obj/.mtl` | `9,084` | `47,253` | `87` | `216` | `216` | `0.106×0.250×0.246` | `food` | `NO` | APPROVED (CC0) |
| `kenney_onion` | `onion` | `.glb, .fbx, .obj/.mtl` | `8,356` | `43,236` | `36` | `136` | `136` | `0.213×0.250×0.246` | `food` | `NO` | APPROVED (CC0) |
| `kenney_orange` | `orange` | `.glb, .fbx, .obj/.mtl` | `13,088` | `52,927` | `64` | `240` | `240` | `0.170×0.167×0.170` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pan_stew` | `pan-stew` | `.glb, .fbx, .obj/.mtl` | `28,316` | `94,037` | `201` | `688` | `688` | `0.657×0.175×0.762` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pan` | `pan` | `.glb, .fbx, .obj/.mtl` | `19,956` | `71,321` | `124` | `472` | `472` | `0.657×0.175×0.762` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_pancakes` | `pancakes` | `.glb, .fbx, .obj/.mtl` | `42,592` | `142,579` | `331` | `542` | `542` | `0.435×0.122×0.504` | `food` | `NO` | APPROVED (CC0) |
| `kenney_paprika_slice` | `paprika-slice` | `.glb, .fbx, .obj/.mtl` | `8,988` | `43,225` | `48` | `192` | `192` | `0.160×0.030×0.160` | `food` | `NO` | APPROVED (CC0) |
| `kenney_paprika` | `paprika` | `.glb, .fbx, .obj/.mtl` | `15,124` | `61,003` | `72` | `264` | `264` | `0.168×0.199×0.168` | `food` | `NO` | APPROVED (CC0) |
| `kenney_peanut_butter` | `peanut-butter` | `.glb, .fbx, .obj/.mtl` | `17,408` | `61,807` | `88` | `344` | `344` | `0.236×0.296×0.236` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pear_half` | `pear-half` | `.glb, .fbx, .obj/.mtl` | `11,336` | `51,897` | `73` | `252` | `252` | `0.098×0.271×0.196` | `food` | `YES` | APPROVED (CC0) |
| `kenney_pear` | `pear` | `.glb, .fbx, .obj/.mtl` | `15,556` | `59,904` | `71` | `272` | `272` | `0.196×0.271×0.196` | `food` | `YES` | APPROVED (CC0) |
| `kenney_pepper_mill` | `pepper-mill` | `.glb, .fbx, .obj/.mtl` | `25,664` | `86,475` | `128` | `504` | `504` | `0.158×0.548×0.158` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_pepper` | `pepper` | `.glb, .fbx, .obj/.mtl` | `12,928` | `52,890` | `52` | `200` | `200` | `0.104×0.077×0.319` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pie` | `pie` | `.glb, .fbx, .obj/.mtl` | `22,420` | `78,719` | `150` | `584` | `584` | `0.950×0.150×0.950` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pineapple` | `pineapple` | `.glb, .fbx, .obj/.mtl` | `20,248` | `71,262` | `96` | `392` | `392` | `0.241×0.472×0.245` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pizza_box` | `pizza-box` | `.glb, .fbx, .obj/.mtl` | `8,788` | `50,368` | `46` | `128` | `128` | `0.942×0.882×0.952` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_pizza_cutter` | `pizza-cutter` | `.glb, .fbx, .obj/.mtl` | `8,584` | `42,626` | `52` | `192` | `192` | `0.536×0.056×0.255` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_pizza` | `pizza` | `.glb, .fbx, .obj/.mtl` | `106,780` | `301,320` | `1026` | `1208` | `1208` | `0.842×0.043×0.842` | `food` | `NO` | APPROVED (CC0) |
| `kenney_plate_broken` | `plate-broken` | `.glb, .fbx, .obj/.mtl` | `33,220` | `137,618` | `157` | `336` | `336` | `0.892×0.090×0.892` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_plate_deep` | `plate-deep` | `.glb, .fbx, .obj/.mtl` | `7,944` | `47,198` | `72` | `280` | `280` | `0.892×0.145×0.892` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_plate_dinner` | `plate-dinner` | `.glb, .fbx, .obj/.mtl` | `27,908` | `98,916` | `208` | `708` | `708` | `0.892×0.221×0.892` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_plate_rectangle` | `plate-rectangle` | `.glb, .fbx, .obj/.mtl` | `6,756` | `38,354` | `28` | `136` | `136` | `0.859×0.130×0.719` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_plate_sauerkraut` | `plate-sauerkraut` | `.glb, .fbx, .obj/.mtl` | `64,728` | `183,795` | `310` | `1160` | `1160` | `0.892×0.175×0.892` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_plate` | `plate` | `.glb, .fbx, .obj/.mtl` | `8,480` | `47,454` | `72` | `280` | `280` | `0.892×0.090×0.892` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_popsicle_chocolate` | `popsicle-chocolate` | `.glb, .fbx, .obj/.mtl` | `11,796` | `50,446` | `84` | `264` | `264` | `0.095×0.490×0.200` | `food` | `NO` | APPROVED (CC0) |
| `kenney_popsicle_stick` | `popsicle-stick` | `.glb, .fbx, .obj/.mtl` | `4,768` | `36,328` | `20` | `72` | `72` | `0.020×0.340×0.040` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_popsicle` | `popsicle` | `.glb, .fbx, .obj/.mtl` | `8,116` | `41,085` | `44` | `156` | `156` | `0.075×0.490×0.180` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pot_lid` | `pot-lid` | `.glb, .fbx, .obj/.mtl` | `10,992` | `49,548` | `72` | `264` | `264` | `0.657×0.118×0.625` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_pot_stew_lid` | `pot-stew-lid` | `.glb, .fbx, .obj/.mtl` | `15,824` | `64,997` | `82` | `336` | `336` | `0.657×0.118×0.625` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pot_stew` | `pot-stew` | `.glb, .fbx, .obj/.mtl` | `29,560` | `96,131` | `222` | `740` | `740` | `0.657×0.361×0.822` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pot` | `pot` | `.glb, .fbx, .obj/.mtl` | `18,900` | `67,614` | `124` | `456` | `456` | `0.657×0.361×0.822` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_pudding` | `pudding` | `.glb, .fbx, .obj/.mtl` | `6,612` | `38,853` | `30` | `112` | `112` | `0.250×0.200×0.289` | `food` | `NO` | APPROVED (CC0) |
| `kenney_pumpkin_basic` | `pumpkin-basic` | `.glb, .fbx, .obj/.mtl` | `8,484` | `44,224` | `42` | `160` | `160` | `0.420×0.299×0.364` | `food` | `YES` | APPROVED (CC0) |
| `kenney_pumpkin` | `pumpkin` | `.glb, .fbx, .obj/.mtl` | `20,436` | `76,531` | `98` | `376` | `376` | `0.419×0.229×0.419` | `food` | `YES` | APPROVED (CC0) |
| `kenney_radish` | `radish` | `.glb, .fbx, .obj/.mtl` | `16,456` | `61,466` | `90` | `332` | `332` | `0.343×0.576×0.343` | `food` | `NO` | APPROVED (CC0) |
| `kenney_rice_ball` | `rice-ball` | `.glb, .fbx, .obj/.mtl` | `6,200` | `43,059` | `56` | `208` | `208` | `0.081×0.131×0.115` | `food` | `NO` | APPROVED (CC0) |
| `kenney_rollingPin` | `rollingPin` | `.glb, .fbx, .obj/.mtl` | `14,304` | `56,501` | `75` | `280` | `280` | `0.814×0.140×0.162` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_salad` | `salad` | `.glb, .fbx, .obj/.mtl` | `17,200` | `63,589` | `106` | `340` | `340` | `0.502×0.273×0.580` | `food` | `NO` | APPROVED (CC0) |
| `kenney_sandwich` | `sandwich` | `.glb, .fbx, .obj/.mtl` | `19,724` | `76,908` | `108` | `176` | `176` | `0.432×0.168×0.434` | `food` | `NO` | APPROVED (CC0) |
| `kenney_sausage_half` | `sausage-half` | `.glb, .fbx, .obj/.mtl` | `8,852` | `44,434` | `54` | `200` | `200` | `0.185×0.119×0.137` | `food` | `NO` | APPROVED (CC0) |
| `kenney_sausage` | `sausage` | `.glb, .fbx, .obj/.mtl` | `9,556` | `44,802` | `48` | `184` | `184` | `0.371×0.119×0.137` | `food` | `NO` | APPROVED (CC0) |
| `kenney_shaker_pepper` | `shaker-pepper` | `.glb, .fbx, .obj/.mtl` | `9,300` | `47,203` | `68` | `232` | `232` | `0.095×0.196×0.095` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_shaker_salt` | `shaker-salt` | `.glb, .fbx, .obj/.mtl` | `11,792` | `50,871` | `68` | `232` | `232` | `0.095×0.196×0.095` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_skewer_vegetables` | `skewer-vegetables` | `.glb, .fbx, .obj/.mtl` | `22,604` | `102,127` | `90` | `176` | `176` | `0.597×0.108×0.108` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_skewer` | `skewer` | `.glb, .fbx, .obj/.mtl` | `16,544` | `79,692` | `66` | `136` | `136` | `0.597×0.094×0.108` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_soda_bottle` | `soda-bottle` | `.glb, .fbx, .obj/.mtl` | `11,324` | `49,316` | `60` | `200` | `200` | `0.180×0.580×0.156` | `food` | `NO` | APPROVED (CC0) |
| `kenney_soda_can_crushed` | `soda-can-crushed` | `.glb, .fbx, .obj/.mtl` | `21,304` | `72,845` | `120` | `424` | `424` | `0.247×0.181×0.247` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_soda_can` | `soda-can` | `.glb, .fbx, .obj/.mtl` | `16,384` | `60,569` | `86` | `328` | `328` | `0.225×0.351×0.225` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_soda_glass` | `soda-glass` | `.glb, .fbx, .obj/.mtl` | `12,888` | `65,338` | `91` | `192` | `192` | `0.262×0.413×0.297` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_soda` | `soda` | `.glb, .fbx, .obj/.mtl` | `12,356` | `57,289` | `104` | `376` | `376` | `0.254×0.432×0.254` | `food` | `NO` | APPROVED (CC0) |
| `kenney_soy` | `soy` | `.glb, .fbx, .obj/.mtl` | `5,144` | `37,661` | `36` | `136` | `136` | `0.165×0.040×0.191` | `other` | `NO` | APPROVED (CC0) |
| `kenney_steamer` | `steamer` | `.glb, .fbx, .obj/.mtl` | `45,700` | `124,268` | `262` | `492` | `492` | `0.640×0.600×0.640` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_strawberry` | `strawberry` | `.glb, .fbx, .obj/.mtl` | `16,620` | `62,623` | `80` | `312` | `312` | `0.120×0.182×0.120` | `food` | `YES` | APPROVED (CC0) |
| `kenney_styrofoam_dinner` | `styrofoam-dinner` | `.glb, .fbx, .obj/.mtl` | `24,448` | `104,277` | `147` | `378` | `378` | `1.259×0.822×0.759` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_styrofoam` | `styrofoam` | `.glb, .fbx, .obj/.mtl` | `11,980` | `57,030` | `80` | `244` | `244` | `1.259×0.822×0.759` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_sub` | `sub` | `.glb, .fbx, .obj/.mtl` | `58,388` | `172,826` | `272` | `574` | `574` | `0.283×0.223×0.676` | `food` | `NO` | APPROVED (CC0) |
| `kenney_sundae` | `sundae` | `.glb, .fbx, .obj/.mtl` | `26,416` | `106,234` | `176` | `560` | `560` | `0.223×0.668×0.258` | `food` | `NO` | APPROVED (CC0) |
| `kenney_sushi_egg` | `sushi-egg` | `.glb, .fbx, .obj/.mtl` | `7,644` | `41,805` | `56` | `156` | `156` | `0.118×0.079×0.174` | `food` | `NO` | APPROVED (CC0) |
| `kenney_sushi_salmon` | `sushi-salmon` | `.glb, .fbx, .obj/.mtl` | `8,852` | `44,556` | `68` | `192` | `192` | `0.108×0.089×0.201` | `food` | `NO` | APPROVED (CC0) |
| `kenney_taco` | `taco` | `.glb, .fbx, .obj/.mtl` | `17,476` | `64,776` | `112` | `348` | `348` | `0.426×0.262×0.114` | `food` | `NO` | APPROVED (CC0) |
| `kenney_tajine_lid` | `tajine-lid` | `.glb, .fbx, .obj/.mtl` | `13,796` | `55,686` | `81` | `272` | `272` | `0.755×0.442×0.794` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_tajine` | `tajine` | `.glb, .fbx, .obj/.mtl` | `15,644` | `59,402` | `84` | `328` | `328` | `0.819×0.138×0.861` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_tomato_slice` | `tomato-slice` | `.glb, .fbx, .obj/.mtl` | `12,348` | `49,932` | `88` | `280` | `280` | `0.180×0.030×0.180` | `food` | `NO` | APPROVED (CC0) |
| `kenney_tomato` | `tomato` | `.glb, .fbx, .obj/.mtl` | `14,084` | `55,797` | `68` | `264` | `264` | `0.170×0.143×0.170` | `food` | `NO` | APPROVED (CC0) |
| `kenney_turkey` | `turkey` | `.glb, .fbx, .obj/.mtl` | `37,192` | `123,960` | `190` | `544` | `544` | `0.935×0.377×0.679` | `food` | `NO` | APPROVED (CC0) |
| `kenney_utensil_fork` | `utensil-fork` | `.glb, .fbx, .obj/.mtl` | `4,816` | `34,462` | `24` | `88` | `88` | `0.503×0.018×0.084` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_utensil_knife` | `utensil-knife` | `.glb, .fbx, .obj/.mtl` | `3,492` | `31,408` | `11` | `36` | `36` | `0.601×0.018×0.078` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_utensil_spoon` | `utensil-spoon` | `.glb, .fbx, .obj/.mtl` | `6,128` | `37,044` | `19` | `92` | `92` | `0.480×0.028×0.120` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_waffle` | `waffle` | `.glb, .fbx, .obj/.mtl` | `47,924` | `133,036` | `296` | `1176` | `1176` | `0.320×0.040×0.320` | `food` | `NO` | APPROVED (CC0) |
| `kenney_watermelon` | `watermelon` | `.glb, .fbx, .obj/.mtl` | `93,884` | `285,708` | `1217` | `1376` | `1376` | `0.455×0.476×0.455` | `food` | `NO` | APPROVED (CC0) |
| `kenney_whipped_cream` | `whipped-cream` | `.glb, .fbx, .obj/.mtl` | `4,916` | `41,176` | `42` | `160` | `160` | `0.136×0.097×0.157` | `food` | `NO` | APPROVED (CC0) |
| `kenney_whisk` | `whisk` | `.glb, .fbx, .obj/.mtl` | `10,264` | `47,376` | `66` | `300` | `300` | `0.724×0.158×0.158` | `other` | `N/A` | APPROVED (CC0) |
| `kenney_whole_ham` | `whole-ham` | `.glb, .fbx, .obj/.mtl` | `11,752` | `54,440` | `72` | `256` | `256` | `0.381×0.440×0.640` | `food` | `NO` | APPROVED (CC0) |
| `kenney_wholer_ham` | `wholer-ham` | `.glb, .fbx, .obj/.mtl` | `12,916` | `54,760` | `54` | `232` | `232` | `0.341×0.394×0.829` | `food` | `NO` | APPROVED (CC0) |
| `kenney_wine_red` | `wine-red` | `.glb, .fbx, .obj/.mtl` | `14,200` | `57,202` | `76` | `264` | `264` | `0.191×0.699×0.165` | `food` | `NO` | APPROVED (CC0) |
| `kenney_wine_white` | `wine-white` | `.glb, .fbx, .obj/.mtl` | `13,524` | `54,141` | `66` | `248` | `248` | `0.203×0.656×0.176` | `food` | `NO` | APPROVED (CC0) |

### 5.2 Pack: `KayKit_Dungeon_Pack_1.1_FREE.zip` (`211` unique models)

| Asset ID | Name | Formats | Primary File Size (B) | Total Pack Bytes | Verts | Polys | Tris | Scale `(X, Y, Z)` m | Category | Hamster Safe | Licence & Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `kaykit_banner_blue` | `banner_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,614` | `62,917` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_brown` | `banner_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,617` | `62,890` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_green` | `banner_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,617` | `62,954` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternA_blue` | `banner_patternA_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,773` | `66,423` | `74` | `70` | `110` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternA_brown` | `banner_patternA_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,776` | `66,332` | `74` | `70` | `110` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternA_green` | `banner_patternA_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,776` | `66,396` | `74` | `70` | `110` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternA_red` | `banner_patternA_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,770` | `66,386` | `74` | `70` | `110` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternA_white` | `banner_patternA_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,776` | `66,364` | `74` | `70` | `110` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternA_yellow` | `banner_patternA_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,779` | `66,401` | `74` | `70` | `110` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternB_blue` | `banner_patternB_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,961` | `63,758` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternB_brown` | `banner_patternB_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,964` | `63,731` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternB_green` | `banner_patternB_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,964` | `63,795` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternB_red` | `banner_patternB_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,958` | `63,753` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternB_white` | `banner_patternB_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,964` | `63,731` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternB_yellow` | `banner_patternB_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,967` | `63,768` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternC_blue` | `banner_patternC_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,961` | `63,758` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternC_brown` | `banner_patternC_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,964` | `63,763` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternC_green` | `banner_patternC_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,964` | `63,763` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternC_red` | `banner_patternC_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,958` | `63,753` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternC_white` | `banner_patternC_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,964` | `63,763` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_patternC_yellow` | `banner_patternC_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,967` | `63,768` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_red` | `banner_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,611` | `62,944` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_shield_blue` | `banner_shield_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,619` | `184,984` | `358` | `388` | `639` | `2.232×3.196×0.374` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_shield_brown` | `banner_shield_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,622` | `184,957` | `358` | `388` | `639` | `2.232×3.196×0.374` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_shield_green` | `banner_shield_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,622` | `184,989` | `358` | `388` | `639` | `2.232×3.196×0.374` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_shield_red` | `banner_shield_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,616` | `185,011` | `358` | `388` | `639` | `2.232×3.196×0.374` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_shield_white` | `banner_shield_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,622` | `184,989` | `358` | `388` | `639` | `2.232×3.196×0.374` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_shield_yellow` | `banner_shield_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,625` | `185,058` | `358` | `388` | `639` | `2.232×3.196×0.374` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_thin_blue` | `banner_thin_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,522` | `59,134` | `57` | `49` | `83` | `1.100×3.171×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_thin_brown` | `banner_thin_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,525` | `59,107` | `57` | `49` | `83` | `1.100×3.171×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_thin_green` | `banner_thin_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,525` | `59,171` | `57` | `49` | `83` | `1.100×3.171×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_thin_red` | `banner_thin_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,519` | `59,161` | `57` | `49` | `83` | `1.100×3.171×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_thin_white` | `banner_thin_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,525` | `59,139` | `57` | `49` | `83` | `1.100×3.171×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_thin_yellow` | `banner_thin_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,528` | `59,144` | `57` | `49` | `83` | `1.100×3.171×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_triple_blue` | `banner_triple_blue` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,555` | `96,211` | `181` | `161` | `263` | `3.700×3.196×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_triple_brown` | `banner_triple_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,558` | `96,088` | `181` | `161` | `263` | `3.700×3.196×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_triple_green` | `banner_triple_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,558` | `96,312` | `181` | `161` | `263` | `3.700×3.196×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_triple_red` | `banner_triple_red` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,552` | `96,270` | `181` | `161` | `263` | `3.700×3.196×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_triple_white` | `banner_triple_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,558` | `96,152` | `181` | `161` | `263` | `3.700×3.196×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_triple_yellow` | `banner_triple_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,561` | `96,125` | `181` | `161` | `263` | `3.700×3.196×0.362` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_white` | `banner_white` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,617` | `62,922` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_banner_yellow` | `banner_yellow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,620` | `62,927` | `67` | `63` | `97` | `1.500×3.196×0.312` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_barrel_large` | `barrel_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `28,825` | `146,959` | `310` | `313` | `561` | `1.800×2.000×1.800` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_barrel_large_decorated` | `barrel_large_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `54,275` | `253,815` | `569` | `641` | `1047` | `1.938×2.557×1.855` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_barrel_small` | `barrel_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `17,615` | `83,971` | `109` | `114` | `207` | `1.001×1.018×1.001` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_barrel_small_stack` | `barrel_small_stack` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `76,589` | `274,142` | `591` | `774` | `1149` | `1.850×1.770×1.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_barrier` | `barrier` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,256` | `58,475` | `68` | `45` | `90` | `4.000×1.100×0.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_barrier_colum_half` | `barrier_colum_half` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,183` | `58,565` | `61` | `45` | `86` | `2.350×1.400×0.700` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_barrier_column` | `barrier_column` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,834` | `62,587` | `77` | `57` | `110` | `4.000×1.400×0.700` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_barrier_corner` | `barrier_corner` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,094` | `67,592` | `97` | `66` | `128` | `2.395×1.400×2.395` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_barrier_half` | `barrier_half` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `5,921` | `49,992` | `36` | `21` | `42` | `2.000×1.100×0.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bed_decorated` | `bed_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `73,110` | `321,302` | `811` | `871` | `1410` | `2.606×1.701×3.057` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_bed_floor` | `bed_floor` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,504` | `79,381` | `140` | `141` | `232` | `1.500×0.563×3.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_bed_frame` | `bed_frame` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,630` | `94,118` | `200` | `179` | `304` | `1.500×1.063×3.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_A_brown` | `bottle_A_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,806` | `71,561` | `74` | `92` | `144` | `0.368×0.886×0.368` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_A_green` | `bottle_A_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `11,318` | `72,329` | `74` | `92` | `144` | `0.368×0.886×0.368` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_A_labeled_brown` | `bottle_A_labeled_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,958` | `71,945` | `74` | `92` | `144` | `0.368×0.886×0.368` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_A_labeled_green` | `bottle_A_labeled_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `11,470` | `72,681` | `74` | `92` | `144` | `0.368×0.886×0.368` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_B_brown` | `bottle_B_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,804` | `71,591` | `74` | `92` | `144` | `0.553×0.886×0.553` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_B_green` | `bottle_B_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `11,316` | `72,359` | `74` | `92` | `144` | `0.553×0.886×0.553` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_C_brown` | `bottle_C_brown` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,807` | `71,531` | `74` | `92` | `144` | `0.737×0.906×0.737` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_bottle_C_green` | `bottle_C_green` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `11,319` | `72,331` | `74` | `92` | `144` | `0.737×0.906×0.737` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_box_large` | `box_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `14,387` | `77,243` | `96` | `110` | `188` | `1.500×1.500×1.500` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_box_small` | `box_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `14,340` | `77,163` | `96` | `110` | `188` | `1.000×1.000×1.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_box_small_decorated` | `box_small_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `57,360` | `227,438` | `493` | `512` | `928` | `1.490×1.483×1.487` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_box_stacked` | `box_stacked` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `126,505` | `504,070` | `1134` | `1251` | `2173` | `3.475×3.309×3.635` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_candle` | `candle` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,323` | `54,107` | `37` | `48` | `66` | `0.334×0.873×0.329` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_candle_lit` | `candle_lit` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `7,590` | `61,908` | `66` | `84` | `120` | `0.334×1.051×0.329` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_candle_melted` | `candle_melted` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,344` | `54,851` | `37` | `48` | `66` | `0.334×0.702×0.329` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_candle_thin` | `candle_thin` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,339` | `54,197` | `37` | `48` | `66` | `0.193×0.873×0.190` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_candle_thin_lit` | `candle_thin_lit` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `7,606` | `62,030` | `66` | `84` | `120` | `0.193×1.051×0.190` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_candle_triple` | `candle_triple` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,963` | `80,592` | `111` | `144` | `198` | `0.501×0.873×0.390` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_ceiling_tile` | `ceiling_tile` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,576` | `50,608` | `36` | `30` | `60` | `4.000×0.350×4.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_chair` | `chair` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,995` | `102,865` | `177` | `174` | `294` | `0.750×1.226×0.750` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_chest` | `chest` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `45,607` | `150,055` | `150` | `149` | `266` | `1.600×0.600×1.246` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_chest_gold` | `chest_gold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `85,751` | `304,428` | `600` | `593` | `1106` | `1.600×1.041×1.246` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_coin` | `coin` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `7,478` | `57,863` | `42` | `48` | `80` | `0.360×0.125×0.360` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_coin_stack_large` | `coin_stack_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `85,523` | `353,180` | `948` | `936` | `1776` | `1.437×1.157×1.659` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_coin_stack_medium` | `coin_stack_medium` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `49,083` | `217,675` | `519` | `512` | `968` | `0.993×0.641×1.034` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_coin_stack_small` | `coin_stack_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `23,873` | `119,323` | `228` | `224` | `416` | `0.959×0.478×0.896` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_column` | `column` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,220` | `49,935` | `25` | `24` | `44` | `0.700×1.400×0.700` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_crates_stacked` | `crates_stacked` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `85,138` | `330,993` | `730` | `806` | `1331` | `2.089×2.142×2.249` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_large` | `floor_dirt_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,960` | `69,242` | `90` | `99` | `104` | `4.000×0.209×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_large_rocky` | `floor_dirt_large_rocky` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,088` | `92,984` | `152` | `182` | `187` | `4.000×0.393×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_small_A` | `floor_dirt_small_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,220` | `53,392` | `39` | `40` | `45` | `2.000×0.186×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_small_B` | `floor_dirt_small_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `5,264` | `50,158` | `30` | `31` | `36` | `2.000×0.189×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_small_C` | `floor_dirt_small_C` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `5,343` | `49,863` | `28` | `28` | `33` | `2.000×0.209×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_small_corner` | `floor_dirt_small_corner` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,683` | `54,496` | `42` | `41` | `56` | `2.000×0.154×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_small_D` | `floor_dirt_small_D` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `4,431` | `46,122` | `17` | `15` | `20` | `2.000×0.138×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_dirt_small_weeds` | `floor_dirt_small_weeds` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `22,673` | `128,843` | `231` | `321` | `416` | `2.000×0.295×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_foundation_allsides` | `floor_foundation_allsides` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `30,177` | `124,270` | `284` | `230` | `360` | `2.200×2.000×2.200` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_foundation_corner` | `floor_foundation_corner` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `17,605` | `86,680` | `154` | `126` | `202` | `2.100×2.000×2.100` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_foundation_diagonal_corner` | `floor_foundation_diagonal_corner` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `10,845` | `66,256` | `83` | `69` | `111` | `2.100×2.000×2.100` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_foundation_front` | `floor_foundation_front` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `11,319` | `67,205` | `89` | `74` | `123` | `2.000×2.000×2.100` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_foundation_front_and_back` | `floor_foundation_front_and_back` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `17,629` | `86,774` | `154` | `126` | `202` | `2.000×2.000×2.200` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_foundation_front_and_sides` | `floor_foundation_front_and_sides` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `23,917` | `105,601` | `219` | `178` | `281` | `2.200×2.000×2.100` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_big_grate` | `floor_tile_big_grate` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `22,284` | `101,295` | `233` | `152` | `292` | `4.000×1.050×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_big_grate_open` | `floor_tile_big_grate_open` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `21,739` | `99,679` | `232` | `144` | `284` | `4.000×1.050×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_big_spikes` | `floor_tile_big_spikes` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `46,067` | `157,346` | `313` | `289` | `530` | `4.000×0.200×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_extralarge_grates` | `floor_tile_extralarge_grates` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `50,813` | `197,807` | `561` | `416` | `772` | `8.000×1.130×8.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_extralarge_grates_open` | `floor_tile_extralarge_grates_open` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `50,268` | `196,400` | `561` | `412` | `764` | `8.000×1.130×8.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_grate` | `floor_tile_grate` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,681` | `71,653` | `128` | `71` | `142` | `4.000×1.030×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_grate_open` | `floor_tile_grate_open` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,556` | `71,384` | `128` | `70` | `140` | `4.000×1.030×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_large` | `floor_tile_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,927` | `72,668` | `97` | `100` | `188` | `4.000×0.150×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_large_rocks` | `floor_tile_large_rocks` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `22,584` | `119,532` | `194` | `257` | `338` | `4.000×0.636×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small` | `floor_tile_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,593` | `52,821` | `36` | `37` | `66` | `2.000×0.150×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small_broken_A` | `floor_tile_small_broken_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,133` | `59,511` | `50` | `62` | `94` | `2.000×0.150×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small_broken_B` | `floor_tile_small_broken_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `7,064` | `55,567` | `41` | `52` | `76` | `2.000×0.150×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small_corner` | `floor_tile_small_corner` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `4,863` | `47,359` | `18` | `18` | `31` | `2.000×0.150×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small_decorated` | `floor_tile_small_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `24,700` | `126,616` | `229` | `289` | `390` | `2.000×0.773×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small_weeds_A` | `floor_tile_small_weeds_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `30,019` | `160,177` | `306` | `437` | `589` | `2.000×0.295×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_tile_small_weeds_B` | `floor_tile_small_weeds_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `23,503` | `131,095` | `233` | `333` | `447` | `2.000×0.295×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_wood_large` | `floor_wood_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `21,530` | `85,055` | `135` | `168` | `272` | `4.000×0.150×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_wood_large_dark` | `floor_wood_large_dark` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `21,545` | `85,080` | `135` | `168` | `272` | `4.000×0.150×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_wood_small` | `floor_wood_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,138` | `54,046` | `42` | `50` | `78` | `2.000×0.150×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_floor_wood_small_dark` | `floor_wood_small_dark` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,153` | `54,103` | `42` | `50` | `78` | `2.000×0.150×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_keg` | `keg` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `42,698` | `196,287` | `453` | `434` | `807` | `1.800×2.051×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_keg_decorated` | `keg_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `118,363` | `470,612` | `1159` | `1184` | `2058` | `3.519×2.051×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_key` | `key` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `9,107` | `68,322` | `80` | `92` | `160` | `0.896×0.403×0.142` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_keyring` | `keyring` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `30,261` | `167,456` | `364` | `420` | `728` | `1.031×0.261×1.209` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_keyring_hanging` | `keyring_hanging` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `30,285` | `167,016` | `364` | `412` | `728` | `0.680×1.220×0.384` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_pillar` | `pillar` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `11,513` | `65,495` | `73` | `72` | `136` | `1.500×4.000×1.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_pillar_decorated` | `pillar_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `46,999` | `206,063` | `421` | `446` | `761` | `2.232×4.000×1.710` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_plate` | `plate` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,331` | `62,701` | `62` | `72` | `120` | `0.971×0.129×0.971` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_plate_food_A` | `plate_food_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `24,200` | `141,500` | `291` | `355` | `547` | `1.025×0.787×0.971` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_plate_food_B` | `plate_food_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,582` | `100,244` | `166` | `224` | `306` | `0.971×0.236×0.971` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_plate_small` | `plate_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `8,350` | `62,800` | `62` | `72` | `120` | `0.485×0.129×0.485` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_plate_stack` | `plate_stack` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `18,879` | `109,884` | `198` | `216` | `360` | `0.997×0.564×1.002` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_rubble_half` | `rubble_half` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `24,809` | `139,560` | `228` | `385` | `390` | `4.000×3.500×3.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_rubble_large` | `rubble_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `46,170` | `239,379` | `460` | `778` | `788` | `8.129×3.496×3.183` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_shelf_large` | `shelf_large` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `7,984` | `55,902` | `48` | `39` | `76` | `2.000×0.450×0.500` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_shelf_small` | `shelf_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,904` | `52,772` | `36` | `33` | `60` | `1.000×0.400×0.500` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_shelf_small_candles` | `shelf_small_candles` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `14,967` | `87,650` | `144` | `150` | `231` | `1.000×0.994×0.500` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_shelves` | `shelves` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,960` | `69,817` | `96` | `78` | `152` | `2.000×1.950×0.500` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs` | `stairs` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `28,690` | `122,311` | `282` | `219` | `358` | `5.000×5.100×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_long` | `stairs_long` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `35,355` | `142,974` | `354` | `273` | `442` | `5.000×5.100×8.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_long_modular_center` | `stairs_long_modular_center` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,722` | `52,811` | `56` | `27` | `54` | `2.000×4.000×8.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_long_modular_left` | `stairs_long_modular_left` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `21,090` | `99,082` | `205` | `150` | `248` | `1.500×5.100×8.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_long_modular_right` | `stairs_long_modular_right` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `21,040` | `99,046` | `205` | `150` | `248` | `1.500×5.100×8.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_modular_center` | `stairs_modular_center` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `6,707` | `52,754` | `56` | `27` | `54` | `2.000×4.000×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_modular_left` | `stairs_modular_left` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `17,751` | `88,808` | `169` | `123` | `206` | `1.500×5.100×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_modular_right` | `stairs_modular_right` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `17,700` | `88,512` | `169` | `123` | `206` | `1.500×5.100×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_narrow` | `stairs_narrow` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `28,709` | `122,510` | `282` | `219` | `358` | `4.000×5.100×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_wall_left` | `stairs_wall_left` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `42,628` | `169,132` | `415` | `370` | `574` | `4.000×5.100×5.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_wall_right` | `stairs_wall_right` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `42,631` | `169,076` | `415` | `370` | `574` | `4.000×5.100×5.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_walled` | `stairs_walled` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `56,574` | `212,694` | `548` | `517` | `790` | `5.000×4.000×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_wide` | `stairs_wide` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `28,705` | `122,238` | `282` | `219` | `358` | `7.000×5.100×4.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_wood` | `stairs_wood` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,537` | `92,514` | `162` | `184` | `296` | `3.300×4.050×6.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stairs_wood_decorated` | `stairs_wood_decorated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `142,380` | `548,223` | `1336` | `1611` | `2537` | `3.300×4.050×6.000` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_stool` | `stool` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `13,909` | `76,786` | `112` | `100` | `172` | `0.750×0.500×0.750` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_sword_shield` | `sword_shield` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `31,942` | `159,072` | `291` | `325` | `542` | `2.232×1.667×0.336` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_sword_shield_broken` | `sword_shield_broken` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `24,815` | `134,088` | `209` | `255` | `396` | `1.426×1.962×0.336` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_sword_shield_gold` | `sword_shield_gold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `31,957` | `159,065` | `291` | `325` | `542` | `2.232×1.667×0.336` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_table_long` | `table_long` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `19,911` | `95,783` | `172` | `166` | `280` | `2.000×1.000×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_long_broken` | `table_long_broken` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `38,292` | `170,294` | `333` | `378` | `550` | `2.409×1.266×4.404` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_long_decorated_A` | `table_long_decorated_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `94,207` | `424,677` | `1094` | `1229` | `1961` | `2.059×1.886×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_long_decorated_C` | `table_long_decorated_C` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `194,368` | `755,305` | `1881` | `2144` | `3499` | `2.000×2.768×4.025` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_long_tablecloth` | `table_long_tablecloth` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `23,334` | `109,250` | `228` | `202` | `354` | `2.000×1.000×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_long_tablecloth_decorated_A` | `table_long_tablecloth_decorated_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `97,628` | `438,875` | `1150` | `1265` | `2035` | `2.059×1.886×4.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_medium` | `table_medium` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `18,622` | `90,643` | `160` | `152` | `256` | `2.000×1.000×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_medium_broken` | `table_medium_broken` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `19,826` | `101,915` | `154` | `186` | `247` | `2.277×0.972×2.428` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_medium_decorated_A` | `table_medium_decorated_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `60,616` | `275,676` | `660` | `756` | `1186` | `2.000×1.886×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_medium_tablecloth` | `table_medium_tablecloth` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `20,100` | `94,973` | `180` | `158` | `270` | `2.000×1.000×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_medium_tablecloth_decorated_B` | `table_medium_tablecloth_decorated_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `62,094` | `280,393` | `680` | `762` | `1200` | `2.000×1.886×2.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_small` | `table_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,305` | `81,003` | `132` | `110` | `192` | `1.000×1.000×1.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_small_decorated_A` | `table_small_decorated_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `50,275` | `228,828` | `533` | `578` | `986` | `1.039×1.621×1.211` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_table_small_decorated_B` | `table_small_decorated_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `89,590` | `329,329` | `859` | `830` | `1576` | `1.012×2.157×1.000` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_torch` | `torch` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `13,544` | `83,431` | `110` | `124` | `216` | `0.550×1.042×0.550` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_torch_lit` | `torch_lit` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `14,809` | `91,573` | `139` | `160` | `270` | `0.550×1.126×0.550` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_torch_mounted` | `torch_mounted` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `17,240` | `97,433` | `142` | `159` | `278` | `0.550×1.062×0.616` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_large_A` | `trunk_large_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,741` | `84,100` | `104` | `114` | `204` | `1.500×1.000×1.300` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_large_B` | `trunk_large_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,741` | `84,100` | `104` | `114` | `204` | `1.500×1.000×1.300` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_large_C` | `trunk_large_C` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,741` | `84,164` | `104` | `114` | `204` | `1.500×1.000×1.300` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_medium_A` | `trunk_medium_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,079` | `72,713` | `76` | `82` | `148` | `0.953×0.727×0.875` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_medium_B` | `trunk_medium_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,079` | `72,681` | `76` | `82` | `148` | `0.953×0.727×0.875` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_medium_C` | `trunk_medium_C` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `12,079` | `72,681` | `76` | `82` | `148` | `0.953×0.727×0.875` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_small_A` | `trunk_small_A` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,743` | `84,163` | `104` | `114` | `204` | `0.675×0.484×0.583` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_small_B` | `trunk_small_B` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,743` | `84,195` | `104` | `114` | `204` | `0.675×0.484×0.583` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_trunk_small_C` | `trunk_small_C` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,743` | `84,163` | `104` | `114` | `204` | `0.675×0.484×0.583` | `decor` | `N/A` | APPROVED (CC0) |
| `kaykit_wall` | `wall` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `38,224` | `150,649` | `368` | `311` | `494` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_arched` | `wall_arched` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `53,720` | `204,139` | `524` | `473` | `724` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_archedwindow_gated` | `wall_archedwindow_gated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `49,916` | `199,316` | `524` | `429` | `732` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_archedwindow_gated_scaffold` | `wall_archedwindow_gated_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `46,202` | `185,244` | `512` | `395` | `674` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_archedwindow_open` | `wall_archedwindow_open` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `43,126` | `176,301` | `430` | `380` | `635` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_broken` | `wall_broken` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `55,120` | `217,592` | `550` | `467` | `784` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_corner` | `wall_corner` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `34,160` | `141,004` | `316` | `282` | `443` | `2.500×4.000×2.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_corner_gated` | `wall_corner_gated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `35,709` | `151,490` | `372` | `299` | `557` | `2.500×4.000×2.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_corner_scaffold` | `wall_corner_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,230` | `159,468` | `404` | `318` | `515` | `2.500×4.000×2.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_corner_small` | `wall_corner_small` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `19,336` | `93,420` | `162` | `138` | `223` | `1.500×4.000×1.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_cracked` | `wall_cracked` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `106,257` | `469,233` | `1152` | `1463` | `2010` | `4.000×4.000×1.259` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_crossing` | `wall_crossing` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `50,815` | `195,003` | `480` | `449` | `698` | `4.000×4.000×4.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_doorway` | `wall_doorway` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `57,405` | `198,699` | `292` | `278` | `448` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_doorway_scaffold` | `wall_doorway_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `63,768` | `219,150` | `394` | `318` | `530` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_doorway_sides` | `wall_doorway_sides` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `81,492` | `293,338` | `800` | `730` | `1160` | `5.000×4.000×4.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_doorway_Tsplit` | `wall_doorway_Tsplit` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `76,487` | `279,943` | `739` | `707` | `1096` | `8.000×4.000×2.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_endcap` | `wall_endcap` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `19,421` | `93,103` | `166` | `136` | `222` | `1.067×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_gated` | `wall_gated` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `32,078` | `133,936` | `330` | `240` | `449` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_half` | `wall_half` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `22,360` | `102,340` | `198` | `170` | `272` | `2.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_half_endcap` | `wall_half_endcap` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `22,259` | `102,038` | `196` | `169` | `268` | `2.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_half_endcap_sloped` | `wall_half_endcap_sloped` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `19,139` | `92,300` | `162` | `141` | `230` | `2.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_open_scaffold` | `wall_open_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `15,572` | `78,781` | `136` | `110` | `196` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_pillar` | `wall_pillar` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `39,977` | `158,195` | `366` | `335` | `540` | `4.000×4.000×1.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_scaffold` | `wall_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `44,261` | `173,008` | `466` | `361` | `584` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_shelves` | `wall_shelves` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `104,761` | `387,928` | `960` | `919` | `1582` | `4.000×4.000×1.368` | `prop` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_sloped` | `wall_sloped` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `21,584` | `100,152` | `191` | `163` | `257` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_Tsplit` | `wall_Tsplit` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `44,549` | `174,296` | `424` | `381` | `596` | `4.000×4.000×2.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_Tsplit_sloped` | `wall_Tsplit_sloped` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `42,024` | `166,943` | `393` | `357` | `555` | `4.000×4.000×2.500` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_window_closed` | `wall_window_closed` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `46,932` | `182,525` | `464` | `379` | `664` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_window_closed_scaffold` | `wall_window_closed_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `52,000` | `200,752` | `552` | `415` | `736` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_window_open` | `wall_window_open` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `42,726` | `168,579` | `404` | `349` | `604` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |
| `kaykit_wall_window_open_scaffold` | `wall_window_open_scaffold` | `.gltf/.bin, .fbx (x2 standard+unity), .obj/.mtl` | `47,794` | `186,806` | `492` | `385` | `676` | `4.000×4.000×1.000` | `other` | `N/A` | APPROVED (CC0) |

### 5.3 Pack: `drive-download-20261119T082111Z-1-001.zip` (`103` unique models)

| Asset ID | Name | Formats | Primary File Size (B) | Total Pack Bytes | Verts | Polys | Tris | Scale `(X, Y, Z)` m | Category | Hamster Safe | Licence & Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `drive_apple` | `Apple` | `.blend, .fbx, .obj/.mtl` | `558,084` | `617,075` | `229` | `229` | `440` | `0.802×0.852×0.799` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_apple_green` | `Apple_Green` | `.blend, .fbx, .obj/.mtl` | `557,412` | `616,480` | `229` | `229` | `440` | `0.802×0.852×0.799` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_avocado` | `Avocado` | `.blend, .fbx, .obj/.mtl` | `534,112` | `566,920` | `132` | `128` | `256` | `0.753×1.094×0.540` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_avocado_empty` | `Avocado_Empty` | `.blend, .fbx, .obj/.mtl` | `521,624` | `550,542` | `108` | `104` | `212` | `0.738×1.094×0.382` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bacon_burned` | `Bacon_Burned` | `.blend, .fbx, .obj/.mtl` | `547,704` | `595,398` | `284` | `284` | `564` | `1.157×0.021×0.297` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bacon_cooked` | `Bacon_Cooked` | `.blend, .fbx, .obj/.mtl` | `558,808` | `607,839` | `284` | `284` | `564` | `1.157×0.021×0.297` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bacon_uncooked` | `Bacon_Uncooked` | `.blend, .fbx, .obj/.mtl` | `558,808` | `607,801` | `284` | `284` | `564` | `1.157×0.021×0.297` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_banana` | `Banana` | `.blend, .fbx, .obj/.mtl` | `517,256` | `554,589` | `176` | `174` | `348` | `1.175×1.404×0.309` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bottle1` | `Bottle1` | `.blend, .fbx, .obj/.mtl` | `532,360` | `561,544` | `112` | `106` | `220` | `0.452×1.564×0.452` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bottle2` | `Bottle2` | `.blend, .fbx, .obj/.mtl` | `543,432` | `574,206` | `112` | `106` | `220` | `0.452×1.623×0.452` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bread` | `Bread` | `.blend, .fbx, .obj/.mtl` | `545,016` | `592,982` | `208` | `210` | `412` | `0.693×0.847×1.199` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_bread_slice` | `Bread_Slice` | `.blend, .fbx, .obj/.mtl` | `541,592` | `586,456` | `186` | `188` | `368` | `0.693×0.847×0.108` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_broccoli` | `Broccoli` | `.blend, .fbx, .obj/.mtl` | `527,256` | `565,562` | `147` | `205` | `270` | `0.751×0.900×0.644` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_burger` | `Burger` | `.blend, .fbx, .obj/.mtl` | `592,072` | `680,576` | `573` | `516` | `847` | `1.652×1.065×1.700` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_burger_bread` | `Burger_Bread` | `.blend, .fbx, .obj/.mtl` | `520,604` | `553,775` | `156` | `126` | `218` | `1.477×0.405×1.579` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_burgerlarge` | `BurgerLarge` | `.blend, .fbx, .obj/.mtl` | `622,120` | `756,581` | `954` | `855` | `1408` | `1.719×1.446×1.666` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_burgerpatty_burned` | `BurgerPatty_Burned` | `.blend, .fbx, .obj/.mtl` | `507,576` | `529,440` | `66` | `64` | `128` | `1.425×0.336×1.425` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_burgerpatty_cooked` | `BurgerPatty_Cooked` | `.blend, .fbx, .obj/.mtl` | `507,576` | `529,434` | `66` | `64` | `128` | `1.425×0.336×1.425` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_burgerpatty_raw` | `BurgerPatty_Raw` | `.blend, .fbx, .obj/.mtl` | `508,248` | `530,098` | `66` | `64` | `128` | `1.425×0.336×1.425` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_carrot` | `Carrot` | `.blend, .fbx, .obj/.mtl` | `551,224` | `621,703` | `442` | `432` | `864` | `0.947×2.779×0.932` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cheese_singles` | `Cheese_Singles` | `.blend, .fbx, .obj/.mtl` | `506,248` | `526,028` | `54` | `48` | `96` | `1.031×0.028×0.975` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cheeseburger` | `Cheeseburger` | `.blend, .fbx, .obj/.mtl` | `558,064` | `617,872` | `332` | `332` | `588` | `1.465×0.938×1.541` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_chickenleg` | `ChickenLeg` | `.blend, .fbx, .obj/.mtl` | `539,256` | `573,221` | `146` | `144` | `288` | `1.399×0.582×0.612` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_chocolatebar` | `ChocolateBar` | `.blend, .fbx, .obj/.mtl` | `520,728` | `553,373` | `220` | `208` | `436` | `0.575×0.068×0.874` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_chopsticks` | `Chopsticks` | `.blend, .fbx, .obj/.mtl` | `521,104` | `558,126` | `224` | `214` | `440` | `1.630×0.053×0.126` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_coconut` | `Coconut` | `.blend, .fbx, .obj/.mtl` | `520,760` | `543,813` | `43` | `82` | `82` | `0.778×0.777×0.783` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_coconut_half` | `Coconut_Half` | `.blend, .fbx, .obj/.mtl` | `524,200` | `550,872` | `68` | `108` | `132` | `0.784×0.777×0.412` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cookingpot` | `CookingPot` | `.blend, .fbx, .obj/.mtl` | `513,224` | `541,484` | `136` | `124` | `260` | `2.418×1.076×1.992` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cookingpot2` | `CookingPot2` | `.blend, .fbx, .obj/.mtl` | `523,656` | `553,326` | `136` | `124` | `260` | `2.291×0.622×1.992` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cookingpot2_soup` | `CookingPot2_Soup` | `.blend, .fbx, .obj/.mtl` | `523,688` | `553,601` | `136` | `124` | `260` | `2.291×0.622×1.992` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cookingpot_soup` | `CookingPot_Soup` | `.blend, .fbx, .obj/.mtl` | `523,656` | `553,205` | `136` | `124` | `260` | `2.418×1.076×1.992` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_corndog` | `Corndog` | `.blend, .fbx, .obj/.mtl` | `525,424` | `557,780` | `146` | `138` | `284` | `0.256×1.352×0.256` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_croissant` | `Croissant` | `.blend, .fbx, .obj/.mtl` | `508,536` | `531,149` | `88` | `54` | `132` | `1.304×0.550×0.731` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_cupcake` | `Cupcake` | `.blend, .fbx, .obj/.mtl` | `538,844` | `584,394` | `216` | `230` | `412` | `0.734×0.932×0.726` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_donut1` | `Donut1` | `.blend, .fbx, .obj/.mtl` | `604,588` | `691,546` | `568` | `495` | `984` | `0.859×0.291×0.870` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_donut2` | `Donut2` | `.blend, .fbx, .obj/.mtl` | `577,824` | `662,669` | `568` | `495` | `984` | `0.879×0.291×0.867` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_donut3` | `Donut3` | `.blend, .fbx, .obj/.mtl` | `529,344` | `573,754` | `252` | `252` | `504` | `0.859×0.280×0.857` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_donut4` | `Donut4` | `.blend, .fbx, .obj/.mtl` | `577,824` | `662,490` | `568` | `495` | `984` | `0.881×0.289×0.868` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_doublecheeseburger` | `DoubleCheeseburger` | `.blend, .fbx, .obj/.mtl` | `570,256` | `647,887` | `472` | `472` | `860` | `1.494×1.197×1.541` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_egg_burned` | `Egg_Burned` | `.blend, .fbx, .obj/.mtl` | `517,532` | `539,732` | `57` | `65` | `101` | `1.192×0.107×1.117` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_egg_fried` | `Egg_Fried` | `.blend, .fbx, .obj/.mtl` | `518,204` | `540,372` | `57` | `65` | `101` | `1.192×0.107×1.117` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_egg_whole` | `Egg_Whole` | `.blend, .fbx, .obj/.mtl` | `524,760` | `565,175` | `146` | `144` | `288` | `0.363×0.466×0.363` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_egg_whole_white` | `Egg_Whole_White` | `.blend, .fbx, .obj/.mtl` | `524,760` | `565,187` | `146` | `144` | `288` | `0.363×0.466×0.363` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_eggplant` | `Eggplant` | `.blend, .fbx, .obj/.mtl` | `529,280` | `568,211` | `188` | `184` | `368` | `0.962×1.752×0.718` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_fish` | `Fish` | `.blend, .fbx, .obj/.mtl` | `545,160` | `592,246` | `221` | `236` | `438` | `3.202×0.303×1.059` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_fishbone` | `FishBone` | `.blend, .fbx, .obj/.mtl` | `542,024` | `594,881` | `312` | `286` | `588` | `1.955×0.332×0.830` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_fork` | `Fork` | `.blend, .fbx, .obj/.mtl` | `510,024` | `533,415` | `96` | `88` | `188` | `0.208×0.047×2.018` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_fries` | `Fries` | `.blend, .fbx, .obj/.mtl` | `534,480` | `571,684` | `200` | `162` | `324` | `0.949×0.586×1.326` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_fryingpan` | `FryingPan` | `.blend, .fbx, .obj/.mtl` | `521,740` | `550,431` | `114` | `102` | `214` | `1.737×0.253×2.788` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_hotdog` | `Hotdog` | `.blend, .fbx, .obj/.mtl` | `575,152` | `659,626` | `547` | `498` | `988` | `0.785×0.409×1.662` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_hotdog_bun` | `Hotdog_Bun` | `.blend, .fbx, .obj/.mtl` | `524,088` | `569,424` | `246` | `244` | `488` | `0.785×0.409×1.643` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_icecream_1` | `IceCream_1` | `.blend, .fbx, .obj/.mtl` | `546,424` | `597,469` | `263` | `280` | `466` | `0.701×1.198×0.701` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_icecream_2` | `IceCream_2` | `.blend, .fbx, .obj/.mtl` | `553,976` | `620,391` | `367` | `394` | `638` | `0.730×1.574×0.730` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_icecream_3` | `IceCream_3` | `.blend, .fbx, .obj/.mtl` | `574,080` | `667,664` | `667` | `684` | `1278` | `0.515×0.927×0.515` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_icecream_4` | `IceCream_4` | `.blend, .fbx, .obj/.mtl` | `585,472` | `696,575` | `801` | `824` | `1498` | `0.515×1.184×0.515` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_icecream_cone` | `IceCream_Cone` | `.blend, .fbx, .obj/.mtl` | `517,768` | `553,524` | `176` | `170` | `348` | `0.552×0.810×0.552` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_icecream_cone2` | `IceCream_Cone2` | `.blend, .fbx, .obj/.mtl` | `562,664` | `638,266` | `540` | `532` | `1076` | `0.467×0.630×0.449` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_jar_large` | `Jar_Large` | `.blend, .fbx, .obj/.mtl` | `524,792` | `553,393` | `110` | `102` | `216` | `0.633×0.638×0.602` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_ketchupbottle` | `KetchupBottle` | `.blend, .fbx, .obj/.mtl` | `512,872` | `539,749` | `120` | `114` | `236` | `0.500×1.533×0.500` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_ketchupmustard` | `KetchupMustard` | `.blend, .fbx, .obj/.mtl` | `544,768` | `605,798` | `364` | `360` | `720` | `0.163×0.106×1.281` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_knife` | `Knife` | `.blend, .fbx, .obj/.mtl` | `506,948` | `527,324` | `60` | `56` | `112` | `0.162×0.033×2.008` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_lettuce` | `Lettuce` | `.blend, .fbx, .obj/.mtl` | `535,384` | `601,670` | `322` | `459` | `620` | `1.788×0.231×1.683` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_lettuce_whole` | `Lettuce_Whole` | `.blend, .fbx, .obj/.mtl` | `528,152` | `579,111` | `314` | `292` | `592` | `1.661×1.369×1.661` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_mayobottle` | `MayoBottle` | `.blend, .fbx, .obj/.mtl` | `512,872` | `539,741` | `120` | `114` | `236` | `0.500×1.533×0.500` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_mushroom` | `Mushroom` | `.blend, .fbx, .obj/.mtl` | `505,960` | `526,031` | `48` | `44` | `92` | `0.358×0.410×0.413` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_mushroom_sliced` | `Mushroom_Sliced` | `.blend, .fbx, .obj/.mtl` | `530,392` | `551,872` | `48` | `40` | `92` | `0.413×0.176×0.417` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_mustardbottle` | `MustardBottle` | `.blend, .fbx, .obj/.mtl` | `512,264` | `539,163` | `120` | `114` | `236` | `0.500×1.533×0.500` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_orange` | `Orange` | `.blend, .fbx, .obj/.mtl` | `518,680` | `549,111` | `106` | `104` | `208` | `0.745×0.742×0.745` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pancake` | `Pancake` | `.blend, .fbx, .obj/.mtl` | `560,896` | `602,462` | `195` | `190` | `378` | `1.442×0.255×1.442` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pancakes_stack` | `Pancakes_Stack` | `.blend, .fbx, .obj/.mtl` | `583,408` | `656,656` | `458` | `440` | `896` | `1.581×0.637×1.621` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_peanutbutter` | `PeanutButter` | `.blend, .fbx, .obj/.mtl` | `528,768` | `557,352` | `110` | `102` | `216` | `0.475×0.724×0.451` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_peanutbutter_2` | `PeanutButter_2` | `.blend, .fbx, .obj/.mtl` | `546,952` | `575,548` | `110` | `102` | `216` | `0.475×0.724×0.451` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pepper_green` | `Pepper_Green` | `.blend, .fbx, .obj/.mtl` | `543,752` | `612,336` | `406` | `408` | `808` | `0.674×1.117×0.712` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pepper_red` | `Pepper_Red` | `.blend, .fbx, .obj/.mtl` | `548,760` | `617,329` | `406` | `408` | `808` | `0.674×1.106×0.712` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pizza` | `Pizza` | `.blend, .fbx, .obj/.mtl` | `568,104` | `651,390` | `650` | `471` | `1200` | `3.372×0.161×3.357` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pizza_burned` | `Pizza_Burned` | `.blend, .fbx, .obj/.mtl` | `539,368` | `577,893` | `210` | `172` | `392` | `1.072×0.113×1.164` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pizza_slice` | `Pizza_Slice` | `.blend, .fbx, .obj/.mtl` | `536,064` | `574,581` | `210` | `172` | `392` | `1.072×0.113×1.164` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_plate` | `Plate` | `.blend, .fbx, .obj/.mtl` | `509,272` | `532,861` | `80` | `72` | `156` | `1.737×0.255×1.827` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_plate2` | `Plate2` | `.blend, .fbx, .obj/.mtl` | `511,032` | `536,978` | `100` | `92` | `196` | `1.973×0.220×2.075` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_plate_square` | `Plate_Square` | `.blend, .fbx, .obj/.mtl` | `511,112` | `536,052` | `104` | `90` | `204` | `1.637×0.132×1.637` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_popsicle_chocolate` | `Popsicle_Chocolate` | `.blend, .fbx, .obj/.mtl` | `516,656` | `536,963` | `46` | `38` | `84` | `0.291×0.990×0.080` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_popsicle_multiple` | `Popsicle_Multiple` | `.blend, .fbx, .obj/.mtl` | `527,144` | `551,943` | `64` | `56` | `120` | `0.291×0.990×0.080` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_popsicle_strawberry` | `Popsicle_Strawberry` | `.blend, .fbx, .obj/.mtl` | `512,680` | `532,989` | `46` | `38` | `84` | `0.291×0.990×0.080` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_pumpkin` | `Pumpkin` | `.blend, .fbx, .obj/.mtl` | `541,344` | `597,767` | `326` | `320` | `644` | `1.497×0.931×1.512` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sashimi_salmon` | `Sashimi_Salmon` | `.blend, .fbx, .obj/.mtl` | `516,096` | `541,578` | `82` | `80` | `160` | `0.598×0.152×0.272` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sashimi_salmon2` | `Sashimi_Salmon2` | `.blend, .fbx, .obj/.mtl` | `522,568` | `549,110` | `82` | `80` | `160` | `0.598×0.152×0.272` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sausage_cooked` | `Sausage_Cooked` | `.blend, .fbx, .obj/.mtl` | `508,264` | `531,794` | `72` | `74` | `140` | `0.240×0.241×1.656` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sausage_raw` | `Sausage_Raw` | `.blend, .fbx, .obj/.mtl` | `508,264` | `531,776` | `72` | `74` | `140` | `0.240×0.241×1.656` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_soda` | `Soda` | `.blend, .fbx, .obj/.mtl` | `529,592` | `570,992` | `240` | `228` | `472` | `0.912×1.923×0.912` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_soysauce` | `SoySauce` | `.blend, .fbx, .obj/.mtl` | `515,560` | `534,651` | `32` | `26` | `60` | `0.596×0.275×0.596` | `other` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_spoon` | `Spoon` | `.blend, .fbx, .obj/.mtl` | `509,292` | `534,590` | `70` | `104` | `128` | `0.393×0.084×1.885` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_steak` | `Steak` | `.blend, .fbx, .obj/.mtl` | `527,760` | `568,232` | `222` | `213` | `412` | `1.320×0.340×1.913` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_steak_burned` | `Steak_burned` | `.blend, .fbx, .obj/.mtl` | `531,736` | `572,254` | `222` | `213` | `412` | `1.320×0.340×1.913` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sushi_nigiri1` | `Sushi_Nigiri1` | `.blend, .fbx, .obj/.mtl` | `517,736` | `545,952` | `102` | `98` | `196` | `0.598×0.234×0.272` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sushi_nigiri2` | `Sushi_Nigiri2` | `.blend, .fbx, .obj/.mtl` | `524,192` | `553,715` | `102` | `98` | `196` | `0.598×0.234×0.272` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sushi_nigirioctopus` | `Sushi_NigiriOctopus` | `.blend, .fbx, .obj/.mtl` | `550,688` | `611,286` | `364` | `309` | `648` | `0.762×0.350×0.267` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sushi_roll1` | `Sushi_Roll1` | `.blend, .fbx, .obj/.mtl` | `536,056` | `561,634` | `76` | `66` | `140` | `0.292×0.154×0.292` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_sushi_roll2` | `Sushi_Roll2` | `.blend, .fbx, .obj/.mtl` | `536,056` | `561,815` | `76` | `66` | `140` | `0.293×0.154×0.293` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_tentacle` | `Tentacle` | `.blend, .fbx, .obj/.mtl` | `549,032` | `607,306` | `344` | `291` | `612` | `0.762×0.276×0.267` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_tomato` | `Tomato` | `.blend, .fbx, .obj/.mtl` | `539,440` | `582,739` | `176` | `171` | `344` | `0.752×0.626×0.752` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_tomato_slice` | `Tomato_Slice` | `.blend, .fbx, .obj/.mtl` | `530,688` | `581,076` | `345` | `295` | `670` | `0.806×0.076×0.669` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_turnip` | `Turnip` | `.blend, .fbx, .obj/.mtl` | `562,608` | `640,910` | `498` | `488` | `976` | `1.248×2.392×1.234` | `food` | `YES` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |
| `drive_waffle` | `Waffle` | `.blend, .fbx, .obj/.mtl` | `551,384` | `616,869` | `558` | `552` | `1112` | `1.134×0.232×1.529` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence) |

### 5.4 Pack: `Food&DrinksPack.rar` (`10` unique models)

| Asset ID | Name | Formats | Primary File Size (B) | Total Pack Bytes | Verts | Polys | Tris | Scale `(X, Y, Z)` m | Category | Hamster Safe | Licence & Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `fooddrinks_cannedfood` | `CannedFood` | `.fbx, .png` | `61,232` | `2,500,602` | `486` | `960` | `960` | `0.384×0.097×0.141` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_canned_tuna` | `Canned_Tuna` | `.fbx, .png` | `31,712` | `2,558,482` | `162` | `320` | `320` | `0.120×0.120×0.040` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_coffeecup` | `CoffeeCup` | `.fbx, .png` | `47,424` | `5,277,845` | `402` | `800` | `800` | `0.090×0.090×0.141` | `other` | `N/A` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_frozenpizza` | `FrozenPizza` | `.fbx, .png` | `34,048` | `7,210,182` | `48` | `88` | `88` | `0.707×0.301×0.025` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_hamburger` | `Hamburger` | `.fbx, .png` | `73,200` | `3,983,069` | `572` | `1128` | `1128` | `0.138×0.138×0.077` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_hotdog` | `HotDog` | `.fbx, .png` | `51,024` | `2,286,732` | `399` | `784` | `784` | `0.054×0.158×0.038` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_ice_cream` | `Ice_Cream` | `.fbx, .png` | `55,776` | `6,614,768` | `390` | `768` | `768` | `0.603×0.152×0.174` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_milk` | `Milk` | `.fbx, .png` | `28,224` | `642,764` | `78` | `148` | `148` | `0.111×0.111×0.334` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_pizza` | `Pizza` | `.fbx, .png` | `39,472` | `3,747,932` | `216` | `428` | `428` | `0.304×0.301×0.012` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
| `fooddrinks_sushi` | `Sushi` | `.fbx, .png` | `69,904` | `3,424,879` | `724` | `1229` | `1229` | `0.055×0.049×0.041` | `food` | `NO` | REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters) |
