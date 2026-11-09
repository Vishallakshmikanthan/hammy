# HAMMY — Architecture & Technical Decisions Log

## 2026-11-09: Environment Initialization & MCP Setup
- **Blender Version:** Blender 5.2.3 LTS verified.
- **Python Version:** 3.13.13 bundled with Blender.
- **Hardware Acceleration:** NVIDIA GeForce RTX 5070 Laptop GPU detected with OptiX Ray-Tracing & CUDA. OptiX configured as primary compute device for Cycles renders.
- **Bridge Setup:** Resolved port 9876 conflict between default extension and `mcp_connector_v2.py`. Live WebSocket server verified responsive at ~100ms latency.
- **Scripts Scaffold:** Initialized `blender/scripts/common.py` with idempotent collection and material management, metric unit enforcement, and dated scene snapshots.
- **Headless Pipeline:** Verified `blender -b -P blender/scripts/00_check_env.py` runs cleanly in background mode.

