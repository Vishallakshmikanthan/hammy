"""
HAMMY Pipeline — Environment and GPU Verification Script (Prompt 0)
Run headless:
  blender -b -P blender/scripts/00_check_env.py
"""

import sys
import os
import json
import bpy

# Add current scripts directory to path to import common
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

try:
    import common
except ImportError:
    common = None


def check_environment():
    report = {}

    # 1. Blender & Python
    report["blender_version"] = bpy.app.version_string
    report["python_version"] = sys.version.split()[0]
    report["render_engine"] = bpy.context.scene.render.engine

    # 2. Metric units
    units = bpy.context.scene.unit_settings
    report["units"] = {
        "system": units.system,
        "scale_length": units.scale_length,
        "length_unit": units.length_unit,
    }

    # 3. Cycles & Compute Devices
    cpref = bpy.context.preferences.addons.get('cycles')
    if cpref:
        cpref.preferences.get_devices()
        compute_type = getattr(cpref.preferences, 'compute_device_type', 'NONE')
        devices = []
        for d in cpref.preferences.devices:
            devices.append({
                "name": d.name,
                "type": d.type,
                "use": d.use
            })
        report["cycles"] = {
            "compute_device_type": compute_type,
            "scene_device": bpy.context.scene.cycles.device,
            "devices": devices
        }
    else:
        report["cycles"] = {"error": "Cycles addon not enabled"}

    return report


def main():
    print("\n" + "=" * 60)
    print(" HAMMY ART PIPELINE — ENVIRONMENT & GPU VERIFICATION ")
    print("=" * 60)

    report = check_environment()
    print(f"Blender Version:       {report['blender_version']}")
    print(f"Python Version:        {report['python_version']}")
    print(f"Current Render Engine: {report['render_engine']}")
    print(f"Unit System:           {report['units']['system']} (scale: {report['units']['scale_length']}, unit: {report['units']['length_unit']})")

    cycles = report.get("cycles", {})
    compute_type = cycles.get("compute_device_type", "NONE")
    scene_device = cycles.get("scene_device", "CPU")
    print(f"Cycles Compute Type:   {compute_type}")
    print(f"Cycles Scene Device:   {scene_device}")

    print("\nDetected Compute Devices:")
    for dev in cycles.get("devices", []):
        status = "[ACTIVE]" if dev["use"] else "[AVAILABLE]"
        print(f"  - {dev['type']:<8} | {dev['name']:<35} | {status}")

    optix_found = any(d['type'] == 'OPTIX' for d in cycles.get("devices", []))
    cuda_found = any(d['type'] == 'CUDA' for d in cycles.get("devices", []))

    print("-" * 60)
    if optix_found:
        print(">> GPU STATUS: OptiX Ray-Tracing Acceleration is READY on RTX GPU.")
    elif cuda_found:
        print(">> GPU STATUS: CUDA Acceleration is READY.")
    else:
        print(">> GPU STATUS: CPU only (No OptiX/CUDA devices detected).")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

