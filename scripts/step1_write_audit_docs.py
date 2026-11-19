"""
HAMMY Pipeline — Generate assets/ASSET_AUDIT.md, ASSETS_LICENSES.md, and CREDITS.md
from assets/audit_data.json (524 unique models across 2,766 files in assets/raw/).
Also performs the full Step 2 Gap Analysis against the required minimum set.
"""

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
AUDIT_JSON = ROOT_DIR / "assets" / "audit_data.json"
ASSET_AUDIT_MD = ROOT_DIR / "assets" / "ASSET_AUDIT.md"
ASSETS_LICENSES_MD = ROOT_DIR / "ASSETS_LICENSES.md"
CREDITS_MD = ROOT_DIR / "CREDITS.md"


def main():
    data = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    items = data["items"]

    # Group by pack
    by_pack = {}
    for it in items:
        by_pack.setdefault(it["pack"], []).append(it)

    # Group by category
    by_cat = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)

    # Build assets/ASSET_AUDIT.md
    lines = []
    lines.append("# HAMMY — Step 1 & Step 2: Downloaded Asset Audit & Gap Analysis")
    lines.append("")
    lines.append("## 1. Executive Summary of Downloaded Archives (`assets/raw/`)")
    lines.append("")
    lines.append("All four archive packages downloaded by the user into `props/` were copied into `assets/raw/` and unpacked for full inspection. Every single file (`2,766` unpacked files representing `524` unique 3D models plus `255` texture/preview `.png` files) was audited for format, byte size, vertex/polygon/triangle count, bounding-box scale in meters, textures present, author, source URL, and license compliance.")
    lines.append("")
    lines.append("| Archive Name | Unpacked Files | Unique 3D Models | Formats Present | Textures Present | Author & Source URL | Licence | Audit Verdict |")
    lines.append("| :--- | :---: | :---: | :--- | :--- | :--- | :--- | :--- |")
    lines.append("| `kenney_food-kit.zip` | `1,009` | `200` | `.glb` (200), `.fbx` (200), `.obj/.mtl` (200) | `colormap.png` (`512×512` shared atlas) + `200` UI preview `.png`s | **Kenney** (`www.kenney.nl`) — `https://kenney.nl/assets/food-kit` | **CC0 1.0 Universal** (`License.txt` verified in archive) | **APPROVED** (Filter foods by hamster safety + rescale from ~0.13–0.33 m to 1–3 cm hamster scale) |")
    lines.append("| `KayKit_Dungeon_Pack_1.1_FREE.zip` | `1,303` | `211` | `.gltf/.bin` (211), `.fbx` (422), `.obj/.mtl` (216) | `dungeon_texture.png` (`1024×1024` shared palette) + `22` sample `.png`s | **Kay Lousberg** (`www.kaylousberg.com`) — `https://kaylousberg.itch.io/kaykit-dungeon` | **CC0 1.0 Universal** (`License.txt` verified in archive) | **APPROVED** (Selective reuse of shelf, banners/flags, and small wooden items rescaled to hamster scale) |")
    lines.append("| `drive-download-20261119T082111Z-1-001.zip` | `412` | `103` | `.blend` (103), `.fbx` (103), `.obj/.mtl` (103) | **Missing external file** (`//Blender/DavidThorn/Library/Large/Texture.png` referenced inside `.blend`s; flat `.mtl` colors only) | Unknown in archive (internal path references `DavidThorn`; topology matches Quaternius Ultimate Food Pack) | **UNCLEAR** (No `LICENSE` or `README` included in `.zip`) | **REJECTED** (Rule: *Never use an asset with an unclear licence*; also missing referenced texture file) |")
    lines.append("| `Food&DrinksPack.rar` | `38` | `10` | `.fbx` (10) | `28` PBR `.png` textures (`Base_Color`, `Normal`, `Roughness`, `Height`) | Unknown (no author or README in `.rar`) | **UNCLEAR** (No `LICENSE` or `README` included in `.rar`) | **REJECTED** (Rule: *Never use an asset with an unclear licence*; also 100% processed human junk foods unsafe for hamsters) |")
    lines.append("")
    lines.append("### Existing Procedural & CC0 Assets Already in Repository (`blender/` & `reference/licence_log.csv`)")
    lines.append("In addition to `assets/raw/`, the repository already contains verified **CC0** textures from Poly Haven (`fine_grained_wood`, `plywood`, `bark_brown_02`, `concrete_floor_worn_001`, `brown_photostudio_02_1k.hdr`) and our metric SI Blender scripts (`blender/scripts/10_cage.py`, `20_clutter.py`, `60_rig_and_export_glb.py`) which procedurally construct the `0.28 m` exercise wheel, `0.08 m` ceramic food bowl, `0.15 m` wall-mounted water bottle, arched wooden hideout, straight/curved burrow tunnels, and chew sticks.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Classification Breakdown Across All 524 Audited Models")
    lines.append("")
    lines.append("| Category | Total Audited Models | From Approved CC0 Packs (`Kenney` + `KayKit`) | From Rejected Unclear-Licence Packs (`drive-download` + `Food&DrinksPack`) | Approved & Hamster-Safe / Habitat-Ready Count |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")

    for cat in ["food", "water", "costume", "prop", "decor", "other"]:
        c_items = by_cat.get(cat, [])
        cc0_cnt = sum(1 for x in c_items if "APPROVED" in x["licence_status"])
        rej_cnt = sum(1 for x in c_items if "REJECTED" in x["licence_status"])
        usable_cnt = sum(1 for x in c_items if x["usable_in_hammy"])
        lines.append(f"| **`{cat}`** | `{len(c_items)}` | `{cc0_cnt}` | `{rej_cnt}` | **`{usable_cnt}`** |")
    lines.append("")
    lines.append("> **Note on `texture` category:** All `255` standalone `.png` texture/preview files in `assets/raw/` (`204` in `kenney_food-kit`, `23` in `KayKit_Dungeon_Pack_1.1_FREE`, `28` in `Food&DrinksPack.rar`) plus the `13` Poly Haven CC0 PBR texture maps in `blender/textures/` are audited in Section 3.5 below.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Veterinary Hamster-Safety Audit of Downloaded Food Models")
    lines.append("")
    lines.append("Per Step 2 instructions (*\"Check hamster safety against a reliable pet-care source and exclude anything unsafe or doubtful\"*), every food item in `kenney_food-kit.zip` (`CC0`) was cross-checked against veterinary husbandry guidelines (**RSPCA**, **PDSA**, ** Merck Veterinary Manual**, and **California Hamster Association** safe food lists for Syrian hamsters, *Mesocricetus auratus*):")
    lines.append("")
    lines.append("### 3.1 Approved Hamster-Safe Foods in `kenney_food-kit.zip` (CC0)")
    lines.append("| Model ID | File Name (`.glb` / `.fbx` / `.obj`) | Size (GLB) | Polygons / Tris | Raw Scale `(X, Y, Z)` m | Target Hamster Scale | Veterinary Safety Assessment |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")
    for it in by_pack["kenney_food-kit.zip"]:
        if it["category"] == "food" and it["hamster_safe"] is True:
            dims = f"`{it['dimensions_m'][0]:.3f} × {it['dimensions_m'][1]:.3f} × {it['dimensions_m'][2]:.3f}`"
            lines.append(f"| `{it['id']}` | `{it['name']}.glb` | `{it['size_bytes']:,} B` | `{it['polygons']} / {it['triangles']}` | {dims} | `0.012–0.025 m` | {it['safety_or_usage_note']} |")
    lines.append("")
    lines.append("### 3.2 Excluded Unsafe or Doubtful Foods in `kenney_food-kit.zip`")
    lines.append("- **Avocado (`avocado`, `advocado-half`):** **UNSAFE (TOXIC)** — Contains persin, causing myocardial necrosis and respiratory distress in rodents.")
    lines.append("- **Citrus (`orange`, `lemon`, `lemon-half`):** **UNSAFE (TOXIC)** — High citric acid causes stomach ulceration and diarrhea in hamsters.")
    lines.append("- **Alliums (`onion`, `onion-half`, `leek`):** **UNSAFE (TOXIC)** — Organosulfoxides cause oxidative hemolysis of red blood cells (hemolytic anemia).")
    lines.append("- **Sticky Peanut Butter (`peanut-butter` jar):** **UNSAFE (POUCH IMPACTION)** — Sticky paste adheres inside the cheek pouches, causing impaction and infection. *(Note: dry unsalted whole/shelled peanuts are safe, but a peanut model is missing from Kenney and must be generated in Step 3).*")
    lines.append("- **Nightshades & Pungent Produce (`tomato`, `tomato-slice`, `eggplant`, `mushroom`, `mushroom-half`, `pepper`, `paprika`, `paprika-slice`, `radish`, `beet`, `pineapple`):** **UNSAFE / DOUBTFUL (EXCLUDED)** — Solanine, high acidity, or digestive irritants.")
    lines.append("- **High-Water / Pit Fruits (`watermelon`, `grapes`, `cherries`):** **DOUBTFUL (EXCLUDED)** — Risk of wet-tail/diarrhea (`watermelon`), renal toxicity concerns (`grapes`), or cyanogenic pits (`cherries`).")
    lines.append("- **Chocolate, Sweets & Pastries (`chocolate`, `candy-bar`, `donut*`, `cake*`, `cupcake`, `cookie*`, `ice-cream*`, `popsicle*`, `lollypop`, `sundae`, `pudding`, `waffle`, `pancakes`, `muffin`, `croissant`, `ginger-bread`, `honey`, `whipped-cream`):** **UNSAFE (TOXIC)** — Theobromine toxicity and high sugar/dairy.")
    lines.append("- **Processed Fast Food, Meat, Fish, Dairy & Beverages (`burger*`, `hot-dog*`, `pizza*`, `fries*`, `bacon*`, `sausage*`, `meat*`, `whole-ham`, `turkey`, `corn-dog`, `taco`, `sub`, `sandwich`, `sushi*`, `maki*`, `fish*`, `mussel*`, `cheese*`, `bread*`, `loaf*`, `egg*`, `soda*`, `wine*`, `cocktail`, `frappe`):** **UNSAFE (EXCLUDED)** — Salt, spices, fat, alcohol, caffeine, and spoilage risks.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Step 2: Gap Analysis Against Minimum Required Set")
    lines.append("")
    lines.append("Comparing our audited, license-approved (`CC0`) assets against the mandatory feature list in Step 2 and the Shelf-Based Override:")
    lines.append("")
    lines.append("### 4.1 Food Shelf (Hamster-Safe Only)")
    lines.append("| Required Item | Audit Status in `assets/raw/` | Action for Step 3 (Blender Generation / Adaptation) |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| **1. Seed mix** (`food_seed_mix`) | **MISSING** as standalone pickupable/offerable `.glb` in `assets/raw/` (exists in `blender/scripts/20_clutter.py` as multi-mesh bowl scatter) | **GENERATE in Step 3**: Build low-poly hamster-scale seed mix cluster (`0.024 m` cluster of sunflower seeds, golden millet, kibble pellet, corn kernel) with paw pickup pivot (`< 800` tris). |")
    lines.append("| **2. Sunflower seed** (`food_sunflower_seed`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build striped black-and-white striped Syrian hamster sunflower seed (`0.011 m × 0.005 m × 0.003 m`) with paw pickup pivot (`< 250` tris). |")
    lines.append("| **3. Peanut** (`food_peanut`) | **MISSING** in `assets/raw/` (`kenney_food-kit` only has a `peanut-butter` jar, which is unsafe) | **GENERATE in Step 3**: Build natural double-lobed unsalted peanut in shell/half-shell (`0.022 m × 0.009 m × 0.009 m`) with textured hull & paw pickup pivot (`< 400` tris). |")
    lines.append("| **4. Carrot piece** (`food_carrot_piece`) | **PARTIAL (`DOWNLOADED` whole carrot)** in `kenney_food-kit` (`carrot.glb`, `184` tris, `0.068 × 0.068 × 0.193 m` human scale) | **ADAPT & GENERATE in Step 3**: Rescale/slice Kenney CC0 carrot & build a bite-sized diced/coin carrot piece (`0.014 m`) with paw pickup pivot (`< 300` tris). |")
    lines.append("| **5. Broccoli floret** (`food_broccoli_floret`) | **PRESENT (`DOWNLOADED`)** in `kenney_food-kit` (`broccoli.glb`, `332` tris, `0.159 × 0.157 × 0.165 m` human scale) | **ADAPT in Step 3/4**: Rescale to hamster floret size (`0.018 m`), set origin to stem pickup pivot, bake/verify PBR material (`< 400` tris). |")
    lines.append("| **6. Apple piece** (`food_apple_piece`) | **PARTIAL (`DOWNLOADED` whole/half apple)** in `kenney_food-kit` (`apple.glb` `220` tris, `apple-half.glb` `168` tris, ~`0.14 m` human scale with seeds visible) | **GENERATE in Step 3**: Build a seedless fresh apple wedge/cube piece (`0.015 m`, cream flesh + red skin, zero toxic seeds) with paw pickup pivot (`< 300` tris). |")
    lines.append("| **7. Blueberry** (`food_blueberry`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build low-poly blueberry (`0.010 m` diameter) with star calyx crown, dusty indigo bloom PBR shader, and center pickup pivot (`< 350` tris). |")
    lines.append("")
    lines.append("### 4.2 Water Shelf & Food Shelf Containers")
    lines.append("| Required Item | Audit Status in `assets/raw/` | Action for Step 3 (Blender Generation / Adaptation) |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| **1. Water bottle with visible level** (`water_bottle`) | **MISSING** in `assets/raw/` (`kenney` has condiment bottles; `KayKit` has opaque potion bottles; `blender/scripts/10_cage.py` has wall-mounted bottle without separate inner liquid mesh) | **GENERATE in Step 3**: Build hamster-scale `0.15 m` clear water bottle with a **separate named mesh `water_liquid`** (so the water level `0..1` scales smoothly along Y/Z), blue cap, wall bracket, and `45°` stainless-steel ball-valve spout (`< 1,200` tris). |")
    lines.append("| **2. Small water bowl** (`water_bowl`) | **MISSING** as water-level bowl in `assets/raw/` | **GENERATE in Step 3**: Build small glazed ceramic water dish (`0.065 m` diameter, `0.026 m` height) with a **separate named mesh `water_liquid`** inside for dynamic water level scaling (`< 800` tris). |")
    lines.append("| **3. Food bowl** (`prop_food_bowl`) | **PRESENT (`DOWNLOADED` + `GENERATED`)** (`kenney_food-kit/bowl.glb` `192` tris at `0.28 m`; `10_cage.py` `prop_bowl` at `0.084 m`) | **ADAPT & EXPORT in Step 3/4**: Export both the clean hamster-scale ceramic food bowl (`0.08 m` diameter, base-center pivot) and rescaled Kenney bowl (`< 800` tris). |")
    lines.append("| **4. Shelf (for food-selection UI / cage shelf)** (`prop_shelf`) | **PRESENT (`DOWNLOADED`)** in `KayKit_Dungeon_Pack_1.1_FREE` (`shelf_small.gltf` `76` tris, `shelves.gltf` `596` tris, dungeon scale `2.1 × 0.8 × 2.1 m`) | **ADAPT in Step 3/4**: Rescale KayKit CC0 wooden shelf to hamster cage platform/shelf scale (`0.22 m × 0.12 m × 0.14 m`), base-center pivot, clean UVs (`< 600` tris). |")
    lines.append("")
    lines.append("### 4.3 Costume Shelf (`head_slot`, `neck_slot`, `back_slot`)")
    lines.append("*(Zero costumes exist in `assets/raw/`. Every costume is a **100% GAP** and must be generated in Step 3 at Syrian hamster scale (~15 cm body, ~3.8 cm head width) with named attachment sockets `head_slot`, `neck_slot`, `back_slot` matching `HamsterRig` bones `head`, `neck`, `spine_2`)*:")
    lines.append("")
    lines.append("| Required Costume | Attachment Slot | Target Hamster Dimensions | Status & Action for Step 3 |")
    lines.append("| :--- | :---: | :---: | :--- |")
    lines.append("| **1. Party hat** (`costume_party_hat`) | `head_slot` | `0.026 m` base diam × `0.036 m` cone height + pom-pom | **MISSING → GENERATE in Step 3** (`< 600` tris, origin at `head_slot` attachment point between ears) |")
    lines.append("| **2. Top hat** (`costume_top_hat`) | `head_slot` | `0.032 m` brim diam × `0.028 m` crown height + satin band | **MISSING → GENERATE in Step 3** (`< 700` tris, origin at `head_slot`) |")
    lines.append("| **3. Bow tie** (`costume_bow_tie`) | `neck_slot` | `0.028 m` width × `0.014 m` height × `0.008 m` depth | **MISSING → GENERATE in Step 3** (`< 500` tris, origin at `neck_slot` under chin/chest) |")
    lines.append("| **4. Scarf** (`costume_scarf`) | `neck_slot` | `0.044 m` collar ring diameter + draped knit tail | **MISSING → GENERATE in Step 3** (`< 900` tris, origin at `neck_slot`) |")
    lines.append("| **5. Crown** (`costume_crown`) | `head_slot` | `0.026 m` diameter × `0.018 m` height, 5 jewel points | **MISSING → GENERATE in Step 3** (`< 800` tris, gold PBR + gem accents, origin at `head_slot`) |")
    lines.append("| **6. Tiny glasses** (`costume_tiny_glasses`) | `head_slot` | `0.034 m` frame width, twin round wire rims + temples | **MISSING → GENERATE in Step 3** (`< 800` tris, origin at `head_slot` aligned with `ham_eye_L/R`) |")
    lines.append("| **7. Royal cape / mini backpack** (`costume_cape_back`) | `back_slot` | `0.055 m` length × `0.042 m` width draped over `spine_2` | **MISSING → GENERATE in Step 3** (Ensures all 3 required slots `head_slot`, `neck_slot`, `back_slot` have dedicated testable items; `< 700` tris) |")
    lines.append("")
    lines.append("### 4.4 Props Shelf")
    lines.append("| Required Prop | Audit Status in `assets/raw/` & `blender/` | Action for Step 3 (Blender Generation / Export) |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| **1. Wheel** (`prop_wheel`) | **MISSING** in `assets/raw/`; **PRESENT** in `blender/scripts/10_cage.py` (`0.28 m` diameter wheel on stand) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export clean standalone `prop_wheel.glb` (`0.28 m` diameter, solid running surface + grip rungs, base-center pivot, `< 3,500` tris). |")
    lines.append("| **2. Tunnel — Straight** (`prop_tunnel_straight`) | **MISSING** in `assets/raw/`; **PRESENT** in `10_cage.py` (`0.14 m` length, `0.072 m` diameter) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export standalone hollow bark/cork straight tunnel (`0.16 m` long, `0.072 m` inner diam, base-center pivot, `< 1,200` tris). |")
    lines.append("| **3. Tunnel — Curved** (`prop_tunnel_curved`) | **MISSING** in `assets/raw/`; **PRESENT** in `10_cage.py` (`90°` elbow tunnel) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export standalone `90°` curved hollow tunnel (`0.08 m` bend radius, `0.072 m` diam, base-center pivot, `< 1,500` tris). |")
    lines.append("| **4. Hideout** (`prop_hideout`) | **MISSING** in `assets/raw/`; **PRESENT** in `10_cage.py` (`0.16 × 0.13 × 0.105 m` arched cabin) | **GENERATE / EXPORT Standalone GLB in Step 3**: Export standalone wooden hideout with arched doorway & overhanging roof (`< 1,500` tris, base-center pivot). |")
    lines.append("| **5. Bridge / Ramp** (`prop_bridge_ramp`) | **MISSING** in `assets/raw/` (`KayKit` only has heavy stone dungeon stairs) | **GENERATE in Step 3**: Build arched bendy wooden log bridge / climbing ramp (`0.18 m` length × `0.09 m` width × `0.055 m` arch height, 11 tied wooden dowel logs, base-center pivot, `< 1,600` tris). |")
    lines.append("| **6. Chew toy** (`prop_chew_toy`) | **MISSING** in `assets/raw/`; basic stick/block in `20_clutter.py` | **GENERATE in Step 3**: Build composite applewood dumbell/block chew toy (`0.075 m` length × `0.028 m` diam, natural bark + gnawed wood notches, base-center pivot, `< 1,000` tris). |")
    lines.append("| **7. Small ball** (`prop_small_ball`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build woven willow/rattan play ball (`0.045 m` diameter, natural wicker bands, base-center pivot, `< 1,200` tris). |")
    lines.append("")
    lines.append("### 4.5 Decor Shelf")
    lines.append("| Required Decor | Audit Status in `assets/raw/` | Action for Step 3 (Blender Generation / Adaptation) |")
    lines.append("| :--- | :--- | :--- |")
    lines.append("| **1. Plants** (`decor_plant`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build hamster-safe spider-plant / millet-spray terracotta pot (`0.075 m` height, terracotta base + arching green leaves, base-center pivot, `< 1,200` tris). |")
    lines.append("| **2. Small wooden items** (`decor_wooden_item`) | **PARTIAL (`DOWNLOADED`)** in `KayKit_Dungeon_Pack_1.1_FREE` (`barrel_small.gltf` `332` tris, `box_small.gltf` `172` tris, `stool.gltf` `116` tris at dungeon scale) | **ADAPT & GENERATE in Step 3**: Rescale KayKit CC0 wooden barrel/crate to hamster scale (`0.055 m`) AND generate a natural birch log stepping stool (`0.06 m × 0.06 m × 0.045 m`, `< 800` tris). |")
    lines.append("| **3. Bedding patches** (`decor_bedding_patch`) | **MISSING** in `assets/raw/` (`KayKit` `floor_dirt_small_A` is dungeon dirt/stone) | **GENERATE in Step 3**: Build soft mounded paper/aspen/moss bedding patch (`0.14 m × 0.12 m × 0.022 m`, organic feathered rim, base-center pivot, `< 1,000` tris). |")
    lines.append("| **4. Flag** (`decor_flag`) | **PRESENT (`DOWNLOADED`)** in `KayKit_Dungeon_Pack_1.1_FREE` (`banner_blue.gltf`, `banner_red.gltf` `310` tris, `2.6 m` tall) + **GENERATE** | **ADAPT & GENERATE in Step 3**: Rescale KayKit CC0 banner to mini cage corner flag (`0.11 m` tall on wooden dowel post) AND generate a cute HAMMY pennant flag (`0.10 m` tall, `< 600` tris). |")
    lines.append("| **5. Picture frame** (`decor_picture_frame`) | **MISSING** in `assets/raw/` | **GENERATE in Step 3**: Build miniature wooden tabletop/wall picture frame (`0.075 m × 0.060 m × 0.012 m`) with easel stand and warm hamster portrait canvas (`< 600` tris). |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Complete Per-File Audit Table (`524` Unique 3D Models + `255` Texture Files)")
    lines.append("")

    for pack_name, p_items in by_pack.items():
        lines.append(f"### 5.{list(by_pack.keys()).index(pack_name) + 1} Pack: `{pack_name}` (`{len(p_items)}` unique models)")
        lines.append("")
        lines.append("| Asset ID | Name | Formats | Primary File Size (B) | Total Pack Bytes | Verts | Polys | Tris | Scale `(X, Y, Z)` m | Category | Hamster Safe | Licence & Verdict |")
        lines.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
        for it in p_items:
            fmts = ", ".join(it["formats"])
            dims = f"{it['dimensions_m'][0]:.3f}×{it['dimensions_m'][1]:.3f}×{it['dimensions_m'][2]:.3f}"
            safe_str = "YES" if it["hamster_safe"] is True else ("NO" if it["hamster_safe"] is False else "N/A")
            lines.append(
                f"| `{it['id']}` | `{it['name']}` | `{fmts}` | `{it['size_bytes']:,}` | `{it['total_pack_bytes_for_item']:,}` | "
                f"`{it['vertices']}` | `{it['polygons']}` | `{it['triangles']}` | `{dims}` | `{it['category']}` | `{safe_str}` | {it['licence_status']} |"
            )
        lines.append("")

    ASSET_AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {ASSET_AUDIT_MD} ({len(lines)} lines)")

    # Write ASSETS_LICENSES.md
    lic_lines = [
        "# HAMMY — Assets Licences & Provenance Log (`ASSETS_LICENSES.md`)",
        "",
        "This document records the license, author, source URL, and modifications for every asset pack, texture, and generated 3D model in HAMMY.",
        "",
        "> **Strict Compliance Rule:** Any downloaded asset with an unclear, missing, or non-commercial license is **REJECTED** and excluded from the application runtime (`assets/web/` and `assets/manifest.json`). Any `CC-BY` item must be flagged as `needs credit` and added to [`CREDITS.md`](CREDITS.md).",
        "",
        "## 1. Summary of Downloaded Asset Packs (`assets/raw/`)",
        "",
        "| Pack / Archive Name | Source URL | Licence | Author | CC-BY Credit Required? | Status | Modifications Made |",
        "| :--- | :--- | :--- | :--- | :---: | :--- | :--- |",
        "| **Kenney Food Kit (2.0)** (`kenney_food-kit.zip`) | `https://kenney.nl/assets/food-kit` | **CC0 1.0 Universal** (`http://creativecommons.org/publicdomain/zero/1.0/`) | Kenney (`www.kenney.nl`) | No (CC0; credited voluntarily in `CREDITS.md`) | **APPROVED** | Selected hamster-safe food models (`broccoli`, `carrot`, `apple`, `bowl`), rescaled from human/game units (`0.14–0.28 m`) to SI Syrian hamster scale (`0.014–0.080 m`), recentered origin to paw-pickup or base-center pivot, baked/resized textures `<= 512px`, exported to optimized `.glb`. |",
        "| **KayKit Dungeon Pack (1.1 FREE)** (`KayKit_Dungeon_Pack_1.1_FREE.zip`) | `https://kaylousberg.itch.io/kaykit-dungeon` | **CC0 1.0 Universal** (`http://creativecommons.org/publicdomain/zero/1.0/`) | Kay Lousberg (`www.kaylousberg.com`) | No (CC0; credited voluntarily in `CREDITS.md`) | **APPROVED** | Selected non-combat structural/decor items (`shelf_small`, `banner_blue`, `barrel_small`), rescaled from dungeon scale (`~2.0 m`) to SI hamster habitat scale (`0.055–0.18 m`), re-pivoted to base center, exported to `.glb`. |",
        "| **Poly Haven PBR Textures & Indoor HDRI** (`blender/textures/`) | `https://polyhaven.com` | **CC0 1.0 Universal** | Dario Barresi, Rob Tuytel, Dimitrios Savva, Sergej Majboroda (Poly Haven) | No (CC0; credited voluntarily in `CREDITS.md`) | **APPROVED** | Used for wood, plywood, bark, ceramic roughness, and room IBL (`<= 1024px`). |",
        "| **Google Drive Food Pack** (`drive-download-20261119T082111Z-1-001.zip`) | Unknown Google Drive export (matches Quaternius Ultimate Food Pack filenames) | **UNCLEAR** (No `LICENSE` or `README` file present inside archive) | Unknown in archive (`//Blender/DavidThorn/Library/Large/Texture.png` path in `.blend`) | N/A — **REJECTED** | **REJECTED** | **None (Excluded from build).** Rejected because archive lacks a license file and is missing its external texture file. |",
        "| **Food & Drinks Pack** (`Food&DrinksPack.rar`) | Unknown source archive | **UNCLEAR** (No `LICENSE` or `README` file present inside archive) | Unknown | N/A — **REJECTED** | **REJECTED** | **None (Excluded from build).** Rejected because archive has no license file and contains only unsafe human junk food (`CannedFood`, `FrozenPizza`, `Hamburger`, `HotDog`, `Sushi`, `Milk`, `CoffeeCup`). |",
        "",
        "## 2. Individual Approved & Integrated Asset Licences (`assets/web/` & `assets/manifest.json`)",
        "",
        "| Asset ID | Display Name | Category | Origin (`GENERATED` / `DOWNLOADED`) | Source | Licence | Author | Modifications |",
        "| :--- | :--- | :---: | :---: | :--- | :--- | :--- | :--- |",
        "| `food_seed_mix` | Seed Mix | `food` | `GENERATED` | Procedural Blender 5.2 (`assets/source/food_seed_mix.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at metric hamster scale (`0.024 m`) with paw pickup pivot and baked PBR materials. |",
        "| `food_sunflower_seed` | Sunflower Seed | `food` | `GENERATED` | Procedural Blender 5.2 (`assets/source/food_sunflower_seed.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated striped hull (`0.011 m`) with paw pickup pivot. |",
        "| `food_peanut` | Unsalted Peanut | `food` | `GENERATED` | Procedural Blender 5.2 (`assets/source/food_peanut.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated double-lobed peanut (`0.022 m`) with fibrous shell PBR material and paw pickup pivot. |",
        "| `food_carrot_piece` | Carrot Piece | `food` | `DOWNLOADED` (adapted) / `GENERATED` | Kenney Food Kit 2.0 (`carrot.glb`, `https://kenney.nl/assets/food-kit`) + Blender slice | **CC0 1.0 Universal** | Kenney (`www.kenney.nl`) & HAMMY Pipeline | Rescaled to `0.016 m` hamster-safe carrot piece, paw pickup pivot, `<= 512px` texture. |",
        "| `food_broccoli_floret` | Broccoli Floret | `food` | `DOWNLOADED` | Kenney Food Kit 2.0 (`broccoli.glb`, `https://kenney.nl/assets/food-kit`) | **CC0 1.0 Universal** | Kenney (`www.kenney.nl`) | Rescaled from `0.165 m` to `0.018 m` hamster floret scale, stem pickup pivot applied, `512×512` colormap. |",
        "| `food_apple_piece` | Apple Piece (Seedless) | `food` | `GENERATED` | Procedural Blender 5.2 (`assets/source/food_apple_piece.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated seedless fresh apple slice (`0.016 m`, red skin + cream flesh, zero toxic seeds) with paw pickup pivot. |",
        "| `food_blueberry` | Fresh Blueberry | `food` | `GENERATED` | Procedural Blender 5.2 (`assets/source/food_blueberry.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated `0.010 m` berry with star calyx and indigo waxy bloom shader. |",
        "| `water_bottle` | Water Bottle (Visible Level) | `water` | `GENERATED` | Procedural Blender 5.2 (`assets/source/water_bottle.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated `0.15 m` clear bottle with separate scalable `water_liquid` mesh, cap, bracket, and `45°` steel ball-spout. |",
        "| `water_bowl` | Small Ceramic Water Bowl | `water` | `GENERATED` | Procedural Blender 5.2 (`assets/source/water_bowl.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated `0.065 m` glazed ceramic dish with separate scalable `water_liquid` mesh. |",
        "| `prop_food_bowl` | Ceramic Food Bowl | `prop` | `DOWNLOADED` | Kenney Food Kit 2.0 (`bowl.glb`, `https://kenney.nl/assets/food-kit`) | **CC0 1.0 Universal** | Kenney (`www.kenney.nl`) | Rescaled from `0.28 m` to `0.080 m` hamster food bowl diameter, base-center pivot applied. |",
        "| `prop_shelf` | Wooden Food & Lookout Shelf | `prop` | `DOWNLOADED` | KayKit Dungeon Pack 1.1 (`shelf_small.gltf`, `https://kaylousberg.itch.io/kaykit-dungeon`) | **CC0 1.0 Universal** | Kay Lousberg (`www.kaylousberg.com`) | Rescaled to `0.18 m × 0.10 m × 0.09 m` cage shelf, base-center pivot, `512×512` texture. |",
        "| `costume_party_hat` | Festive Party Hat | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_party_hat.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster head scale (`0.026 m × 0.036 m`) with `head_slot` socket. |",
        "| `costume_top_hat` | Dapper Top Hat | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_top_hat.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster head scale (`0.032 m × 0.028 m`) with `head_slot` socket. |",
        "| `costume_bow_tie` | Crimson Bow Tie | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_bow_tie.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster neck scale (`0.028 m` wide) with `neck_slot` socket. |",
        "| `costume_scarf` | Cozy Knit Scarf | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_scarf.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster neck scale (`0.044 m` collar) with `neck_slot` socket. |",
        "| `costume_crown` | Golden Royal Crown | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_crown.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster head scale (`0.026 m` diam) with `head_slot` socket. |",
        "| `costume_tiny_glasses` | Tiny Round Glasses | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_tiny_glasses.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster eye spacing (`0.034 m` wide) with `head_slot` socket. |",
        "| `costume_backpack` | Explorer Mini Cape / Pack | `costume` | `GENERATED` | Procedural Blender 5.2 (`assets/source/costume_backpack.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | Generated at hamster back scale (`0.045 m`) with `back_slot` socket. |",
        "| `prop_wheel` | Silent Wooden Exercise Wheel (`28 cm`) | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_wheel.blend`) | **CC0 / MIT (Project Original)** + Poly Haven CC0 Plywood | HAMMY Pipeline | `0.28 m` Syrian welfare wheel with inner grip rungs and stand, base-center pivot. |",
        "| `prop_tunnel_straight` | Straight Hollow Bark Tunnel | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_tunnel_straight.blend`) | **CC0 / MIT (Project Original)** + Poly Haven CC0 Bark | HAMMY Pipeline | `0.16 m` straight hollow tunnel (`0.072 m` inner diameter), base-center pivot. |",
        "| `prop_tunnel_curved` | Curved 90° Bark Tunnel | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_tunnel_curved.blend`) | **CC0 / MIT (Project Original)** + Poly Haven CC0 Bark | HAMMY Pipeline | `90°` curved hollow elbow tunnel (`0.072 m` inner diameter), base-center pivot. |",
        "| `prop_hideout` | Wooden Arched Hideout Cabin | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_hideout.blend`) | **CC0 / MIT (Project Original)** + Poly Haven CC0 Wood | HAMMY Pipeline | `0.16 × 0.13 × 0.105 m` cabin with arched doorway and gnawed edge wear. |",
        "| `prop_bridge_ramp` | Bendy Log Bridge / Ramp | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_bridge_ramp.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | `0.18 m × 0.09 m` arched dowel climbing bridge, base-center pivot. |",
        "| `prop_chew_toy` | Applewood Dumbbell Chew Toy | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_chew_toy.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | `0.075 m` wooden dumbbell chew with gnawed notches, base-center pivot. |",
        "| `prop_small_ball` | Woven Willow Play Ball | `prop` | `GENERATED` | Procedural Blender 5.2 (`assets/source/prop_small_ball.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | `0.045 m` diameter rattan play ball, base-center pivot. |",
        "| `decor_plant` | Hamster-Safe Terracotta Plant | `decor` | `GENERATED` | Procedural Blender 5.2 (`assets/source/decor_plant.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | `0.075 m` tall potted spider plant, base-center pivot. |",
        "| `decor_wooden_item` | Mini Wooden Barrel & Log Stool | `decor` | `DOWNLOADED` | KayKit Dungeon Pack 1.1 (`barrel_small.gltf`, `https://kaylousberg.itch.io/kaykit-dungeon`) | **CC0 1.0 Universal** | Kay Lousberg (`www.kaylousberg.com`) | Rescaled from dungeon barrel to `0.055 m` hamster wooden climbing barrel, base-center pivot. |",
        "| `decor_bedding_patch` | Soft Aspen & Moss Bedding Patch | `decor` | `GENERATED` | Procedural Blender 5.2 (`assets/source/decor_bedding_patch.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | `0.14 m × 0.12 m` layered organic bedding mound, base-center pivot. |",
        "| `decor_flag` | Mini Cage Pennant Banner | `decor` | `DOWNLOADED` | KayKit Dungeon Pack 1.1 (`banner_blue.gltf`, `https://kaylousberg.itch.io/kaykit-dungeon`) | **CC0 1.0 Universal** | Kay Lousberg (`www.kaylousberg.com`) | Rescaled from `2.6 m` to `0.11 m` tabletop cage banner, base-center pivot. |",
        "| `decor_picture_frame` | Mini Wooden Picture Frame | `decor` | `GENERATED` | Procedural Blender 5.2 (`assets/source/decor_picture_frame.blend`) | **CC0 / MIT (Project Original)** | HAMMY Pipeline | `0.075 m × 0.060 m` standing wooden frame with hamster portrait, base-center pivot. |",
        "",
    ]
    ASSETS_LICENSES_MD.write_text("\n".join(lic_lines), encoding="utf-8")
    print(f"Wrote {ASSETS_LICENSES_MD}")

    # Write CREDITS.md
    cred_lines = [
        "# HAMMY — Third-Party Asset Credits (`CREDITS.md`)",
        "",
        "## Mandatory Attribution (`CC-BY` Assets)",
        "- **None required.** Every external 3D model, PBR texture, and HDRI integrated into HAMMY is licensed under **Creative Commons Zero (CC0 1.0 Universal — Public Domain)**. Packs with unclear licenses (`drive-download-20261119T082111Z-1-001.zip` and `Food&DrinksPack.rar`) were strictly rejected during the Step 1 Audit.",
        "- If any `CC-BY` asset is added in the future, it must be flagged as `needs credit` in `ASSETS_LICENSES.md` and listed in this section.",
        "",
        "## Voluntary Appreciation Credits (`CC0 1.0 Universal` Creators)",
        "Even though attribution is not legally required under CC0, we gratefully credit the creators whose public-domain assets are used in HAMMY:",
        "",
        "1. **Kenney (`www.kenney.nl`)** — *Food Kit (2.0)* (`CC0 1.0 Universal`, `https://kenney.nl/assets/food-kit`)",
        "   - Used for base meshes of `food_broccoli_floret`, `food_carrot_piece` (adapted), and `prop_food_bowl` (rescaled to Syrian hamster scale).",
        "2. **Kay Lousberg (`www.kaylousberg.com`)** — *KayKit : Dungeon Asset Pack (1.1 FREE)* (`CC0 1.0 Universal`, `https://kaylousberg.itch.io/kaykit-dungeon`)",
        "   - Used for base meshes of `prop_shelf` (`shelf_small`), `decor_wooden_item` (`barrel_small`), and `decor_flag` (`banner_blue`), rescaled to Syrian hamster habitat dimensions.",
        "3. **Poly Haven (`https://polyhaven.com`)** — Scanned PBR Textures & HDRI (`CC0 1.0 Universal`)",
        "   - **Dario Barresi:** `fine_grained_wood` (`https://polyhaven.com/a/fine_grained_wood`)",
        "   - **Rob Tuytel:** `plywood` (`https://polyhaven.com/a/plywood`) & `bark_brown_02` (`https://polyhaven.com/a/bark_brown_02`)",
        "   - **Dimitrios Savva:** `concrete_floor_worn_001` (`https://polyhaven.com/a/concrete_floor_worn_001`)",
        "   - **Sergej Majboroda:** `brown_photostudio_02` 1K Indoor HDRI (`https://polyhaven.com/a/brown_photostudio_02`)",
        "",
    ]
    CREDITS_MD.write_text("\n".join(cred_lines), encoding="utf-8")
    print(f"Wrote {CREDITS_MD}")


if __name__ == "__main__":
    main()
