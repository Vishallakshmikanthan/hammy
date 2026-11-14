import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RGBELoader } from "three/examples/jsm/loaders/RGBELoader.js";
import { loadHamsterAsset } from "./hamsterAssetLoader";
import { applyLodVisibility, QUALITY_PRESETS, selectLodByDistance, type LodLevel } from "./lodAndQuality";
import { PoseApplicationLayer } from "./poseApplication";
import { ProceduralRigLayer } from "./proceduralRig";
import {
  DEFAULT_PROCEDURAL_CONFIG,
  type HamsterValidationReport,
  type ProceduralLayerConfig,
  type QualityPreset,
} from "./types";

export const RigStudioView: React.FC = () => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [config, setConfig] = useState<ProceduralLayerConfig>(DEFAULT_PROCEDURAL_CONFIG);
  const configRef = useRef<ProceduralLayerConfig>(config);
  configRef.current = config;

  const [quality, setQuality] = useState<QualityPreset>("high");
  const qualityRef = useRef<QualityPreset>(quality);
  qualityRef.current = quality;

  const [walkDemo, setWalkDemo] = useState(false);
  const walkDemoRef = useRef(walkDemo);
  walkDemoRef.current = walkDemo;

  const [lodOverride, setLodOverride] = useState<"auto" | LodLevel>("auto");
  const lodOverrideRef = useRef(lodOverride);
  lodOverrideRef.current = lodOverride;

  const [status, setStatus] = useState<{
    loading: boolean;
    error: string | null;
    validation: HamsterValidationReport | null;
    activeLod: LodLevel;
    fps: number;
    camDistance: number;
  }>({
    loading: true,
    error: null,
    validation: null,
    activeLod: "LOD0",
    fps: 0,
    camDistance: 0.25,
  });

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 960;
    const height = container.clientHeight || 540;

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, QUALITY_PRESETS[qualityRef.current].pixelRatioMax));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#181b20");

    const camera = new THREE.PerspectiveCamera(35, width / height, 0.01, 20);
    camera.position.set(0.18, 0.11, 0.22);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.032, 0);
    controls.enableDamping = true;
    controls.update();

    // HDRI + Studio Lighting
    new RGBELoader().load(
      "/assets/hdri/brown_photostudio_02_1k.hdr",
      (tex) => {
        tex.mapping = THREE.EquirectangularReflectionMapping;
        scene.environment = tex;
        scene.environmentIntensity = 0.85;
      },
      undefined,
      () => {
        scene.add(new THREE.HemisphereLight("#fff4e4", "#2a231c", 0.7));
      }
    );

    const key = new THREE.DirectionalLight("#fff5e6", 2.0);
    key.position.set(0.4, 0.7, 0.4);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    scene.add(key);

    const rim = new THREE.DirectionalLight("#ffd19c", 1.1);
    rim.position.set(-0.4, 0.35, -0.4);
    scene.add(rim);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(0.4, 48),
      new THREE.MeshStandardMaterial({ color: "#262a33", roughness: 0.9 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    let disposed = false;
    let rafId = 0;
    let poseLayer: PoseApplicationLayer | null = null;
    let procLayer: ProceduralRigLayer | null = null;
    let loadedAsset: Awaited<ReturnType<typeof loadHamsterAsset>> | null = null;

    loadHamsterAsset("/assets/hamster.glb", { strict: true })
      .then((asset) => {
        if (disposed) return;
        loadedAsset = asset;
        // Apply realistic Syrian golden-agouti coat, glossy cornea eyes, and moist pink nose/paws
        asset.root.traverse((obj) => {
          if (!(obj as THREE.Mesh).isMesh) return;
          const m = obj as THREE.Mesh;
          if (m.name.includes("ham_body")) {
            m.material = new THREE.MeshStandardMaterial({
              color: "#c6894b",
              roughness: 0.92,
              metalness: 0.0,
            });
          } else if (m.name.includes("ham_eye")) {
            m.material = new THREE.MeshPhysicalMaterial({
              color: "#09090c",
              roughness: 0.04,
              metalness: 0.0,
              clearcoat: 1.0,
              clearcoatRoughness: 0.03,
            });
          } else if (m.name.includes("ham_nose")) {
            m.material = new THREE.MeshPhysicalMaterial({
              color: "#e69a9f",
              roughness: 0.25,
              clearcoat: 0.7,
            });
          } else if (m.name.includes("ham_ear") || m.name.includes("ham_paw") || m.name.includes("ham_tail")) {
            m.material = new THREE.MeshStandardMaterial({
              color: "#dfb0a8",
              roughness: 0.78,
            });
          }
        });
        scene.add(asset.root);
        poseLayer = new PoseApplicationLayer(asset);
        procLayer = new ProceduralRigLayer(asset);
        setStatus((prev) => ({
          ...prev,
          loading: false,
          validation: asset.validation,
        }));
      })
      .catch((err) => {
        if (disposed) return;
        setStatus((prev) => ({
          ...prev,
          loading: false,
          error: err instanceof Error ? err.message : String(err),
        }));
      });

    let lastTime = performance.now();
    let hudTimer = 0;
    let frameCount = 0;
    let gaitPhase = 0;

    const animate = (now: number) => {
      rafId = requestAnimationFrame(animate);
      const dt = Math.min(0.05, Math.max(0.001, (now - lastTime) * 0.001));
      lastTime = now;

      if (loadedAsset && poseLayer && procLayer) {
        const walking = walkDemoRef.current;
        if (walking) {
          gaitPhase += dt * 11.0;
        }
        poseLayer.applyPhysicsPose({
          rootPosition: walking ? [Math.sin(now * 0.0008) * 0.015, Math.abs(Math.sin(gaitPhase)) * 0.003, 0] : [0, 0, 0],
          rootQuaternion: [0, 0, 0, 1],
          velocity: walking ? [0, 0, 0.22] : [0, 0, 0],
          angularVelocity: [0, 0, 0],
          footContacts: {
            fl: !walking || Math.sin(gaitPhase) > 0,
            fr: !walking || Math.sin(gaitPhase + Math.PI) > 0,
            bl: !walking || Math.sin(gaitPhase + Math.PI) > 0,
            br: !walking || Math.sin(gaitPhase) > 0,
          },
          gaitPhase,
        });
        procLayer.update(dt, configRef.current);

        const dist = camera.position.distanceTo(loadedAsset.root.position);
        const activeLod =
          lodOverrideRef.current === "auto" ? selectLodByDistance(dist, qualityRef.current) : lodOverrideRef.current;
        applyLodVisibility(loadedAsset.lodMeshes, activeLod);

        hudTimer += dt;
        frameCount++;
        if (hudTimer >= 0.3) {
          const fps = frameCount / hudTimer;
          hudTimer = 0;
          frameCount = 0;
          setStatus((prev) => ({ ...prev, activeLod, fps, camDistance: dist }));
        }
      }

      controls.update();
      renderer.render(scene, camera);
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
      disposed = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div className="phase3-layout" data-testid="rig-studio-view">
      <div className="phase3-viewport-wrap">
        <div ref={mountRef} className="phase3-canvas-mount" />
        <div className="perf-hud" data-testid="rig-perf-hud">
          <div>
            <strong>Asset:</strong> {status.loading ? "Loading hamster.glb..." : status.error ? "ERROR" : "hamster.glb Validated"}
          </div>
          <div>
            <strong>Active LOD:</strong> {status.activeLod} ({status.camDistance.toFixed(2)} m) | <strong>Preset:</strong> {quality}
          </div>
          <div>
            <strong>FPS:</strong> {status.fps.toFixed(1)}
          </div>
          {status.validation && (
            <div>
              <strong>Bones:</strong> {status.validation.foundBones.length} | <strong>Morphs:</strong>{" "}
              {status.validation.foundBlendShapes.length} | <strong>LODs:</strong> {status.validation.foundLods.length}
            </div>
          )}
        </div>
        {status.error && (
          <div className="error-banner" data-testid="rig-asset-error">
            {status.error}
          </div>
        )}
      </div>

      <aside className="phase3-panel">
        <h2>P3.2 Hamster Rig &amp; Procedural Studio</h2>
        <p className="panel-subtitle">Toggle and tune each procedural animation module on the rigged glTF.</p>

        <div className="control-group">
          <label>
            Quality Preset
            <select value={quality} onChange={(e) => setQuality(e.target.value as QualityPreset)}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="ultra">Ultra</option>
            </select>
          </label>
          <label>
            LOD Selection
            <select value={lodOverride} onChange={(e) => setLodOverride(e.target.value as "auto" | LodLevel)}>
              <option value="auto">Auto (Camera Distance)</option>
              <option value="LOD0">Force LOD0 (High)</option>
              <option value="LOD1">Force LOD1 (Medium)</option>
              <option value="LOD2">Force LOD2 (Low)</option>
            </select>
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={walkDemo} onChange={(e) => setWalkDemo(e.target.checked)} />
            Simulate Walk Gait (Pose Application)
          </label>
        </div>

        <div className="control-group">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.breathing.enabled}
              onChange={(e) => setConfig({ ...config, breathing: { ...config.breathing, enabled: e.target.checked } })}
            />
            Breathing ({config.breathing.rateHz.toFixed(1)} Hz)
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={config.breathing.amplitude}
            onChange={(e) =>
              setConfig({ ...config, breathing: { ...config.breathing, amplitude: Number(e.target.value) } })
            }
          />

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.whiskerTwitch.enabled}
              onChange={(e) =>
                setConfig({ ...config, whiskerTwitch: { ...config.whiskerTwitch, enabled: e.target.checked } })
              }
            />
            Whisker Twitch / Sniff ({config.whiskerTwitch.sniffHz.toFixed(1)} Hz)
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={config.whiskerTwitch.amplitude}
            onChange={(e) =>
              setConfig({ ...config, whiskerTwitch: { ...config.whiskerTwitch, amplitude: Number(e.target.value) } })
            }
          />

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.earOrientation.enabled}
              onChange={(e) =>
                setConfig({ ...config, earOrientation: { ...config.earOrientation, enabled: e.target.checked } })
              }
            />
            Ear Orientation (Alert: {config.earOrientation.alertLevel.toFixed(2)})
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={config.earOrientation.alertLevel}
            onChange={(e) =>
              setConfig({ ...config, earOrientation: { ...config.earOrientation, alertLevel: Number(e.target.value) } })
            }
          />

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.blinkAndGaze.enabled}
              onChange={(e) =>
                setConfig({ ...config, blinkAndGaze: { ...config.blinkAndGaze, enabled: e.target.checked } })
              }
            />
            Blink &amp; Gaze Micro-movements
          </label>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.tail.enabled}
              onChange={(e) => setConfig({ ...config, tail: { ...config.tail, enabled: e.target.checked } })}
            />
            Tail Stub Motion
          </label>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.springJiggle.enabled}
              onChange={(e) =>
                setConfig({ ...config, springJiggle: { ...config.springJiggle, enabled: e.target.checked } })
              }
            />
            Spring-Bone Fur/Skin Jiggle ({config.springJiggle.amplitude.toFixed(2)})
          </label>
          <input
            type="range"
            min={0}
            max={1.5}
            step={0.05}
            value={config.springJiggle.amplitude}
            onChange={(e) =>
              setConfig({ ...config, springJiggle: { ...config.springJiggle, amplitude: Number(e.target.value) } })
            }
          />

          <label>
            Cheek Pouch Left ({config.cheekPouch.leftFill.toFixed(2)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={config.cheekPouch.leftFill}
              onChange={(e) =>
                setConfig({ ...config, cheekPouch: { ...config.cheekPouch, leftFill: Number(e.target.value) } })
              }
            />
          </label>
          <label>
            Cheek Pouch Right ({config.cheekPouch.rightFill.toFixed(2)})
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={config.cheekPouch.rightFill}
              onChange={(e) =>
                setConfig({ ...config, cheekPouch: { ...config.cheekPouch, rightFill: Number(e.target.value) } })
              }
            />
          </label>
        </div>
      </aside>
    </div>
  );
};

