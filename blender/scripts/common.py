"""
HAMMY Pipeline — Common Helper Utilities for Blender / Cycles Scripts.
Idempotent helpers to manage collections, objects, units, materials, and dated backups.
"""

import bpy
import os
from datetime import datetime


def get_or_create_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    """
    Idempotent collection getter/creator.
    If the collection exists, returns it. Otherwise creates it under parent (defaults to Scene Master Collection).
    """
    if name in bpy.data.collections:
        col = bpy.data.collections[name]
        target_parent = parent or bpy.context.scene.collection
        # Ensure it is linked in the scene hierarchy
        if col.name not in [c.name for c in target_parent.children]:
            try:
                target_parent.children.link(col)
            except RuntimeError:
                pass
        return col

    col = bpy.data.collections.new(name)
    target_parent = parent or bpy.context.scene.collection
    target_parent.children.link(col)
    return col


def clear_collection(name: str, remove_data: bool = True):
    """
    Idempotent collection cleaner.
    Unlinks and deletes all objects belonging to this collection so re-running scripts does not duplicate meshes.
    """
    if name not in bpy.data.collections:
        return

    col = bpy.data.collections[name]
    objects = list(col.objects)
    for obj in objects:
        col.objects.unlink(obj)
        if remove_data:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and hasattr(bpy.data, "meshes") and data in bpy.data.meshes.values():
                if data.users == 0:
                    bpy.data.meshes.remove(data)


def make_material(name: str, use_nodes: bool = True) -> bpy.types.Material:
    """
    Idempotent material getter/creator with nodes enabled.
    """
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name=name)

    mat.use_nodes = use_nodes
    return mat


def set_unit_scale_metric():
    """
    Enforce Rule 1: Metric units, unit scale 1.0, length in meters.
    """
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'


def configure_cycles_gpu(device_type: str = "OPTIX") -> dict:
    """
    Configures Cycles to render with GPU acceleration (OptiX or CUDA).
    Returns device and status info.
    """
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    
    cpref = bpy.context.preferences.addons.get('cycles')
    if not cpref:
        return {"status": "error", "message": "Cycles addon not loaded"}

    cpref.preferences.get_devices()
    types_available = [d.type for d in cpref.preferences.devices]
    
    target_type = device_type.upper()
    if target_type not in types_available:
        target_type = "CUDA" if "CUDA" in types_available else "NONE"

    if target_type != "NONE":
        cpref.preferences.compute_device_type = target_type
        cpref.preferences.get_devices()
        activated = []
        for dev in cpref.preferences.devices:
            if dev.type == target_type:
                dev.use = True
                activated.append(dev.name)
            elif dev.type == 'CPU':
                dev.use = False
        scene.cycles.device = 'GPU'
        return {"status": "ok", "compute_device_type": target_type, "devices": activated}
    else:
        scene.cycles.device = 'CPU'
        return {"status": "fallback_cpu", "compute_device_type": "NONE", "devices": ["CPU"]}


def save_dated_copy(base_name: str = "scene", output_dir: str = "blender") -> str:
    """
    Enforce Rule 2: Save dated copies before major changes (scene_YYYYMMDD_HHMM.blend).
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{base_name}_{timestamp}.blend"
    filepath = os.path.abspath(os.path.join(output_dir, filename))
    bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=True)
    return filepath

