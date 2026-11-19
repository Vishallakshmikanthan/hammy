"""Export the 1M-step imitation_mixed policy to best_policy.onnx and refresh renders & report."""

from __future__ import annotations

import json
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from scripts.stage3_train_and_ablate import render_policy_videos
from training.hamster_locomotion_env import HamsterLocomotionEnv
from training.onnx_export_sb3 import export_ppo_to_onnx


def main() -> None:
    run_dir = Path("training/runs/stage3/imitation_mixed")
    venv = DummyVecEnv([lambda: HamsterLocomotionEnv(source_filter="mixed", use_imitation=True, curriculum_stage=2)])
    vnorm = VecNormalize.load(str(run_dir / "vecnorm.pkl"), venv)
    vnorm.training = False
    vnorm.norm_reward = False
    model = PPO.load(str(run_dir / "final_model.zip"), device="cpu")

    label = "LEARNED (1M-step imitation from MIXED 6 REAL_VIDEO + 5 SYNTHETIC refs)"
    onnx_info = export_ppo_to_onnx(
        model,
        vnorm,
        Path("training/runs/stage3/best_policy.onnx"),
        extra_metadata={
            "best_condition": "imitation_mixed",
            "honesty_label": label,
            "source_filter": "mixed",
        },
    )
    videos = render_policy_videos(model, vnorm, "imitation_mixed", label, "mixed")
    vnorm.close()

    rep_p = Path("training/runs/stage3/ablation_report.json")
    rep = json.loads(rep_p.read_text(encoding="utf-8"))
    rep["best_condition"] = "imitation_mixed"
    rep["best_honesty_label"] = label
    rep["onnx_export"] = onnx_info
    rep["rendered_videos"] = videos
    rep_p.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(onnx_info, indent=2))


if __name__ == "__main__":
    main()
