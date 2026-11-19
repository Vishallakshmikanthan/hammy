"""Stage 3: Train PPO locomotion policies with curriculum, domain randomization, and 4-way ablation.

Conditions compared (reproducible seeds, saved config.json, CSV + TensorBoard logs):
  1. imitation_synthetic : LEARNED (imitation from SYNTHETIC procedural reference)
  2. imitation_real      : LEARNED (imitation from REAL_VIDEO wheel/groom reference)
  3. imitation_mixed     : LEARNED (imitation from MIXED real+synthetic reference)
  4. no_imitation        : LEARNED (pure RL baseline, no imitation reward)

Evaluates each condition across 100 episodes (multiple speeds, turning, stop-start),
exports the best policy to ONNX with baked observation normalizer, and renders policy videos.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from contracts.locomotion_contracts import MODEL_VERSION
from training.hamster_locomotion_env import CURRICULUM_STAGES, HamsterLocomotionEnv
from training.onnx_export_sb3 import export_ppo_to_onnx

RUNS_ROOT = Path("training/runs/stage3")
RENDERS_DIR = Path("renders/stage3")


class RewardTermsAndCheckpointCallback(BaseCallback):
    """Logs every reward term separately to CSV + TensorBoard and saves periodic checkpoints."""

    def __init__(
        self,
        run_dir: Path,
        checkpoint_freq_steps: int = 100_000,
        log_freq_rollouts: int = 1,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.run_dir = run_dir
        self.ckpt_dir = run_dir / "checkpoints"
        self.ckpt_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = run_dir / "reward_terms.csv"
        self.checkpoint_freq_steps = checkpoint_freq_steps
        self.log_freq_rollouts = log_freq_rollouts
        self._last_ckpt_step = 0
        self._rollout_idx = 0
        self._buf: dict[str, list[float]] = {}
        self._csv_header_written = False

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        for info in infos:
            rterms = info.get("reward_terms")
            if rterms:
                for k, v in rterms.items():
                    self._buf.setdefault(k, []).append(float(v))
                self._buf.setdefault("fell", []).append(1.0 if info.get("fell") else 0.0)
                self._buf.setdefault("vx", []).append(float(info.get("vx", 0.0)))
                self._buf.setdefault("vx_cmd", []).append(float(info.get("vx_cmd", 0.0)))
                self._buf.setdefault("joint_track_rmse", []).append(float(info.get("joint_track_rmse", 0.0)))
                st = info.get("curriculum_stage", "walk")
                st_idx = CURRICULUM_STAGES.index(st) if st in CURRICULUM_STAGES else 0
                self._buf.setdefault("curriculum_stage_idx", []).append(float(st_idx))

        if self.num_timesteps - self._last_ckpt_step >= self.checkpoint_freq_steps:
            self._last_ckpt_step = self.num_timesteps
            ckpt_p = self.ckpt_dir / f"ppo_{self.num_timesteps}.zip"
            self.model.save(str(ckpt_p))
            vec_env = self.model.get_vec_normalize_env()
            if vec_env is not None:
                vec_env.save(str(self.ckpt_dir / f"vecnorm_{self.num_timesteps}.pkl"))
        return True

    def _on_rollout_end(self) -> None:
        self._rollout_idx += 1
        if not self._buf or (self._rollout_idx % self.log_freq_rollouts != 0):
            return

        row = {"timesteps": int(self.num_timesteps)}
        for k, vals in sorted(self._buf.items()):
            m = float(np.mean(vals))
            row[k] = round(m, 6)
            self.logger.record(f"hamster/{k}", m)
        self._buf.clear()

        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not self._csv_header_written:
                writer.writeheader()
                self._csv_header_written = True
            writer.writerow(row)


def _make_env_fn(
    rank: int,
    seed: int,
    source_filter: str,
    use_imitation: bool,
    curriculum_stage: int,
    auto_curriculum: bool,
    domain_randomization: bool,
):
    def _init():
        env = HamsterLocomotionEnv(
            source_filter=source_filter,  # type: ignore[arg-type]
            use_imitation=use_imitation,
            curriculum_stage=curriculum_stage,
            auto_curriculum=auto_curriculum,
            domain_randomization=domain_randomization,
        )
        env.reset(seed=seed + rank)
        return env

    return _init


def train_condition(
    name: str,
    label: str,
    source_filter: str,
    use_imitation: bool,
    total_timesteps: int,
    n_envs: int,
    seed: int,
    use_subproc: bool = True,
) -> tuple[PPO, VecNormalize, Path]:
    run_dir = RUNS_ROOT / name
    run_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "condition_name": name,
        "honesty_label": label,
        "model_version": MODEL_VERSION,
        "source_filter": source_filter,
        "use_imitation": use_imitation,
        "total_timesteps": total_timesteps,
        "n_envs": n_envs,
        "seed": seed,
        "curriculum": "auto_success_gated (stand->perturb->walk->turn->stop->target)",
        "domain_randomization": True,
        "control_hz": 50,
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Start curriculum at stand/perturb with auto_curriculum=True (advances on >=85% measured non-fall success)
    env_fns = [
        _make_env_fn(
            rank=i,
            seed=seed,
            source_filter=source_filter,
            use_imitation=use_imitation,
            curriculum_stage=i % 3,
            auto_curriculum=True,
            domain_randomization=True,
        )
        for i in range(n_envs)
    ]
    if use_subproc:
        vec_env = SubprocVecEnv(env_fns, start_method="spawn")
    else:
        vec_env = DummyVecEnv(env_fns)
    vec_env = VecNormalize(vec_env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=5e-4,
        n_steps=64,
        batch_size=512,
        n_epochs=8,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.015,
        policy_kwargs={"net_arch": {"pi": [256, 256], "vf": [256, 256]}, "activation_fn": torch.nn.Tanh},
        tensorboard_log=str(run_dir / "tb"),
        device="cuda" if torch.cuda.is_available() else "cpu",
        seed=seed,
        verbose=0,
    )

    cb = RewardTermsAndCheckpointCallback(run_dir=run_dir, checkpoint_freq_steps=max(total_timesteps // 2, 50_000))
    t0 = time.perf_counter()
    model.learn(total_timesteps=total_timesteps, callback=cb)
    train_sec = time.perf_counter() - t0

    model.save(str(run_dir / "final_model.zip"))
    vec_env.save(str(run_dir / "vecnorm.pkl"))

    meta_summary = {**config, "train_wall_sec": round(train_sec, 2), "train_fps": round(total_timesteps / max(train_sec, 1e-6), 1)}
    (run_dir / "train_summary.json").write_text(json.dumps(meta_summary, indent=2), encoding="utf-8")
    print(f"[TRAIN] {name} finished {total_timesteps} steps in {train_sec:.1f}s ({meta_summary['train_fps']} fps)")
    return model, vec_env, run_dir


def evaluate_policy_100_episodes(
    model: PPO,
    vec_norm: VecNormalize,
    source_filter: str,
    n_episodes: int = 100,
    seed: int = 9000,
) -> dict:
    """Evaluate across 100 episodes: 25 slow walk, 25 med trot, 25 turn, 25 stop-start."""
    eval_env = HamsterLocomotionEnv(
        source_filter=source_filter,  # type: ignore[arg-type]
        use_imitation=True,
        curriculum_stage=3,
        auto_curriculum=False,
        domain_randomization=True,
        episode_length_s=5.0,
    )

    obs_mean = vec_norm.obs_rms.mean.astype(np.float32)
    obs_inv_std = (1.0 / np.sqrt(vec_norm.obs_rms.var + vec_norm.epsilon)).astype(np.float32)
    clip_obs = float(vec_norm.clip_obs)

    def normalize_obs(o: np.ndarray) -> np.ndarray:
        return np.clip((o - obs_mean) * obs_inv_std, -clip_obs, clip_obs).astype(np.float32)

    non_falls = 0
    speed_errs = []
    yaw_errs = []
    joint_rmses = []
    walk_distances = []
    stride_freqs = []
    stride_lengths = []
    stop_settling_times = []
    reward_term_totals: dict[str, list[float]] = {}
    all_actions_finite = True

    scenarios = [
        ("walk_slow", 0.12, 0.0),
        ("trot_med", 0.20, 0.0),
        ("turn_lr", 0.14, 0.75),
        ("stop_start", 0.15, 0.0),
    ]

    for ep in range(n_episodes):
        sc_name, vx_c, yaw_c = scenarios[ep % len(scenarios)]
        if sc_name == "turn_lr" and (ep // len(scenarios)) % 2 == 1:
            yaw_c = -yaw_c
        eval_env.set_fixed_command(vx_c, 0.0, yaw_c)
        obs, _ = eval_env.reset(seed=seed + ep)

        start_xy = eval_env.data.qpos[0:2].copy()
        fell = False
        fl_contacts = []
        vx_hist = []
        stop_cmd_step = 100  # 2.0 s into 5.0 s episode

        for step_i in range(eval_env.max_steps):
            if sc_name == "stop_start":
                if stop_cmd_step <= step_i < 175:
                    eval_env.set_fixed_command(0.0, 0.0, 0.0)
                else:
                    eval_env.set_fixed_command(0.15, 0.0, 0.0)

            n_obs = normalize_obs(obs)
            act, _ = model.predict(n_obs, deterministic=True)
            if not np.all(np.isfinite(act)):
                all_actions_finite = False
            obs, rew, term, trunc, info = eval_env.step(act)

            speed_errs.append(abs(info["vx"] - info["vx_cmd"]))
            yaw_errs.append(abs(info["yaw_rate"] - info["yaw_cmd"]))
            if info["joint_track_rmse"] > 0:
                joint_rmses.append(info["joint_track_rmse"])
            for k, v in info["reward_terms"].items():
                reward_term_totals.setdefault(k, []).append(float(v))

            fl_contacts.append(float(info["contacts"][0]))
            vx_hist.append(float(info["vx"]))

            if term:
                fell = True
                break
            if trunc:
                break

        if not fell:
            non_falls += 1
            dist = float(np.linalg.norm(eval_env.data.qpos[0:2] - start_xy))
            if sc_name in ("walk_slow", "trot_med"):
                walk_distances.append(dist)
                # Count stance-entry rising edges on front-left paw to measure stride frequency & length
                c_bin = (np.asarray(fl_contacts) > 0.3).astype(int)
                rises = int(np.sum((c_bin[1:] == 1) & (c_bin[:-1] == 0)))
                dur_s = len(fl_contacts) * eval_env.control_dt
                if rises >= 2 and dur_s > 1.0:
                    freq = rises / dur_s
                    stride_freqs.append(freq)
                    stride_lengths.append(dist / rises)
            elif sc_name == "stop_start" and len(vx_hist) > 160:
                # Settling time after stop command at step 100 until |vx| < 0.04 m/s
                after = np.abs(np.asarray(vx_hist[stop_cmd_step:175]))
                settled = np.where(after < 0.04)[0]
                t_settle = float(settled[0] * eval_env.control_dt) if len(settled) > 0 else 1.5
                stop_settling_times.append(t_settle)

    eval_env.close()

    return {
        "n_episodes": n_episodes,
        "non_fall_rate_pct": round(100.0 * non_falls / max(n_episodes, 1), 2),
        "mean_speed_err_m_s": round(float(np.mean(speed_errs)), 4),
        "mean_yaw_err_rad_s": round(float(np.mean(yaw_errs)), 4),
        "mean_joint_track_rmse_rad": round(float(np.mean(joint_rmses)), 4) if joint_rmses else None,
        "mean_walk_distance_5s_m": round(float(np.mean(walk_distances)), 3) if walk_distances else 0.0,
        "measured_stride_freq_hz": round(float(np.mean(stride_freqs)), 2) if stride_freqs else None,
        "measured_stride_length_m": round(float(np.mean(stride_lengths)), 4) if stride_lengths else None,
        "mean_stop_settling_s": round(float(np.mean(stop_settling_times)), 3) if stop_settling_times else None,
        "all_actions_finite": all_actions_finite,
        "mean_reward_terms": {k: round(float(np.mean(v)), 4) for k, v in sorted(reward_term_totals.items())},
    }


def render_policy_videos(
    model: PPO,
    vec_norm: VecNormalize,
    condition_name: str,
    honesty_label: str,
    source_filter: str,
) -> list[str]:
    RENDERS_DIR.mkdir(parents=True, exist_ok=True)
    obs_mean = vec_norm.obs_rms.mean.astype(np.float32)
    obs_inv_std = (1.0 / np.sqrt(vec_norm.obs_rms.var + vec_norm.epsilon)).astype(np.float32)
    clip_obs = float(vec_norm.clip_obs)

    def _run_video(out_name: str, title: str, schedule_fn, duration_s: float = 5.0) -> tuple[str, np.ndarray]:
        env = HamsterLocomotionEnv(
            source_filter=source_filter,  # type: ignore[arg-type]
            use_imitation=True,
            curriculum_stage=3,
            auto_curriculum=False,
            domain_randomization=False,
            episode_length_s=duration_s,
            render_mode="rgb_array",
        )
        vx0, vy0, yaw0 = schedule_fn(0.0)
        env.set_fixed_command(vx0, vy0, yaw0)
        obs, _ = env.reset(seed=777)

        frames = []
        mid_snap = None
        n_steps = int(round(duration_s / env.control_dt))  # 50 Hz
        for i in range(n_steps):
            t_s = i * env.control_dt
            vx_c, vy_c, yaw_c = schedule_fn(t_s)
            env.set_fixed_command(vx_c, vy_c, yaw_c)
            n_obs = np.clip((obs - obs_mean) * obs_inv_std, -clip_obs, clip_obs).astype(np.float32)
            act, _ = model.predict(n_obs, deterministic=True)
            obs, _, term, trunc, info = env.step(act)

            if i % 2 == 0:  # 25 fps video
                img = env.render(camera="track_three_quarter")
                cv2.rectangle(img, (0, 0), (640, 44), (18, 20, 26), -1)
                cv2.putText(
                    img,
                    f"LEARNED PPO ({condition_name}) | {title}",
                    (10, 17),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.46,
                    (110, 240, 160),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    img,
                    f"t={t_s:4.2f}s | cmd=({vx_c:.2f}m/s, {yaw_c:+.2f}r/s) | actual=({info['vx']:.2f}m/s, {info['yaw_rate']:+.2f}r/s)",
                    (10, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (235, 235, 235),
                    1,
                    cv2.LINE_AA,
                )
                frames.append(img)
                if i == n_steps // 2:
                    mid_snap = img.copy()
            if term or trunc:
                break
        env.close()
        out_p = RENDERS_DIR / out_name
        imageio.mimsave(out_p, frames, fps=25, quality=8)
        return str(out_p), (mid_snap if mid_snap is not None else frames[0])

    v1, s1 = _run_video(
        "policy_walk_speeds.mp4",
        "Walk 0.12 -> 0.20 m/s",
        lambda t: (0.12, 0.0, 0.0) if t < 2.5 else (0.20, 0.0, 0.0),
    )
    v2, s2 = _run_video(
        "policy_turn_left_right.mp4",
        "Turn Left +0.75 -> Right -0.75 rad/s",
        lambda t: (0.14, 0.0, 0.75) if t < 2.5 else (0.14, 0.0, -0.75),
    )
    v3, s3 = _run_video(
        "policy_stop_start.mp4",
        "Stop-Start (Walk -> Stop -> Walk)",
        lambda t: (0.0, 0.0, 0.0) if (1.8 <= t < 3.4) else (0.15, 0.0, 0.0),
    )
    preview = np.hstack([cv2.resize(im, (480, 270)) for im in (s1, s2, s3)])
    preview_p = RENDERS_DIR / "stage3_policy_preview.png"
    imageio.imwrite(preview_p, preview)
    return [v1, v2, v3, str(preview_p)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=400_000)
    parser.add_argument("--n-envs", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--eval-episodes", type=int, default=100)
    args = parser.parse_args()

    RUNS_ROOT.mkdir(parents=True, exist_ok=True)

    conditions = [
        ("imitation_synthetic", "LEARNED (imitation from SYNTHETIC reference)", "synthetic", True),
        ("imitation_real", "LEARNED (imitation from REAL_VIDEO wheel/groom reference)", "real", True),
        ("imitation_mixed", "LEARNED (imitation from MIXED real+synthetic reference)", "mixed", True),
        ("no_imitation", "LEARNED (pure RL baseline, no imitation)", "mixed", False),
    ]

    ablation_results = {}
    trained_models = {}

    for name, label, src_filter, use_imit in conditions:
        model, vec_norm, run_dir = train_condition(
            name=name,
            label=label,
            source_filter=src_filter,
            use_imitation=use_imit,
            total_timesteps=args.timesteps,
            n_envs=args.n_envs,
            seed=args.seed,
            use_subproc=False,
        )
        ev = evaluate_policy_100_episodes(
            model,
            vec_norm,
            source_filter=src_filter,
            n_episodes=args.eval_episodes,
            seed=9000,
        )
        ev["honesty_label"] = label
        ev["source_filter"] = src_filter
        ev["use_imitation"] = use_imit
        (run_dir / "eval_100ep.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
        ablation_results[name] = ev
        trained_models[name] = (model, vec_norm, label, src_filter)
        vec_norm.close()
        print(f"[EVAL] {name}: non_fall={ev['non_fall_rate_pct']}%, speed_err={ev['mean_speed_err_m_s']}m/s, walk_dist={ev['mean_walk_distance_5s_m']}m")

    # Pick best policy: highest non-fall rate, then lowest speed error
    best_name = sorted(
        ablation_results.keys(),
        key=lambda k: (-ablation_results[k]["non_fall_rate_pct"], ablation_results[k]["mean_speed_err_m_s"]),
    )[0]
    best_model, best_vec, best_label, best_filter = trained_models[best_name]

    onnx_info = export_ppo_to_onnx(
        best_model,
        best_vec,
        RUNS_ROOT / "best_policy.onnx",
        extra_metadata={
            "best_condition": best_name,
            "honesty_label": best_label,
            "source_filter": best_filter,
        },
    )
    video_paths = render_policy_videos(best_model, best_vec, best_name, best_label, best_filter)

    final_report = {
        "best_condition": best_name,
        "best_honesty_label": best_label,
        "onnx_export": onnx_info,
        "rendered_videos": video_paths,
        "ablation": ablation_results,
    }
    report_path = RUNS_ROOT / "ablation_report.json"
    report_path.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print("\n=== STAGE 3 FINAL REPORT ===")
    print(json.dumps(final_report, indent=2))


if __name__ == "__main__":
    main()
