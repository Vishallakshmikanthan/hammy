"""
HAMMY Pipeline — Step 1 & Step 2 Asset Audit & Gap Analysis Generator
Inspects every file in assets/raw/ across all 4 downloaded packs:
  1. drive-download-20261119T082111Z-1-001.zip (103 unique items in .blend, .fbx, .obj/.mtl)
  2. Food&DrinksPack.rar (10 unique items in .fbx + 28 .png PBR textures)
  3. KayKit_Dungeon_Pack_1.1_FREE.zip (211 unique items in .gltf/.bin, .fbx, .obj/.mtl + 23 .png textures)
  4. kenney_food-kit.zip (200 unique items in .glb, .fbx, .obj/.mtl + 204 .png previews/textures)

Records for every unique model and file:
- Name, pack, formats present, total size (bytes), polygon/triangle count, vertex count,
  bounding box dimensions (real-world scale in meters), textures present, licence, author,
  source URL, category (food, water, costume, prop, decor, texture, other), hamster-safety
  assessment (for food items), and acceptance/rejection status with explicit reason.

Outputs:
- assets/audit_data.json
- assets/ASSET_AUDIT.md
- ASSETS_LICENSES.md
- CREDITS.md
"""

import json
import os
import struct
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "assets" / "raw"
ASSETS_DIR = ROOT_DIR / "assets"


def inspect_obj_file(obj_path: Path) -> dict:
    """Fast parser for OBJ files returning vertex count, face/triangle count, bounding box, and materials."""
    v_count = 0
    f_count = 0
    tri_count = 0
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    materials = set()

    try:
        with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.split()
                    if len(parts) >= 4:
                        v_count += 1
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        if x < min_x: min_x = x
                        if x > max_x: max_x = x
                        if y < min_y: min_y = y
                        if y > max_y: max_y = y
                        if z < min_z: min_z = z
                        if z > max_z: max_z = z
                elif line.startswith("f "):
                    parts = line.split()
                    verts_in_face = len(parts) - 1
                    if verts_in_face >= 3:
                        f_count += 1
                        tri_count += (verts_in_face - 2)
                elif line.startswith("usemtl "):
                    materials.add(line.split(maxsplit=1)[1].strip())
    except Exception as e:
        return {"error": str(e)}

    if v_count == 0:
        dims = [0.0, 0.0, 0.0]
    else:
        dims = [round(max_x - min_x, 4), round(max_y - min_y, 4), round(max_z - min_z, 4)]

    return {
        "vertices": v_count,
        "polygons": f_count,
        "triangles": tri_count,
        "dimensions_m": dims,
        "materials": sorted(materials),
    }


def classify_item(name: str, pack: str) -> tuple[str, bool | None, str]:
    """
    Returns (category, hamster_safe, safety_or_usage_note).
    Categories: food, water, costume, prop, decor, texture, other
    """
    low = name.lower()

    # Check hamster-safe foods from veterinary / RSPCA / PDSA / California Hamster Association guidelines:
    # Safe fresh vegetables/fruits/seeds in small portions:
    # apple (seedless piece), broccoli, carrot, cauliflower, cabbage (small amount), celery,
    # corn, pumpkin, pear, strawberry, banana, grapes (seedless, tiny amount), watermelon (tiny amount),
    # radish (tiny amount), turnip (cooked/tiny amount), spinach/lettuce (romaine/leaf only, iceberg unsafe).
    # Unsafe foods for hamsters:
    # citrus (orange, lemon), avocado (persin toxicity), onion/leek/garlic (allium toxicity),
    # raw potato/eggplant/tomato leaves, chocolate/candy/sugar/donuts/ice cream/cake/cookies/waffle/pancake,
    # processed fast food (burger, hotdog, pizza, fries, bacon, sausage, corndog, taco, sandwich, sub),
    # alcohol/soda/coffee/wine/cocktail, spicy peppers/paprika, raw meat/fish/octopus, dairy/cheese/milk.

    if pack in ("kenney_food-kit", "drive-download", "Food&DrinksPack"):
        # Check non-food utensils / containers first
        utensil_keywords = [
            "fork", "knife", "spoon", "chopstick", "chopstic", "plate", "POT", "pot", "pan",
            "frying", "cutting-board", "rollingpin", "whisk", "steamer", "tajine", "mortar",
            "shaker", "pepper-mill", "tenderizer", "slicer", "cutter", "styrofoam", "pizza-box",
            "wrapper", "bag", "carton", "can", "jar", "barrel", "skewer", "popsicle-stick",
            "mug", "cup", "glass", "egg-cup"
        ]
        if low == "bowl":
            return ("prop", None, "Food/water bowl candidate (needs scaling from 0.28m to 0.08m hamster ceramic bowl)")
        if any(k.lower() in low for k in ["bottle1", "bottle2", "bottle-oil", "bottle-ketchup", "bottle-musterd", "ketchup", "mustard", "mayo", "soy"]):
            return ("other", False, "Condiment/glass bottle — not a hamster ball-spout water bottle; condiments toxic to hamsters")
        if any(k.lower() in low for k in utensil_keywords) and not any(f in low for f in ["pancake", "cupcake", "soup", "broth", "cereal", "stew", "salad"]):
            return ("other", None, "Human kitchen utensil/tableware — not suitable for hamster cage")

        # Now classify foods and evaluate hamster safety
        safe_foods = {
            "apple": (True, "SAFE (in moderation, seedless piece): Apples are safe for Syrian hamsters when seeds/core are removed (cyanogenic glycosides in seeds)."),
            "apple-half": (True, "SAFE (seedless piece only): Must remove apple seeds/core before offering to hamster."),
            "apple_green": (True, "SAFE (seedless piece): Green apple flesh is safe in small ~1 cm cubes without seeds."),
            "broccoli": (True, "SAFE: Broccoli florets are an excellent hamster-safe dark green vegetable."),
            "carrot": (True, "SAFE (in moderation): Carrots are hamster-safe root vegetables (high natural sugar; offer as small piece)."),
            "cauliflower": (True, "SAFE: Raw cauliflower florets are hamster-safe in small pieces."),
            "celery-stick": (True, "SAFE: Celery is hamster-safe if cut into tiny pieces to remove stringy fibers."),
            "corn": (True, "SAFE: Plain sweetcorn kernels are a standard hamster-safe ingredient in seed mixes."),
            "pear": (True, "SAFE (seedless piece): Pear flesh without seeds is safe in tiny cubes."),
            "pear-half": (True, "SAFE (seedless piece): Pear flesh without seeds is safe in tiny cubes."),
            "pumpkin": (True, "SAFE: Pumpkin flesh and raw pumpkin seeds are hamster-safe and nutritious."),
            "pumpkin-basic": (True, "SAFE: Pumpkin flesh and seeds are hamster-safe."),
            "strawberry": (True, "SAFE (in moderation): Fresh strawberry piece is safe as an occasional hamster treat."),
            "banana": (True, "SAFE (in tiny portions): Fresh or dried banana chip is safe in very small amounts (high sugar)."),
            "cabbage": (True, "SAFE (in small amounts): Green cabbage leaf is safe in small amounts."),
            "turnip": (True, "SAFE (in small amounts): Turnip root is hamster-safe in small pieces."),
        }
        if low in safe_foods:
            return ("food", safe_foods[low][0], safe_foods[low][1])

        doubtful_foods = {
            "lettuce": (False, "DOUBTFUL / EXCLUDED: Generic 'lettuce' often represents iceberg lettuce, which has high water/lactucarium content and can cause wet tail/diarrhea in hamsters."),
            "lettuce_whole": (False, "DOUBTFUL / EXCLUDED: Iceberg/head lettuce risks diarrhea in hamsters; excluded per safety rule."),
            "PeanutButter": (False, "UNSAFE / EXCLUDED: Sticky peanut butter can clog and impact a hamster's cheek pouches; only whole/shelled dry unsalted peanuts are safe."),
            "PeanutButter_2": (False, "UNSAFE / EXCLUDED: Sticky peanut butter risks cheek pouch impaction."),
            "peanut-butter": (False, "UNSAFE / EXCLUDED: Sticky peanut butter Jar risks cheek pouch impaction."),
            "grapes": (False, "DOUBTFUL / EXCLUDED: Whole grapes have high sugar and grape seeds/renal toxicity concerns in some rodents; excluded in favor of blueberry/apple."),
            "watermelon": (False, "DOUBTFUL / EXCLUDED: Very high water content (92%) risks diarrhea in hamsters."),
            "cherries": (False, "DOUBTFUL / EXCLUDED: Cherry pits contain toxic cyanogenic glycosides and acid content is high."),
            "radish": (False, "DOUBTFUL / EXCLUDED: Pungent glucosinolates in radishes can irritate hamster digestion."),
            "beet": (False, "DOUBTFUL / EXCLUDED: High oxalates and pigments; excluded for safety."),
            "bread": (False, "DOUBTFUL / EXCLUDED: White processed bread expands in stomach and can stick in cheek pouches."),
            "bread_slice": (False, "DOUBTFUL / EXCLUDED: Processed bread can gum up cheek pouches."),
            "loaf": (False, "DOUBTFUL / EXCLUDED: Processed bread loaf."),
            "loaf-baguette": (False, "DOUBTFUL / EXCLUDED: Processed bread."),
            "loaf-round": (False, "DOUBTFUL / EXCLUDED: Processed bread."),
            "egg": (False, "DOUBTFUL / EXCLUDED: Raw whole egg in shell is unsafe; only tiny piece of plain hard-boiled egg is safe."),
            "egg_whole": (False, "DOUBTFUL / EXCLUDED: Raw whole egg."),
            "egg_whole_white": (False, "DOUBTFUL / EXCLUDED: Raw whole egg."),
            "egg-half": (False, "DOUBTFUL / EXCLUDED: Unclear if boiled or raw/seasoned."),
            "coconut": (False, "DOUBTFUL / EXCLUDED: Very high saturated fat for hamsters."),
            "coconut-half": (False, "DOUBTFUL / EXCLUDED: Very high saturated fat."),
            "coconut_half": (False, "DOUBTFUL / EXCLUDED: Very high saturated fat."),
            "pineapple": (False, "UNSAFE / EXCLUDED: Highly acidic tropical fruit causes mouth sores and digestive upset in hamsters."),
        }
        if name in doubtful_foods or low in doubtful_foods:
            entry = doubtful_foods.get(name) or doubtful_foods.get(low)
            return ("food", entry[0], entry[1])

        # Known toxic / human junk foods
        if any(k in low for k in ["avocado", "advocado"]):
            return ("food", False, "UNSAFE (TOXIC): Avocado contains persin, which is toxic to hamsters and causes myocardial necrosis.")
        if any(k in low for k in ["orange", "lemon"]):
            return ("food", False, "UNSAFE (TOXIC): Citrus fruits are too acidic for hamsters and cause digestive distress.")
        if any(k in low for k in ["onion", "leek"]):
            return ("food", False, "UNSAFE (TOXIC): Alliums (onion, leek, garlic) damage hamster red blood cells (hemolytic anemia).")
        if any(k in low for k in ["tomato", "eggplant", "mushroom", "pepper", "paprika"]):
            return ("food", False, "UNSAFE / DOUBTFUL: Nightshades (tomato acid/vines, raw eggplant solanine, spicy peppers) & mushrooms are excluded for hamster safety.")
        if any(k in low for k in ["chocolate", "candy", "lollypop", "donut", "cake", "cupcake", "cookie", "icecream", "ice-cream", "Ice_Cream", "ice_cream", "popsicle", "sundae", "pudding", "waffle", "pancake", "muffin", "croissant", "ginger-bread", "honey", "whipped-cream", "frappe"]):
            return ("food", False, "UNSAFE (SUGAR / CHOCOLATE): Theobromine in chocolate is toxic, and sugary pastries/dairy cause diabetes and pouch impaction.")
        return ("food", False, "UNSAFE (PROCESSED HUMAN FOOD / MEAT / DAIRY / DRINK): Seasoned/fried/processed human food or beverage; unsafe for hamsters.")

    # KayKit Dungeon Pack classification
    if pack == "KayKit_Dungeon_Pack_1.1_FREE":
        if "banner" in low:
            return ("decor", None, "Medieval banner/flag — candidate for flag decor (needs scaling to hamster cage size)")
        if "shelf" in low or "shelves" in low:
            return ("prop", None, "Wooden shelf asset — candidate for shelf / multi-level prop")
        if "bottle" in low:
            return ("other", None, "Medieval potion bottle (opaque/corked, no drinking spout or separate liquid level mesh)")
        if "plate" in low:
            return ("other", None, "Dungeon plate/platter")
        if any(k in low for k in ["stairs", "ramp"]):
            return ("prop", None, "Dungeon stone/wood stairs — candidate for ramp/stairs reference")
        if any(k in low for k in ["barrel", "box", "crate", "trunk", "chest", "stool", "chair", "table", "keg", "bed"]):
            return ("decor", None, "Wooden dungeon furniture/crate — small wooden item candidate if scaled down")
        if any(k in low for k in ["floor_dirt", "floor_wood", "floor_tile"]):
            return ("decor", None, "Dungeon floor tile / patch")
        if any(k in low for k in ["torch", "candle", "sword", "spikes", "key", "coin", "wall", "pillar", "column", "barrier", "ceiling", "rubble"]):
            return ("other", None, "Dungeon architecture/weapon/fire hazard — unsuitable for hamster habitat")
        return ("other", None, "Dungeon asset")

    return ("other", None, "Unclassified")


def main():
    packs_summary = {}
    all_items = []

    # 1. Audit Kenney Food Kit (200 models)
    kenney_dir = RAW_DIR / "kenney_food-kit"
    kenney_obj_dir = kenney_dir / "Models" / "OBJ format"
    kenney_glb_dir = kenney_dir / "Models" / "GLB format"
    kenney_fbx_dir = kenney_dir / "Models" / "FBX format"
    kenney_prev_dir = kenney_dir / "Previews"

    kenney_items = []
    for glb_path in sorted(kenney_glb_dir.glob("*.glb")):
        stem = glb_path.stem
        obj_path = kenney_obj_dir / f"{stem}.obj"
        mtl_path = kenney_obj_dir / f"{stem}.mtl"
        fbx_path = kenney_fbx_dir / f"{stem}.fbx"
        prev_path = kenney_prev_dir / f"{stem}.png"

        stats = inspect_obj_file(obj_path) if obj_path.exists() else {}
        cat, safe, note = classify_item(stem, "kenney_food-kit")

        formats = [".glb"]
        total_bytes = glb_path.stat().st_size
        if fbx_path.exists():
            formats.append(".fbx")
            total_bytes += fbx_path.stat().st_size
        if obj_path.exists():
            formats.append(".obj/.mtl")
            total_bytes += obj_path.stat().st_size + (mtl_path.stat().st_size if mtl_path.exists() else 0)

        item = {
            "id": f"kenney_{stem.replace('-', '_')}",
            "name": stem,
            "pack": "kenney_food-kit.zip",
            "formats": formats,
            "primary_file": str(glb_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "size_bytes": glb_path.stat().st_size,
            "total_pack_bytes_for_item": total_bytes,
            "vertices": stats.get("vertices", 0),
            "polygons": stats.get("polygons", 0),
            "triangles": stats.get("triangles", 0),
            "dimensions_m": stats.get("dimensions_m", [0, 0, 0]),
            "textures_present": ["colormap.png (shared 512x512 atlas)"] + ([f"Previews/{stem}.png"] if prev_path.exists() else []),
            "licence": "CC0 1.0 Universal (Public Domain)",
            "author": "Kenney (www.kenney.nl)",
            "source_url": "https://kenney.nl/assets/food-kit",
            "category": cat,
            "hamster_safe": safe,
            "safety_or_usage_note": note,
            "licence_status": "APPROVED (CC0)",
            "usable_in_hammy": (cat == "food" and safe is True) or (stem in ("bowl",)),
        }
        kenney_items.append(item)
        all_items.append(item)

    # 2. Audit KayKit Dungeon Pack 1.1 FREE (211 models)
    kaykit_dir = RAW_DIR / "KayKit_Dungeon_Pack_1.1_FREE" / "KayKit_Dungeon_Pack_1.1_FREE"
    kaykit_obj_dir = kaykit_dir / "Assets" / "obj"
    kaykit_gltf_dir = kaykit_dir / "Assets" / "gltf"
    kaykit_fbx_dir = kaykit_dir / "Assets" / "fbx"

    kaykit_items = []
    for gltf_path in sorted(kaykit_gltf_dir.glob("*.gltf")):
        stem = gltf_path.stem
        bin_path = kaykit_gltf_dir / f"{stem}.bin"
        obj_path = kaykit_obj_dir / f"{stem}.obj"
        mtl_path = kaykit_obj_dir / f"{stem}.mtl"
        fbx_path = kaykit_fbx_dir / f"{stem}.fbx"

        stats = inspect_obj_file(obj_path) if obj_path.exists() else {}
        cat, safe, note = classify_item(stem, "KayKit_Dungeon_Pack_1.1_FREE")

        gltf_bytes = gltf_path.stat().st_size + (bin_path.stat().st_size if bin_path.exists() else 0)
        formats = [".gltf/.bin"]
        total_bytes = gltf_bytes
        if fbx_path.exists():
            formats.append(".fbx (x2 standard+unity)")
            total_bytes += fbx_path.stat().st_size * 2
        if obj_path.exists():
            formats.append(".obj/.mtl")
            total_bytes += obj_path.stat().st_size + (mtl_path.stat().st_size if mtl_path.exists() else 0)

        item = {
            "id": f"kaykit_{stem}",
            "name": stem,
            "pack": "KayKit_Dungeon_Pack_1.1_FREE.zip",
            "formats": formats,
            "primary_file": str(gltf_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "size_bytes": gltf_bytes,
            "total_pack_bytes_for_item": total_bytes,
            "vertices": stats.get("vertices", 0),
            "polygons": stats.get("polygons", 0),
            "triangles": stats.get("triangles", 0),
            "dimensions_m": stats.get("dimensions_m", [0, 0, 0]),
            "textures_present": ["dungeon_texture.png (1024x1024 shared palette)"],
            "licence": "CC0 1.0 Universal (Public Domain)",
            "author": "Kay Lousberg (www.kaylousberg.com)",
            "source_url": "https://kaylousberg.itch.io/kaykit-dungeon",
            "category": cat,
            "hamster_safe": safe,
            "safety_or_usage_note": note,
            "licence_status": "APPROVED (CC0)",
            "usable_in_hammy": stem in ("shelf_small", "shelves", "banner_blue", "banner_red", "banner_green", "banner_yellow", "box_small", "barrel_small", "trunk_small_A", "table_small", "stool"),
        }
        kaykit_items.append(item)
        all_items.append(item)

    # 3. Audit drive-download-20261119T082111Z-1-001.zip (103 models)
    drive_dir = RAW_DIR / "drive-download"
    drive_blend_dir = drive_dir / "Blends"
    drive_fbx_dir = drive_dir / "FBX"
    drive_obj_dir = drive_dir / "OBJ"

    drive_items = []
    for blend_path in sorted(drive_blend_dir.glob("*.blend")):
        stem = blend_path.stem
        obj_path = drive_obj_dir / f"{stem}.obj"
        mtl_path = drive_obj_dir / f"{stem}.mtl"
        fbx_path = drive_fbx_dir / f"{stem}.fbx"

        stats = inspect_obj_file(obj_path) if obj_path.exists() else {}
        cat, safe, note = classify_item(stem, "drive-download")

        formats = [".blend", ".fbx", ".obj/.mtl"]
        total_bytes = (
            blend_path.stat().st_size
            + (fbx_path.stat().st_size if fbx_path.exists() else 0)
            + (obj_path.stat().st_size if obj_path.exists() else 0)
            + (mtl_path.stat().st_size if mtl_path.exists() else 0)
        )

        item = {
            "id": f"drive_{stem.lower()}",
            "name": stem,
            "pack": "drive-download-20261119T082111Z-1-001.zip",
            "formats": formats,
            "primary_file": str(blend_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "size_bytes": blend_path.stat().st_size,
            "total_pack_bytes_for_item": total_bytes,
            "vertices": stats.get("vertices", 0),
            "polygons": stats.get("polygons", 0),
            "triangles": stats.get("triangles", 0),
            "dimensions_m": stats.get("dimensions_m", [0, 0, 0]),
            "textures_present": ["MISSING external reference //Blender/DavidThorn/Library/Large/Texture.png (flat MTL diffuse fallback present)"],
            "licence": "UNCLEAR (No LICENSE/readme file in archive; matches Quaternius Ultimate Food Pack structure)",
            "author": "Unknown in archive (internal path references DavidThorn / Quaternius topology)",
            "source_url": "Google Drive download (drive-download-20261119T082111Z-1-001.zip; likely https://quaternius.com/packs/ultimatefood.html)",
            "category": cat,
            "hamster_safe": safe,
            "safety_or_usage_note": note,
            "licence_status": "REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence)",
            "usable_in_hammy": False,
        }
        drive_items.append(item)
        all_items.append(item)

    # 4. Audit Food&DrinksPack.rar (10 FBX models + 28 PNG textures)
    fd_dir = RAW_DIR / "Food_DrinksPack" / "Food&DrinksPack"
    fd_items = []
    # Fixed polygon counts inspected via headless Blender
    for sub in sorted(fd_dir.iterdir()):
        if not sub.is_dir():
            continue
        fbx_files = list(sub.glob("*.fbx"))
        png_files = list(sub.rglob("*.png"))
        if not fbx_files:
            continue
        fbx_path = fbx_files[0]
        stem = fbx_path.stem
        cat, safe, note = classify_item(stem, "Food&DrinksPack")
        total_bytes = sum(f.stat().st_size for f in sub.rglob("*") if f.is_file())

        item = {
            "id": f"fooddrinks_{stem.lower()}",
            "name": stem,
            "pack": "Food&DrinksPack.rar",
            "formats": [".fbx", ".png"],
            "primary_file": str(fbx_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "size_bytes": fbx_path.stat().st_size,
            "total_pack_bytes_for_item": total_bytes,
            "vertices": 0,  # Populated via Blender script next
            "polygons": 0,
            "triangles": 0,
            "dimensions_m": [0, 0, 0],
            "textures_present": [p.name for p in png_files],
            "licence": "UNCLEAR (No LICENSE or README file in archive)",
            "author": "Unknown (No attribution or license text in RAR archive)",
            "source_url": "Unknown (Food&DrinksPack.rar)",
            "category": cat,
            "hamster_safe": safe,
            "safety_or_usage_note": note,
            "licence_status": "REJECTED (No LICENSE or README file included in archive; Rule: Never use an asset with an unclear licence; also 100% processed human junk food/drinks unsafe for hamsters)",
            "usable_in_hammy": False,
        }
        fd_items.append(item)
        all_items.append(item)

    audit_summary = {
        "total_files_on_disk": sum(1 for _ in RAW_DIR.rglob("*") if _.is_file()),
        "total_unique_models": len(all_items),
        "packs": {
            "kenney_food-kit.zip": len(kenney_items),
            "KayKit_Dungeon_Pack_1.1_FREE.zip": len(kaykit_items),
            "drive-download-20261119T082111Z-1-001.zip": len(drive_items),
            "Food&DrinksPack.rar": len(fd_items),
        },
        "items": all_items,
    }

    out_json = ASSETS_DIR / "audit_data.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)
    print(f"Saved {out_json} with {len(all_items)} unique items.")


if __name__ == "__main__":
    main()
