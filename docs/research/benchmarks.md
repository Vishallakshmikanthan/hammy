# HAMMY — P0.1 Dev Environment & Physics Throughput Benchmarks

- **Date:** 2026-11-09
- **OS / Platform:** `Windows-11-10.0.26200-SP0`
- **GPU:** NVIDIA GeForce RTX 5070 Laptop GPU (8 GB VRAM, Blackwell architecture, `sm_120`, OptiX ray-tracing verified via Blender 5.2.3 LTS)
- **Python Environments Detected:**
  - `Python 3.14.6` (`C:\Python314\python.exe`) — `numpy 2.4.6`, `pydantic 2.13.4`
  - `Python 3.13.14` (`C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\python.exe`) — `torch 2.8.0+cpu`, `mujoco 4.0.0`, `gymnasium 1.4.0`, `pydantic 2.14.3`
  - `Blender 5.2.3 LTS Embedded Python 3.13.13` — Full GPU OptiX acceleration active (`~30 s` per 1080p hair-curve frame)

## 1. Windows Application Control Policy Finding (`WinError 4551`)
- Running `scripts/check_env.py` on Windows revealed that **Windows Smart App Control / Application Control Policy (`[WinError 4551]`)** blocks unsigned third-party native C++ `.dll`/`.pyd` extensions installed into user-writable `AppData` or `.venv` directories (`torch\lib\shm.dll` and `mujoco\_specs.pyd`), while signed system binaries (`C:\Python314\python.exe` and `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`) execute unrestricted.
- **Exact Fix for Native PyTorch CUDA 12.8+ & MJX on RTX 5070 (Blackwell):**
  1. **Recommended (per P0.1 prompt context):** Use **WSL2 Ubuntu** (WSL2 is already enabled on this machine), where Linux ELF shared libraries (`.so`) are unaffected by Windows Smart App Control and `mujoco-mjx` + `jax[cuda12]` + PyTorch CUDA 12.8 (`pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128`) run natively on the RTX 5070 GPU.
  2. **On Native Windows:** Add a Windows Defender / Smart App Control folder exclusion for `C:\Users\Lenovo\Downloads\hammy\.venv` and `C:\Users\Lenovo\AppData\Local\Programs\Python\Python313`.

## 2. Measured Simulation Throughput (`HabitatEnv` + `HomeostaticDrives`)
- **Single-Process Planar Rigid-Body + Homeostatic Stepping (`simulation/habitat_env.py`):**
  - **28,800 steps (100 simulated days at `dt = 300 s`)** completed in **4.65 seconds** (`6,187 steps/sec`, or **1,856,100x real-time**).
  - **1,000-step high-frequency physics rollout (`tests/test_phase0_and_phase1.py`)** completed in **0.147 seconds** (`~6,800 steps/sec`).
- **Conclusion:** This throughput comfortably supports Phase 1–2 high-level skill policies, 100-day homeostatic evaluations, memory ablations, and skill-outcome dataset generation directly on Windows, while Phase 4 low-level 12-DOF legged RL should run inside WSL2 Ubuntu with CUDA 12.8+.

