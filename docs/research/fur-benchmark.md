# P3.1 — Real-Time Fur Rendering Benchmark

**Date:** 2026-11-14  
**Machine:** Windows laptop, NVIDIA GeForce RTX 5070 Laptop GPU (8 GB VRAM, Blackwell), 32 GB RAM  
**Browser:** Headless Google Chrome (`--enable-webgl --enable-unsafe-webgpu --use-gl=angle --use-angle=d3d11`, 1280×800 viewport, 60 Hz VSync)  
**Test Subject:** Hamster-scale capsule (`0.036 m` radius, `0.068 m` length ≈ `0.14 m` total length), `24` shells, `12.0 mm` hair length, `180` density, `0.65` clumping, `0.35` gravity droop, `0.00` wind, `0.85` rim light.

## Measured Results (Laptop)

| Technique | Supported | Avg FPS | Avg Frame Time (ms) | P95 Frame Time (ms) | Draw Calls | Triangles |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| **(a) Shell Texturing** (`shells`) | Yes | 60.0 | 16.66 | 16.80 | 26 | 52,848 |
| **(b) Shells + Silhouette Fins** (`shells-fins`) | Yes | 60.0 | 16.66 | 16.80 | 27 | 57,008 |
| **(c) WebGPU Instanced Strands** (`webgpu-strands`, 12k strands) | Yes | 59.3 | 16.85 | 16.80 | 3 | 146,160 |

*Note: Chrome's D3D11/ANGLE compositor caps `requestAnimationFrame` at 60 Hz (`~16.67 ms` per frame), so all three techniques are VSync-bound at ~60 FPS on the RTX 5070 Laptop GPU.*

### Mid-Range Phone Protocol (To Be Recorded on Device)

1. Serve the production bundle (`cd web && npm run preview -- --host 0.0.0.0 --port 4173`).
2. Open `http://<laptop-ip>:4173/?view=fur-benchmark` on a mid-range mobile browser.
3. Tap **Run Automated Benchmark** and record `avgFps`, `avgFrameTimeMs`, `p95FrameTimeMs`, and whether `navigator.gpu` is supported.
4. *Status:* Not yet measured on a physical mid-range phone in this session.

## Visual Reference

- Screenshot (`shells-fins`): [p3_1_fur_shells_fins.png](file:///c:/Users/Lenovo/Downloads/hammy/renders/phase3/p3_1_fur_shells_fins.png)

## Recommendation

Use **(b) Shells + Silhouette Hair-Card Fins** (`shells-fins`) as the default real-time fur technique for HAMMY:

1. **Universal compatibility:** Runs on WebGL2 everywhere (including mobile browsers without WebGPU) with zero fallback complexity.
2. **Silhouette realism:** Pure shell texturing exhibits visible gaps at grazing silhouette angles; adding perpendicular edge-extruded silhouette fins closes the silhouette cleanly for only `+1` draw call (`27` vs `26`) and `+4,160` triangles.
3. **Quality scaling:** Shell count scales trivially across quality presets (`low: 6 shells, fins off`, `medium: 12`, `high: 20`, `ultra: 32`) while keeping frame times well within a 60 FPS budget.

