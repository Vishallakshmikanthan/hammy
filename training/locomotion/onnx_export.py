"""
ONNX exporter and equivalence verifier for Phase 4 locomotion policies.
Embeds schema, morphology, and environment versions in ONNX metadata_props.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict
import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort

from training.locomotion.policy import MLPActorCritic


def export_policy_to_onnx(
    policy: MLPActorCritic,
    onnx_path: Path,
    metadata: Dict[str, str],
) -> Path:
    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    obs_input = helper.make_tensor_value_info("obs", TensorProto.FLOAT, [None, policy.obs_dim])
    act_output = helper.make_tensor_value_info("action", TensorProto.FLOAT, [None, policy.action_dim])

    initializers = [
        numpy_helper.from_array(policy.w1.astype(np.float32), name="w1"),
        numpy_helper.from_array(policy.b1.astype(np.float32), name="b1"),
        numpy_helper.from_array(policy.w2.astype(np.float32), name="w2"),
        numpy_helper.from_array(policy.b2.astype(np.float32), name="b2"),
        numpy_helper.from_array(policy.w3.astype(np.float32), name="w3"),
        numpy_helper.from_array(policy.b3.astype(np.float32), name="b3"),
        numpy_helper.from_array(np.array([policy.action_scale], dtype=np.float32), name="action_scale"),
    ]

    nodes = [
        helper.make_node("MatMul", ["obs", "w1"], ["mm1"]),
        helper.make_node("Add", ["mm1", "b1"], ["z1"]),
        helper.make_node("Tanh", ["z1"], ["h1"]),
        helper.make_node("MatMul", ["h1", "w2"], ["mm2"]),
        helper.make_node("Add", ["mm2", "b2"], ["z2"]),
        helper.make_node("Tanh", ["z2"], ["h2"]),
        helper.make_node("MatMul", ["h2", "w3"], ["mm3"]),
        helper.make_node("Add", ["mm3", "b3"], ["z3"]),
        helper.make_node("Tanh", ["z3"], ["raw_act"]),
        helper.make_node("Mul", ["raw_act", "action_scale"], ["action"]),
    ]

    graph = helper.make_graph(
        nodes=nodes,
        name="HammyLocomotionPolicy",
        inputs=[obs_input],
        outputs=[act_output],
        initializer=initializers,
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    for k, v in metadata.items():
        prop = model.metadata_props.add()
        prop.key = str(k)
        prop.value = str(v)

    onnx.checker.check_model(model)
    onnx.save(model, str(onnx_path))
    return onnx_path


def verify_onnx_equivalence(
    policy: MLPActorCritic,
    onnx_path: Path,
    num_samples: int = 32,
    atol: float = 1e-5,
    seed: int = 999,
) -> float:
    rng = np.random.default_rng(seed)
    test_obs = rng.normal(0.0, 1.0, size=(num_samples, policy.obs_dim)).astype(np.float32)
    ref_out = policy.forward_deterministic(test_obs)

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    ort_out = sess.run(["action"], {"obs": test_obs})[0]
    max_diff = float(np.max(np.abs(ref_out - ort_out)))
    if max_diff > atol:
        raise AssertionError(f"ONNX output mismatch: max_diff={max_diff:.6e} > atol={atol:.6e}")
    return max_diff

