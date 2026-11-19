# Stage 0a: Raw Video Audit (`data/raw_video/`)

**Audit Date:** 2026-11-19 (Updated with 3 additional 1080p clips)  
**Source Note:** All 8 raw clips were supplied in `reference/video/` and mirrored unchanged to `data/raw_video/` so all downstream pipeline paths match the specification. Contact sheets (3×3 evenly spaced frames) were generated in `data/audit_frames/` and visually inspected.

## Summary Table (Ranked by Usefulness for Pose & Gait Extraction)

| Rank | File | Duration (s) | FPS | Resolution | Codec | Camera Angle | Camera Fixed? | Whole Body Visible? | Species | Behaviours Observed | Verdict |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `hamster-video6.mp4` | 95.97 | 23.976 | 1920×1080 | h264 | Clean side profile (wheel) | Yes per cut (multi-cut + split-screen slow-mo) | Yes (full lateral body & legs inside wheel) | Dwarf hamsters (2 individuals) | **Wheel running** (real-time & slow-motion), brief pauses | **USABLE — Primary real-video locomotion / limb-cycle clip** (requires scene-cut segmentation to separate real-time vs. slow-mo; curved wheel surface & dwarf proportions documented) |
| **2** | `hamster-video1.mp4` | 12.20 | 25.00 | 960×540 | h264 | Clean side profile (left-facing) | Yes (`border_diff=0.42`) | Mostly (hind paws partially in wood shavings) | **Syrian hamster** | Stationary crouch, **groom / eat** with forepaws | **USABLE — Primary Syrian hamster lateral proportion & grooming posture clip** (no walking) |
| **3** | `hamster-video7.mp4` | 73.07 | 30.00 | 1920×1080 | h264 | Oblique high 3/4 & top-oblique | No (handheld tracking, `border_diff=51.73`) | Mostly (on wooden platform & bridge) | Dwarf hamster | **Rear / bipedal stand**, **walk**, **turn**, **sniff**, **stop-start** | **USABLE (partial) — Rearing, oblique walk/turn & stop-start timing** (requires camera-drift removal; title overlay on early frames) |
| **4** | `hamster-video8.mp4` | 389.46 | 29.97 | 1920×1080 | h264 | Mixed close-up / oblique montage | No (multi-cut handheld, `border_diff=46.00`) | Partial (close-ups & cage props; full body in some cuts) | **Syrian hamster** (cream) | **Forage, groom, eat, sniff, rear, climb, short walks** | **USABLE (secondary) — Syrian hamster morphology & behaviour reference** (multi-cut close-ups limit continuous gait tracking) |
| **5** | `hamster-video2.mp4` | 40.11 | 29.97 | 960×540 | h264 | Oblique high 3/4 | Mostly (`border_diff=7.35`) | No (inside white plastic box; legs occluded) | Syrian hamster | Stationary eating carrot | **REJECTED** (legs occluded, stationary) |
| **6** | `hamster-video4.mp4` | 29.08 | 25.00 | 960×540 | h264 | Front / 3/4 studio | Yes (`border_diff=0.50`) | No (inside cup; lower body hidden; human hand) | Dwarf hamster | Sniff, receive treat, eat | **REJECTED** (lower body occluded, stationary) |
| **7** | `hamster-video3.mp4` | 20.02 | 29.97 | 960×540 | h264 | High oblique close-up | Yes (fade to black at 20 s) | No (inside clay jar; blurred climb at ~10 s) | Dwarf hamster | Peek/sniff, blurred jump, hide | **REJECTED** (occluded, motion blur) |
| **8** | `hamster-video5.mp4` | 11.73 | 30.00 | 960×540 | h264 | Rotated 90° oblique | No (`border_diff=26.76`, handheld) | No (buried in bedding under ladder) | Dwarf hamster | Sniff/peek from bedding | **REJECTED** (buried, rotated 90°, handheld) |

## Contact Sheet Evidence
- `data/audit_frames/hamster-video1_contact.jpg`
- `data/audit_frames/hamster-video2_contact.jpg`
- `data/audit_frames/hamster-video3_contact.jpg`
- `data/audit_frames/hamster-video4_contact.jpg`
- `data/audit_frames/hamster-video5_contact.jpg`
- `data/audit_frames/hamster-video6_contact.jpg`
- `data/audit_frames/hamster-video7_contact.jpg`
- `data/audit_frames/hamster-video8_contact.jpg`

## Key Findings & Downstream Pipeline Strategy

1. **Usable Real Clips Selected (4 of 8):**
   - `hamster-video1.mp4`: Best fixed-camera lateral silhouette of an adult **Syrian hamster** (proportion extraction + grooming posture).
   - `hamster-video6.mp4`: Crisp 1080p fixed-camera side-profile **wheel running** (both real-time and slow-motion segments) with a circular wheel providing a natural scale/geometry reference; valuable for real limb-cycle phase and stride-frequency extraction (noting dwarf hamster + curved wheel surface).
   - `hamster-video7.mp4`: 1080p **rearing, platform/bridge walking, turning, and stop-start timing** (dwarf hamster, handheld camera).
   - `hamster-video8.mp4`: 6.5 min 1080p **Syrian hamster** montage for behavioural repertoire and proportion cross-checks.
2. **Remaining Gap (Flat-Ground Side/Top Syrian Walking):**
   - None of the 8 clips is a single fixed-camera, unoccluded, flat-ground walking pass of a Syrian hamster.
   - Therefore, per Stage 2.7 and user instructions:
     - We will extract real keypoints, proportions, and gait statistics where reliable from `hamster-video1.mp4`, `hamster-video6.mp4`, and `hamster-video7.mp4`.
     - We will ALSO generate explicitly labeled **`SYNTHETIC`** procedural walk/trot/turn/stop reference clips (marked in filenames `*_SYNTHETIC.npz`, metadata `source_type="SYNTHETIC"`, and all reports).
     - The reference-clip loader in Stage 2/3 will be **source-agnostic** so real flat-ground walking clips added later to `data/raw_video/` can drop in to replace or blend with `SYNTHETIC` clips without changing training code.
3. **Watermarks:** Clips 1–5 carry stock watermarks (`envato`/`videohive`); clips 6–8 are clean 1080p without stock watermarks.

---

## Batch 2 Update: 13 Newly Uploaded Real Videos (21 Total in `data/raw_video/`)

| Clip (Batch 2) | Duration (s) | FPS | Res | View / Camera | Behaviours | Extracted Real-Video Stats (`gait_statistics.json`) | Verdict |
| :--- | :---: | :---: | :---: | :--- | :--- | :--- | :--- |
| `european-hamster-walks-into-view-sniffs-then-moves-away-in-grass.webm` | 17.72 | 25.0 | 898×506 | Fixed side profile | **Flat-ground walk, stop, sniff, turn** | `0.077 m/s`, `1.64 Hz`, `0.047 m` stride, move `0.72 s` / stop `1.16 s` | **USABLE — Retargeted (`real_grass_walk_sniff_REAL.npz`)** |
| `mouse-eating-...-child.webm` | 8.80 | 25.0 | 898×506 | Fixed side profile (flat mat) | **Turn, eat, walk away** | `0.089 m/s`, `1.48 Hz`, `0.060 m` stride, move `0.76 s` / stop `0.25 s` | **USABLE — Retargeted (`real_flat_mat_eat_walk_REAL.npz`)** |
| `curious-white-dwarf-hamster-standing-on-hind-legs...webm` | 6.03 | 30.0 | 898×506 | Fixed front/side | **Bipedal rearing, sniff, drop** | `0.082 m/s`, `1.66 Hz`, move `0.73 s` / stop `0.16 s` | **USABLE — Retargeted (`real_rear_sniff_enclosure_REAL.npz`)** |
| `a-small-pet-hamster-running-across-a-child-s-hands.webm` | 9.11 | 29.97 | 898×506 | Oblique close-up | **Hand-walking / taming** | `0.129 m/s`, `1.54 Hz`, move `1.75 s` / stop `0.07 s` | **USABLE — Retargeted (`real_hand_taming_walk_REAL.npz`)** |
| `hamster-cute-little-animal-pet (4).webm` | 16.52 | 29.97 | 898×506 | **Fixed true top-down** | **Enclosure explore, bowl, turn, stop-start** | `0.099 m/s`, `1.27 Hz`, move `1.22 s` / stop `1.10 s` | **USABLE — Top-down trajectory & timing** |
| `russian-hamster-in-its-wooden-cage-pet-in-its-little-house.webm` | 48.03 | 30.0 | 898×506 | Fixed wide side | **Full habitat ethogram (hideout → ramp → wheel → mat)** | Behaviour sequence reference | **USABLE (behaviour reference)** |
| `mouse-eating-...-child (1).webm` | 14.96 | 25.0 | 898×506 | Fixed side macro | Stationary carrot eating | Posture reference | Secondary |
| `hamster-cute-little-animal-pet.webm`, `(1)`, `(2)`, `(3)` | 15.6–18.3 | 29.97 | 898×506 | Handheld top/oblique | Bedding explore/burrow | Camera motion | Secondary |
| `four-cute-golden-syrian-hamsters-gathering.webm`, `multiple-hamsters-enjoying-food.webm` | 6.9 / 13.0 | 30 / 60 | 898×506 | Oblique / top | Multi-hamster social/eat | Multi-individual occlusion | Rejected for single-animal pose |

