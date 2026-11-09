"""
HAMMY — P0.1: Environment Verification Script (`scripts/check_env.py`).
Checks Python version, PyTorch + CUDA availability, GPU name & VRAM, MuJoCo version,
and whether MJX (`mujoco.mjx` / `jax`) imports cleanly on this machine.
"""

import sys
import platform
import importlib.util


def check_package(name: str):
    spec = importlib.util.find_spec(name)
    if spec is None:
        return None
    try:
        mod = importlib.import_module(name)
        return getattr(mod, "__version__", "installed (no __version__)")
    except Exception as exc:
        return f"error ({exc})"


def get_env_report() -> dict:
    report = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": None,
        "torch_cuda_version": None,
        "cuda_available": False,
        "gpu_name": None,
        "gpu_vram_gb": None,
        "mujoco_version": None,
        "mjx_available": False,
        "mjx_detail": None,
        "gymnasium_version": check_package("gymnasium"),
        "pydantic_version": check_package("pydantic"),
    }

    try:
        import torch
        report["torch_version"] = torch.__version__
        report["torch_cuda_version"] = torch.version.cuda
        report["cuda_available"] = bool(torch.cuda.is_available())
        if report["cuda_available"]:
            report["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            report["gpu_vram_gb"] = round(props.total_memory / (1024 ** 3), 2)
    except Exception as exc:
        report["torch_version"] = f"not installed ({exc})"

    try:
        import mujoco
        report["mujoco_version"] = mujoco.__version__
    except Exception as exc:
        report["mujoco_version"] = f"not installed ({exc})"

    try:
        from mujoco import mjx  # noqa: F401
        import jax
        report["mjx_available"] = True
        report["mjx_detail"] = f"jax {jax.__version__} (devices: {jax.devices()})"
    except Exception as exc:
        report["mjx_available"] = False
        report["mjx_detail"] = str(exc)

    return report


def main():
    rep = get_env_report()
    print("=" * 68)
    print(" HAMMY P0.1 — DEV ENVIRONMENT & PHYSICS STACK CHECK")
    print("=" * 68)
    print(f"Python version      : {rep['python_version']} ({rep['platform']})")
    print(f"PyTorch version     : {rep['torch_version']}")
    print(f"PyTorch CUDA build  : {rep['torch_cuda_version']}")
    print(f"CUDA available      : {rep['cuda_available']}")
    print(f"GPU Name            : {rep['gpu_name']}")
    print(f"GPU VRAM (GB)       : {rep['gpu_vram_gb']}")
    print(f"MuJoCo version      : {rep['mujoco_version']}")
    print(f"MJX imports         : {rep['mjx_available']} ({rep['mjx_detail']})")
    print(f"Gymnasium version   : {rep['gymnasium_version']}")
    print(f"Pydantic version    : {rep['pydantic_version']}")
    print("=" * 68)

    if not rep["cuda_available"]:
        print(
            "\n[DIAGNOSIS] PyTorch CUDA is not active. For an NVIDIA RTX 5070 Laptop GPU "
            "(Blackwell architecture, sm_120), install PyTorch built with CUDA 12.8+ from "
            "the official PyTorch selector (https://pytorch.org/get-started/locally/):\n"
            "  .venv\\Scripts\\pip install --upgrade torch torchvision torchaudio "
            "--index-url https://download.pytorch.org/whl/cu128"
        )


if __name__ == "__main__":
    main()

