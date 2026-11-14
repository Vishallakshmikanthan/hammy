import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  createShellFurGroup,
  createSilhouetteFinsMesh,
  createStrandInstancedMesh,
  detectWebGPUSupport,
} from "./furShaders";
import { DEFAULT_FUR_PARAMS, type FurBenchmarkResult, type FurParams, type FurTechnique } from "./types";

interface FrameMetrics {
  fps: number;
  frameTimeMs: number;
  p95FrameTimeMs: number;
  drawCalls: number;
  triangles: number;
}

export const FurBenchmarkView: React.FC = () => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [params, setParams] = useState<FurParams>(DEFAULT_FUR_PARAMS);
  const paramsRef = useRef<FurParams>(params);
  paramsRef.current = params;

  const [webgpuInfo, setWebgpuInfo] = useState<{ supported: boolean; detail: string }>({
    supported: false,
    detail: "Checking WebGPU...",
  });
  const [metrics, setMetrics] = useState<FrameMetrics>({
    fps: 0,
    frameTimeMs: 0,
    p95FrameTimeMs: 0,
    drawCalls: 0,
    triangles: 0,
  });
  const [benchmarkResults, setBenchmarkResults] = useState<FurBenchmarkResult[]>([]);
  const [isBenchmarking, setIsBenchmarking] = useState(false);

  const frameTimesRef = useRef<number[]>([]);
  const latestMetricsRef = useRef<FrameMetrics>(metrics);

  useEffect(() => {
    detectWebGPUSupport().then((res) => {
      setWebgpuInfo({
        supported: res.supported,
        detail: res.supported ? res.adapterName || "WebGPU Supported" : res.reason || "Unsupported",
      });
    });
  }, []);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 960;
    const height = container.clientHeight || 540;

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#14171c");

    const camera = new THREE.PerspectiveCamera(36, width / height, 0.01, 10);
    camera.position.set(0.18, 0.11, 0.22);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.045, 0);
    controls.enableDamping = true;
    controls.update();

    // Studio key + warm rim + cool fill
    const hemi = new THREE.HemisphereLight("#e8e4dc", "#2b2520", 0.55);
    scene.add(hemi);

    const keyLight = new THREE.DirectionalLight("#fff2dd", 2.2);
    keyLight.position.set(0.45, 0.65, 0.35);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight("#ffd39b", 1.8);
    rimLight.position.set(-0.4, 0.3, -0.45);
    scene.add(rimLight);

    // Matte studio plinth
    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(0.35, 48),
      new THREE.MeshStandardMaterial({ color: "#232730", roughness: 0.88 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    // Hamster-scale placeholder capsule (~14 cm long, ~7.2 cm diameter)
    const capsuleGeo = new THREE.CapsuleGeometry(0.036, 0.068, 16, 32);
    capsuleGeo.rotateZ(Math.PI / 2);

    const subjectGroup = new THREE.Group();
    subjectGroup.position.set(0, 0.046, 0);
    scene.add(subjectGroup);

    const shellFur = createShellFurGroup(capsuleGeo, paramsRef.current);
    const finsFur = createSilhouetteFinsMesh(capsuleGeo, paramsRef.current);
    const strandFur = createStrandInstancedMesh(capsuleGeo, paramsRef.current, 12000);
    const baseCore = new THREE.Mesh(
      capsuleGeo,
      new THREE.MeshStandardMaterial({ color: "#6b4423", roughness: 0.85 })
    );

    subjectGroup.add(shellFur.group);
    subjectGroup.add(finsFur.mesh);
    subjectGroup.add(baseCore);
    subjectGroup.add(strandFur.mesh);

    let rafId = 0;
    let lastTime = performance.now();
    let hudTimer = 0;

    const animate = (now: number) => {
      rafId = requestAnimationFrame(animate);
      const dtMs = Math.max(0.1, now - lastTime);
      lastTime = now;
      const tSec = now * 0.001;

      const cur = paramsRef.current;
      const showShells = cur.technique === "shells" || cur.technique === "shells-fins";
      const showFins = cur.technique === "shells-fins";
      const showStrands = cur.technique === "webgpu-strands";

      shellFur.group.visible = showShells;
      finsFur.mesh.visible = showFins;
      baseCore.visible = showStrands;
      strandFur.mesh.visible = showStrands;

      if (showShells) shellFur.updateUniforms(cur, tSec);
      if (showFins) finsFur.updateUniforms(cur, tSec);
      if (showStrands) strandFur.updateUniforms(cur, tSec);

      subjectGroup.rotation.y = tSec * 0.35;
      controls.update();
      renderer.render(scene, camera);

      const ft = frameTimesRef.current;
      ft.push(dtMs);
      if (ft.length > 120) ft.shift();

      hudTimer += dtMs;
      if (hudTimer >= 250 && ft.length > 0) {
        hudTimer = 0;
        const sorted = [...ft].sort((a, b) => a - b);
        const avgMs = ft.reduce((s, v) => s + v, 0) / ft.length;
        const p95Ms = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))];
        const nextMetrics: FrameMetrics = {
          fps: 1000 / avgMs,
          frameTimeMs: avgMs,
          p95FrameTimeMs: p95Ms,
          drawCalls: renderer.info.render.calls,
          triangles: renderer.info.render.triangles,
        };
        latestMetricsRef.current = nextMetrics;
        setMetrics(nextMetrics);
      }
    };

    rafId = requestAnimationFrame(animate);

    const onResize = () => {
      if (!container) return;
      const w = container.clientWidth || 960;
      const h = container.clientHeight || 540;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      shellFur.dispose();
      finsFur.dispose();
      strandFur.dispose();
      capsuleGeo.dispose();
      renderer.dispose();
    };
  }, []);

  const runSuite = async () => {
    setIsBenchmarking(true);
    const results: FurBenchmarkResult[] = [];
    const techniques: FurTechnique[] = ["shells", "shells-fins", "webgpu-strands"];
    const original = paramsRef.current;

    for (const tech of techniques) {
      if (tech === "webgpu-strands" && !webgpuInfo.supported) {
        results.push({
          technique: tech,
          supported: false,
          avgFps: 0,
          avgFrameTimeMs: 0,
          p95FrameTimeMs: 0,
          drawCalls: 0,
          triangles: 0,
          shellCount: original.shellCount,
          notes: `Skipped: ${webgpuInfo.detail}`,
        });
        continue;
      }

      setParams((prev) => ({ ...prev, technique: tech }));
      frameTimesRef.current = [];
      await new Promise((r) => setTimeout(r, 1500));

      const m = latestMetricsRef.current;
      results.push({
        technique: tech,
        supported: true,
        avgFps: Number(m.fps.toFixed(1)),
        avgFrameTimeMs: Number(m.frameTimeMs.toFixed(2)),
        p95FrameTimeMs: Number(m.p95FrameTimeMs.toFixed(2)),
        drawCalls: m.drawCalls,
        triangles: m.triangles,
        shellCount: original.shellCount,
        notes: tech === "webgpu-strands" ? `WebGPU adapter: ${webgpuInfo.detail}` : undefined,
      });
    }

    setParams(original);
    setBenchmarkResults(results);
    (window as unknown as { __FUR_BENCHMARK_RESULTS__?: FurBenchmarkResult[] }).__FUR_BENCHMARK_RESULTS__ = results;
    setIsBenchmarking(false);
  };

  return (
    <div className="phase3-layout" data-testid="fur-benchmark-view">
      <div className="phase3-viewport-wrap">
        <div ref={mountRef} className="phase3-canvas-mount" />
        <div className="perf-hud" data-testid="fur-perf-hud">
          <div>
            <strong>Technique:</strong> {params.technique}
          </div>
          <div>
            <strong>FPS:</strong> {metrics.fps.toFixed(1)} ({metrics.frameTimeMs.toFixed(2)} ms avg /{" "}
            {metrics.p95FrameTimeMs.toFixed(2)} ms P95)
          </div>
          <div>
            <strong>Draw calls:</strong> {metrics.drawCalls} | <strong>Triangles:</strong>{" "}
            {metrics.triangles.toLocaleString()}
          </div>
          <div>
            <strong>WebGPU:</strong> {webgpuInfo.supported ? `Available (${webgpuInfo.detail})` : `Unavailable (${webgpuInfo.detail})`}
          </div>
        </div>
      </div>

      <aside className="phase3-panel">
        <h2>P3.1 Fur Rendering Benchmark</h2>
        <p className="panel-subtitle">Hamster-scale capsule (0.14 m) — compare real-time fur techniques.</p>

        <div className="control-group">
          <label>
            Technique
            <select
              value={params.technique}
              onChange={(e) => setParams({ ...params, technique: e.target.value as FurTechnique })}
            >
              <option value="shells">(a) Shell Texturing</option>
              <option value="shells-fins">(b) Shells + Silhouette Fins</option>
              <option value="webgpu-strands" disabled={!webgpuInfo.supported}>
                (c) WebGPU Strands {webgpuInfo.supported ? "" : "(Unsupported)"}
              </option>
            </select>
          </label>
        </div>

        <div className="control-group">
          <label>
            Shell Count ({params.shellCount})
            <input
              type="range"
              min={4}
              max={48}
              step={2}
              value={params.shellCount}
              onChange={(e) => setParams({ ...params, shellCount: Number(e.target.value) })}
            />
          </label>
          <label>
            Hair Length ({(params.hairLength * 1000).toFixed(1)} mm)
            <input
              type="range"
              min={0.004}
              max={0.024}
              step={0.001}
              value={params.hairLength}
              onChange={(e) => setParams({ ...params, hairLength: Number(e.target.value) })}
            />
          </label>
          <label>
            Density ({params.density})
            <input
              type="range"
              min={60}
              max={360}
              step={10}
              value={params.density}
              onChange={(e) => setParams({ ...params, density: Number(e.target.value) })}
            />
          </label>
          <label>
            Clumping ({params.clumping.toFixed(2)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={params.clumping}
              onChange={(e) => setParams({ ...params, clumping: Number(e.target.value) })}
            />
          </label>
          <label>
            Gravity Droop ({params.gravityDroop.toFixed(2)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={params.gravityDroop}
              onChange={(e) => setParams({ ...params, gravityDroop: Number(e.target.value) })}
            />
          </label>
          <label>
            Wind Strength ({params.windStrength.toFixed(2)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={params.windStrength}
              onChange={(e) => setParams({ ...params, windStrength: Number(e.target.value) })}
            />
          </label>
          <label>
            Rim Light Strength ({params.rimLightStrength.toFixed(2)})
            <input
              type="range"
              min={0}
              max={2}
              step={0.05}
              value={params.rimLightStrength}
              onChange={(e) => setParams({ ...params, rimLightStrength: Number(e.target.value) })}
            />
          </label>
        </div>

        <button className="btn btn-primary" onClick={runSuite} disabled={isBenchmarking}>
          {isBenchmarking ? "Running Benchmark Suite..." : "Run Automated Benchmark"}
        </button>

        {benchmarkResults.length > 0 && (
          <div className="benchmark-table-wrap" data-testid="fur-benchmark-results">
            <h3>Measured Results</h3>
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th>Technique</th>
                  <th>FPS</th>
                  <th>Avg ms</th>
                  <th>P95 ms</th>
                  <th>Calls</th>
                </tr>
              </thead>
              <tbody>
                {benchmarkResults.map((r) => (
                  <tr key={r.technique}>
                    <td>{r.technique}</td>
                    <td>{r.supported ? r.avgFps : "Skipped"}</td>
                    <td>{r.supported ? r.avgFrameTimeMs : "—"}</td>
                    <td>{r.supported ? r.p95FrameTimeMs : "—"}</td>
                    <td>{r.supported ? r.drawCalls : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </aside>
    </div>
  );
};

