"""
Encodes `renders/step5/frames/frame_*.png` into `renders/step5/eating_animation_sequence.mp4`
and builds a labeled 7-stage contact sheet (`renders/step5/eating_sequence_contact_sheet.png`).
"""

from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
RENDER_DIR = ROOT_DIR / "renders" / "step5"
FRAMES_DIR = RENDER_DIR / "frames"
OUT_MP4 = RENDER_DIR / "eating_animation_sequence.mp4"
OUT_SHEET = RENDER_DIR / "eating_sequence_contact_sheet.png"

STAGE_LABELS = [
    ("stage_sit_up.png", "1. sit_up (Rear on haunches)"),
    ("stage_grab_food.png", "2. grab_food (Both front paws)"),
    ("stage_bring_to_mouth.png", "3. bring_to_mouth (Hold at snout)"),
    ("stage_chew_loop.png", "4. chew_loop (4.8 Hz jaw nibble)"),
    ("stage_swallow.png", "5. swallow (Head dip & blink)"),
    ("stage_stuff_cheek.png", "6. stuff_cheek (Pouches bulge 0->0.98)"),
    ("stage_release_idle.png", "7. release_idle (Return with full cheeks)"),
]


def main():
    frames = sorted(FRAMES_DIR.glob("frame_*.png"))
    if not frames:
        raise RuntimeError(f"No frames found in {FRAMES_DIR}")

    first = cv2.imread(str(frames[0]))
    h, w, _ = first.shape

    # Encode MP4 (repeat each of the 32 frames 3x at 24 fps -> 96 frames = 4.0s smooth 24fps video)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(OUT_MP4), fourcc, 12.0, (w, h))
    for idx, fp in enumerate(frames):
        img = cv2.imread(str(fp))
        # Overlay current clip stage label in top-left corner
        frac = idx / max(1, len(frames) - 1)
        if frac < 0.125:
            lbl = "CLIP 1/7: sit_up (ANIMATION-DRIVEN)"
        elif frac < 0.25:
            lbl = "CLIP 2/7: grab_food (Both Front Paws)"
        elif frac < 0.375:
            lbl = "CLIP 3/7: bring_to_mouth (Socket: food_hold_socket)"
        elif frac < 0.625:
            lbl = "CLIP 4/7: chew_loop (4.8 Hz Jaw + Chew Morph)"
        elif frac < 0.73:
            lbl = "CLIP 5/7: swallow"
        elif frac < 0.88:
            lbl = "CLIP 6/7: stuff_cheek (Cheek Pouch Shape Keys Bulge -> 0.98)"
        else:
            lbl = "CLIP 7/7: release_idle (Cheek Pouches Remain Packed)"

        cv2.rectangle(img, (16, 14), (660, 54), (20, 33, 61), -1)
        cv2.putText(img, lbl, (26, 41), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (244, 237, 224), 2, cv2.LINE_AA)
        writer.write(img)
    writer.release()
    print(f"Saved {OUT_MP4} ({OUT_MP4.stat().st_size:,} B)")

    # Build 7-panel contact sheet (4 top + 3 bottom)
    tiles = []
    tw, th = 480, 270
    for fname, title in STAGE_LABELS:
        p = RENDER_DIR / fname
        im = cv2.imread(str(p))
        im_r = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
        cv2.rectangle(im_r, (8, 8), (tw - 8, 40), (20, 33, 61), -1)
        cv2.putText(im_r, title, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (244, 237, 224), 1, cv2.LINE_AA)
        tiles.append(im_r)

    # Add an 8th summary tile for a clean 2x4 grid
    summary_tile = np.full((th, tw, 3), (20, 33, 61), dtype=np.uint8)
    lines = [
        "HAMMY STEP 5: EATING ANIMATION SET",
        "Honesty Label: ANIMATION-DRIVEN",
        "(Policy decides WHEN & WHERE to eat)",
        "------------------------------------",
        "Clips exported in hamster.glb:",
        " - sit_up, grab_food, bring_to_mouth",
        " - chew_loop, swallow, stuff_cheek",
        " - release_idle, eat_full_sequence",
        "Sockets: head_slot, neck_slot,",
        "         back_slot, food_hold_socket",
        "Morphs: cheek_pouch_left/right (0..1)",
    ]
    for i, line in enumerate(lines):
        col = (107, 107, 255) if i == 0 else (244, 237, 224)
        cv2.putText(summary_tile, line, (18, 28 + i * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, col, 1, cv2.LINE_AA)
    tiles.append(summary_tile)

    row1 = np.hstack(tiles[:4])
    row2 = np.hstack(tiles[4:8])
    sheet = np.vstack([row1, row2])
    cv2.imwrite(str(OUT_SHEET), sheet)
    print(f"Saved contact sheet {OUT_SHEET} ({OUT_SHEET.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
