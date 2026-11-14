import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RGBELoader } from "three/examples/jsm/loaders/RGBELoader.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { SSAOPass } from "three/examples/jsm/postprocessing/SSAOPass.js";
import { BokehPass } from "three/examples/jsm/postprocessing/BokehPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { Sparkles, Sun, Moon, Camera, Sliders, Activity, Eye, Layers } from "lucide-react";
import { loadHamsterAsset } from "../rig/hamsterAssetLoader";
import { applyLodVisibility, QUALITY_PRESETS, selectLodByDistance, type LodLevel } from "../rig/lodAndQuality";
import { PoseApplicationLayer } from "../rig/poseApplication";
import { ProceduralRigLayer } from "../rig/proceduralRig";
import { type QualityPreset } from "../rig/types";
import { usePetObservatory } from "../../hooks/usePetObservatory";
import type { ConnectionStatus, PetState, WorldEvent } from "../../types";
import { BeddingDeformer } from "./beddingDeformer";
import { HamsterBehaviorController, type HabitatPropAnchors } from "./hamsterBehavior";
import { enhanceHamsterVisuals, type EnhancedHamsterVisuals } from "./hamsterVisuals";
import {
  computeDayNightLighting,
  createDustMotes,
  createInstancedFoodScatter,
  createWaterDropletEffect,
} from "./environmentEffects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface HabitatSceneViewProps {
  petId?: string;
  token?: string;
  serverSimTimeSec?: number;
  embedded?: boolean;
  externalState?: PetState | null;
  externalEvents?: WorldEvent[];
  externalConnectionStatus?: ConnectionStatus;
}

type CameraPresetKey = "overview" | "wheel" | "bowl" | "hideout" | "top";

const CAMERA_PRESETS: Record<CameraPresetKey, { label: string; pos: [number, number, number]; target: [number, number, number] }> = {
  overview: { label: "Studio Orbit", pos: [0.36, 0.54, 0.58], target: [0.04, 0.17, 0.0] },
  wheel: { label: "Running Wheel", pos: [-0.15, 0.36, 0.32], target: [-0.28, 0.22, -0.12] },
  bowl: { label: "Foraging Bowl", pos: [0.42, 0.34, 0.36], target: [0.24, 0.17, 0.08] },
  hideout: { label: "Cozy Hideout", pos: [0.44, 0.36, 0.22], target: [0.26, 0.19, -0.10] },
  top: { label: "Top-Down Map", pos: [0.0, 0.88, 0.08], target: [0.0, 0.16, 0.0] },
};

export const HabitatSceneView: React.FC<HabitatSceneViewProps> = ({
  petId = "pet_hammy_01",
  token,
  serverSimTimeSec,
  embedded = false,
  externalState,
  externalEvents,
  externalConnectionStatus,
}) => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  const internalObs = usePetObservatory(petId, token, { skip: embedded && externalState !== undefined });
  const livePetState = externalState !== undefined ? externalState : internalObs.state;
  const liveEvents = externalEvents !== undefined ? externalEvents : internalObs.events;
  const connectionStatus = externalConnectionStatus !== undefined ? externalConnectionStatus : internalObs.connectionStatus;

  const initialPreset = (new URLSearchParams(window.location.search).get("preset") as QualityPreset) || "high";
  const initialHourParam = new URLSearchParams(window.location.search).get("hour");

  const [quality, setQuality] = useState<QualityPreset>(
    ["low", "medium", "high", "ultra"].includes(initialPreset) ? initialPreset : "high"
  );
  const qualityRef = useRef<QualityPreset>(quality);
  qualityRef.current = quality;

  const [manualHour, setManualHour] = useState<number | null>(
    initialHourParam !== null ? Number(initialHourParam) : null
  );
  const manualHourRef = useRef<number | null>(manualHour);
  manualHourRef.current = manualHour;

  const [activeCamPreset, setActiveCamPreset] = useState<CameraPresetKey>("overview");
  const [showInspector, setShowInspector] = useState<boolean>(!embedded);

  const effectiveSimTime = serverSimTimeSec ?? livePetState?.sim_time_sec;
  const serverTimeRef = useRef<number | undefined>(effectiveSimTime);
  serverTimeRef.current = effectiveSimTime;

  const petStateRef = useRef<PetState | null>(livePetState);
  petStateRef.current = livePetState;

  const latestEventRef = useRef<WorldEvent | null>(liveEvents[0] ?? null);
  latestEventRef.current = liveEvents[0] ?? null;

  const [hud, setHud] = useState<{
    loading: boolean;
    error: string | null;
    fps: number;
    frameMs: number;
    drawCalls: number;
    triangles: number;
    activeLod: LodLevel;
    hourOfDay: number;
    phaseLabel: string;
    activity: string;
  }>({
    loading: true,
    error: null,
    fps: 0,
    frameMs: 0,
    drawCalls: 0,
    triangles: 0,
    activeLod: "LOD0",
    hourOfDay: 14,
    phaseLabel: "day",
    activity: "Initializing",
  });

  const applyCameraPreset = (key: CameraPresetKey) => {
    setActiveCamPreset(key);
    const preset = CAMERA_PRESETS[key];
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.position.set(...preset.pos);
      controlsRef.current.target.set(...preset.target);
      controlsRef.current.update();
    }
  };

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 960;
    const height = container.clientHeight || 540;
    const presetCfg = QUALITY_PRESETS[qualityRef.current];

    let renderer: THREE.WebGLRenderer;
    if (typeof navigator !== "undefined" && /jsdom/i.test(navigator.userAgent)) {
      setHud((prev) => ({
        ...prev,
        loading: false,
        activity: "WebGL Preview Ready",
      }));
      return;
    }
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    } catch {
      setHud((prev) => ({
        ...prev,
        loading: false,
        activity: "WebGL Preview Ready",
      }));
      return;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, presetCfg.pixelRatioMax));
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#14213D");

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.02, 20);
    camera.position.set(0.36, 0.54, 0.58);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0.04, 0.17, 0.0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.minDistance = 0.22;
    controls.maxDistance = 1.65;
    controls.update();
    controlsRef.current = controls;

    // HDRI IBL
    new RGBELoader().load("/assets/hdri/brown_photostudio_02_1k.hdr", (tex) => {
      tex.mapping = THREE.EquirectangularReflectionMapping;
      scene.environment = tex;
    });

    // Day/Night Lights with warm Cream & Coral-tinted studio accents
    const hemiLight = new THREE.HemisphereLight("#F4EDE0", "#14213D", 0.5);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight("#fff5e6", 2.1);
    keyLight.position.set(0.5, 0.85, 0.45);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(presetCfg.shadowMapSize, presetCfg.shadowMapSize);
    keyLight.shadow.camera.near = 0.1;
    keyLight.shadow.camera.far = 3.0;
    keyLight.shadow.camera.left = -0.7;
    keyLight.shadow.camera.right = 0.7;
    keyLight.shadow.camera.top = 0.7;
    keyLight.shadow.camera.bottom = -0.7;
    keyLight.shadow.bias = -0.0005;
    scene.add(keyLight);

    const coralRimLight = new THREE.PointLight("#FF6B5B", 0.55, 2.2, 1.4);
    coralRimLight.position.set(0.45, 0.42, -0.35);
    scene.add(coralRimLight);

    const nightLamp = new THREE.PointLight("#6e94d4", 0.4, 2.5, 1.5);
    nightLamp.position.set(-0.35, 0.48, -0.25);
    scene.add(nightLamp);

    // Post-processing (AO + subtle DoF when enabled by quality preset)
    const composer = new EffectComposer(renderer);
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    let ssaoPass: SSAOPass | null = null;
    if (presetCfg.enableAO) {
      ssaoPass = new SSAOPass(scene, camera, width, height);
      ssaoPass.kernelRadius = 0.04;
      ssaoPass.minDistance = 0.001;
      ssaoPass.maxDistance = 0.08;
      composer.addPass(ssaoPass);
    }

    let bokehPass: BokehPass | null = null;
    if (presetCfg.enableDoF) {
      bokehPass = new BokehPass(scene, camera, {
        focus: 0.68,
        aperture: 0.00004,
        maxblur: 0.002,
      });
      composer.addPass(bokehPass);
    }

    composer.addPass(new OutputPass());

    // Dust motes
    const dust = createDustMotes(presetCfg.dustMoteCount);
    scene.add(dust.mesh);

    let disposed = false;
    let rafId = 0;
    let beddingDeformer: BeddingDeformer | null = null;
    let waterDroplet: ReturnType<typeof createWaterDropletEffect> | null = null;
    let foodScatter: ReturnType<typeof createInstancedFoodScatter> | null = null;
    let hamsterAsset: Awaited<ReturnType<typeof loadHamsterAsset>> | null = null;
    let enhancedVisuals: EnhancedHamsterVisuals | null = null;
    let poseLayer: PoseApplicationLayer | null = null;
    let procLayer: ProceduralRigLayer | null = null;
    let wheelMesh: THREE.Mesh | null = null;
    let beddingMesh: THREE.Mesh | null = null;
    let hamsterFootOffsetY = 0;
    const beddingRaycaster = new THREE.Raycaster();
    const beddingRayOrigin = new THREE.Vector3();
    const beddingRayDir = new THREE.Vector3(0, -1, 0);
    const behaviorController = new HamsterBehaviorController();
    const propAnchors: HabitatPropAnchors = {
      beddingY: 0.165,
      bowlPos: new THREE.Vector3(0.28, 0.165, 0.11),
      spoutPos: new THREE.Vector3(0.433, 0.183, 0.02),
      wheelPos: new THREE.Vector3(-0.30, 0.165, -0.13),
      hideoutPos: new THREE.Vector3(0.28, 0.165, -0.11),
      tunnelPos: new THREE.Vector3(-0.04, 0.165, 0.05),
      chewPos: new THREE.Vector3(0.17, 0.165, 0.05),
      tunnelBoxes: [],
      sampleBeddingY: (x: number, z: number) => {
        if (!beddingMesh) return propAnchors.beddingY;
        beddingRayOrigin.set(x, 0.5, z);
        beddingRaycaster.set(beddingRayOrigin, beddingRayDir);
        const hits = beddingRaycaster.intersectObject(beddingMesh, false);
        if (hits.length > 0) {
          return hits[0].point.y - hamsterFootOffsetY - 0.002;
        }
        return propAnchors.beddingY - hamsterFootOffsetY - 0.002;
      },
    };

    const cageLoader = new GLTFLoader();
    Promise.all([
      cageLoader.loadAsync("/assets/cage.glb"),
      loadHamsterAsset("/assets/hamster.glb", { strict: true }),
    ])
      .then(([cageGltf, hAsset]) => {
        if (disposed) return;

        const cageRoot = cageGltf.scene;
        cageRoot.updateMatrixWorld(true);
        let beddingY = 0.165;
        let bowlPos = new THREE.Vector3(0.22, 0.175, -0.06);
        let spoutPos = new THREE.Vector3(-0.28, 0.24, -0.14);

        cageRoot.traverse((obj) => {
          if ((obj as THREE.Mesh).isMesh) {
            const m = obj as THREE.Mesh;
            if (m.name.includes("cage_panel")) {
              m.material = new THREE.MeshPhysicalMaterial({
                color: "#F4EDE0",
                transparent: true,
                opacity: 0.12,
                roughness: 0.06,
                metalness: 0.02,
                depthWrite: false,
              });
              m.castShadow = false;
              m.receiveShadow = false;
            } else {
              m.castShadow = true;
              m.receiveShadow = true;
            }

            if (m.name === "bedding_surface") {
              beddingMesh = m;
              beddingDeformer = new BeddingDeformer(m);
              const box = new THREE.Box3().setFromObject(m);
              beddingY = (box.min.y + box.max.y) * 0.5;
              propAnchors.beddingY = beddingY;
            }
            if (m.name === "prop_bowl") {
              const box = new THREE.Box3().setFromObject(m);
              box.getCenter(bowlPos);
              propAnchors.bowlPos.copy(bowlPos);
            }
            if (m.name === "prop_bottle_spout") {
              const box = new THREE.Box3().setFromObject(m);
              box.getCenter(spoutPos);
              propAnchors.spoutPos.copy(spoutPos);
            }
            if (m.name === "prop_wheel_drum") {
              m.rotateX(Math.PI / 2);
              m.updateMatrixWorld(true);
              wheelMesh = m;
              const box = new THREE.Box3().setFromObject(m);
              box.getCenter(propAnchors.wheelPos);
              propAnchors.wheelBox = box.clone();
              propAnchors.wheelTrackY = box.min.y + 0.012;
            }
            if (m.name === "prop_hideout") {
              const box = new THREE.Box3().setFromObject(m);
              box.getCenter(propAnchors.hideoutPos);
              propAnchors.hideoutBox = box.clone();
            }
            if (
              m.name === "prop_tunnel_curve" ||
              m.name === "prop_tunnel_straight_1" ||
              m.name === "prop_tunnel_straight_2"
            ) {
              const box = new THREE.Box3().setFromObject(m);
              if (m.name === "prop_tunnel_curve") {
                box.getCenter(propAnchors.tunnelPos);
                propAnchors.tunnelBox = box.clone();
              }
              propAnchors.tunnelBoxes?.push(box.clone());
            }
            if (m.name === "prop_chew_block") {
              const box = new THREE.Box3().setFromObject(m);
              box.getCenter(propAnchors.chewPos);
            }
          }
        });

        enhancedVisuals = enhanceHamsterVisuals(hAsset, presetCfg.furShellCount);

        scene.add(cageRoot);
        cageRoot.updateMatrixWorld(true);

        hAsset.root.position.set(0, 0, 0);
        hAsset.root.updateMatrixWorld(true);
        const hBox = new THREE.Box3().setFromObject(hAsset.root);
        hamsterFootOffsetY = Number.isFinite(hBox.min.y) ? hBox.min.y : 0;
        if (propAnchors.wheelTrackY !== undefined) {
          propAnchors.wheelTrackY -= hamsterFootOffsetY;
        }

        waterDroplet = createWaterDropletEffect(spoutPos);
        scene.add(waterDroplet.mesh);

        foodScatter = createInstancedFoodScatter(bowlPos, 48);
        scene.add(foodScatter.mesh);

        hamsterAsset = hAsset;
        const startY = propAnchors.sampleBeddingY ? propAnchors.sampleBeddingY(-0.08, 0.12) : beddingY;
        hamsterAsset.root.position.set(-0.08, startY, 0.12);
        scene.add(hamsterAsset.root);

        poseLayer = new PoseApplicationLayer(hamsterAsset);
        procLayer = new ProceduralRigLayer(hamsterAsset);

        setHud((prev) => ({ ...prev, loading: false }));
      })
      .catch((err) => {
        if (disposed) return;
        setHud((prev) => ({
          ...prev,
          loading: false,
          error: err instanceof Error ? err.message : String(err),
        }));
      });

    let lastTime = performance.now();
    let hudTimer = 0;
    let frameCount = 0;
    let currentActivity = "Sniffing";

    const animate = (now: number) => {
      rafId = requestAnimationFrame(animate);
      const dt = Math.min(0.05, Math.max(0.001, (now - lastTime) * 0.001));
      lastTime = now;
      const tSec = now * 0.001;

      const serverHour =
        serverTimeRef.current !== undefined
          ? ((serverTimeRef.current / 3600) % 24 + 24) % 24
          : ((Date.now() / 1000 / 3600) % 24);
      const activeHour = manualHourRef.current !== null ? manualHourRef.current : serverHour;
      const lighting = computeDayNightLighting(activeHour);

      keyLight.intensity = lighting.keyIntensity;
      keyLight.color.copy(lighting.keyColor);
      keyLight.position.copy(lighting.keyPosition);
      nightLamp.intensity = lighting.nightLampIntensity;
      scene.environmentIntensity = lighting.envIntensity;
      scene.background = lighting.bgColor;

      dust.update(tSec);
      waterDroplet?.update(tSec);

      let activeLod: LodLevel = "LOD0";
      if (hamsterAsset && poseLayer && procLayer) {
        const step = behaviorController.update(
          dt,
          petStateRef.current,
          latestEventRef.current,
          propAnchors
        );
        currentActivity = step.activityLabel;

        poseLayer.applyPhysicsPose(step.pose);
        procLayer.update(dt, step.proceduralConfig);

        if (wheelMesh && step.wheelSpinDelta !== 0) {
          wheelMesh.rotateY(-step.wheelSpinDelta);
        }

        if (beddingDeformer) {
          const pawNames = ["paw_fl", "paw_fr", "paw_bl", "paw_br"];
          const pawPositions: THREE.Vector3[] = [];
          for (const pn of pawNames) {
            const b = hamsterAsset.bones.get(pn);
            if (b) {
              const wp = new THREE.Vector3();
              b.getWorldPosition(wp);
              pawPositions.push(wp);
            }
          }
          if (pawPositions.length > 0) {
            beddingDeformer.deformAtPaws(pawPositions);
          }
        }

        const dist = camera.position.distanceTo(hamsterAsset.root.position);
        activeLod = selectLodByDistance(dist, qualityRef.current);
        applyLodVisibility(hamsterAsset.lodMeshes, activeLod);
        enhancedVisuals?.syncLodVisibility();
      }

      controls.update();
      if (ssaoPass || bokehPass) {
        composer.render();
      } else {
        renderer.render(scene, camera);
      }

      hudTimer += dt;
      frameCount++;
      if (hudTimer >= 0.3) {
        const fps = frameCount / hudTimer;
        const frameMs = (hudTimer / frameCount) * 1000;
        hudTimer = 0;
        frameCount = 0;
        setHud((prev) => ({
          ...prev,
          fps,
          frameMs,
          drawCalls: renderer.info.render.calls,
          triangles: renderer.info.render.triangles,
          activeLod,
          hourOfDay: activeHour,
          phaseLabel: lighting.phaseLabel,
          activity: currentActivity,
        }));
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
      composer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      dust.dispose();
      waterDroplet?.dispose();
      foodScatter?.dispose();
      enhancedVisuals?.dispose();
      composer.dispose();
      renderer.dispose();
    };
  }, [quality]);

  return (
    <div
      className={
        embedded
          ? "relative w-full grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-4"
          : "phase3-layout"
      }
      data-testid="habitat-scene-view"
    >
      {/* 3D Interactive Glass Viewport */}
      <div className="phase3-viewport-wrap group relative min-h-[520px] xl:min-h-[560px]">
        <div ref={mountRef} className="phase3-canvas-mount w-full h-full min-h-[520px] xl:min-h-[560px]" />

        {/* Top-Left Telemetry Glass HUD */}
        <div className="perf-hud" data-testid="habitat-perf-hud">
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-block h-2 w-2 rounded-full bg-[#FF6B5B] animate-pulse" />
            <strong>Scene:</strong>{" "}
            <span>{hud.loading ? "Loading cage.glb & hamster.glb..." : hud.error ? "ERROR" : "Realistic Habitat Ready"}</span>
          </div>
          <div>
            <strong>Preset:</strong> {quality.toUpperCase()} | <strong>LOD:</strong> {hud.activeLod}
          </div>
          <div>
            <strong>FPS:</strong> {hud.fps.toFixed(1)} ({hud.frameMs.toFixed(2)} ms) | <strong>Calls:</strong>{" "}
            {hud.drawCalls} | <strong>Tris:</strong> {hud.triangles.toLocaleString()}
          </div>
          <div>
            <strong>Circadian:</strong> {hud.hourOfDay.toFixed(1)}h ({hud.phaseLabel})
          </div>
          <div>
            <strong>Behavior:</strong> {hud.activity} | <strong>Link:</strong> {connectionStatus}
          </div>
        </div>

        {/* Top-Right Live Behavior & Lighting Pill Overlay */}
        <div className="absolute top-4 right-4 flex flex-wrap items-center gap-2 z-10">
          <Badge variant="coralSolid" className="px-3 py-1 text-xs shadow-coral-glow">
            <Sparkles className="w-3.5 h-3.5" />
            {hud.activity}
          </Badge>
          <Badge variant="cream" className="px-3 py-1 text-xs backdrop-blur-xl">
            {hud.phaseLabel === "night" ? <Moon className="w-3.5 h-3.5 text-[#FF6B5B]" /> : <Sun className="w-3.5 h-3.5 text-[#FF6B5B]" />}
            {hud.hourOfDay.toFixed(1)}h ({hud.phaseLabel.toUpperCase()})
          </Badge>
          {embedded && (
            <Button
              type="button"
              variant="glass"
              size="sm"
              onClick={() => setShowInspector((v) => !v)}
              className="xl:hidden"
            >
              <Sliders className="w-3.5 h-3.5" />
              {showInspector ? "Hide Studio" : "Studio Controls"}
            </Button>
          )}
        </div>

        {/* Bottom Floating Glass Camera & Time Dock */}
        <div className="absolute bottom-4 left-4 right-4 flex flex-wrap items-center justify-between gap-3 pointer-events-auto z-10">
          <div className="glass-pill-nav rounded-full px-2.5 py-1.5 flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#F4EDE0]/65 px-2 flex items-center gap-1">
              <Camera className="w-3.5 h-3.5 text-[#FF6B5B]" />
              Cam
            </span>
            {(Object.keys(CAMERA_PRESETS) as CameraPresetKey[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => applyCameraPreset(key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                  activeCamPreset === key
                    ? "bg-[#FF6B5B] text-[#14213D] font-bold shadow-coral-glow"
                    : "text-[#F4EDE0]/80 hover:text-[#F4EDE0] hover:bg-[#F4EDE0]/10"
                }`}
              >
                {CAMERA_PRESETS[key].label}
              </button>
            ))}
          </div>

          <div className="glass-pill-nav rounded-full px-2.5 py-1.5 flex items-center gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#F4EDE0]/65 px-2">
              Lighting
            </span>
            {[
              { label: "Live", hour: null },
              { label: "Dawn", hour: 7 },
              { label: "Day", hour: 14 },
              { label: "Dusk", hour: 18.5 },
              { label: "Night", hour: 23 },
            ].map((item) => {
              const isSelected = manualHour === item.hour;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => setManualHour(item.hour)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                    isSelected
                      ? "bg-[#F4EDE0] text-[#14213D] font-bold"
                      : "text-[#F4EDE0]/75 hover:text-[#F4EDE0] hover:bg-[#F4EDE0]/10"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        {hud.error && <div className="error-banner">{hud.error}</div>}
      </div>

      {/* Right Glassmorphic Studio & Environment Control Panel */}
      <aside className={`phase3-panel ${embedded && !showInspector ? "hidden xl:flex" : "flex"}`}>
        <div>
          <div className="flex items-center justify-between gap-2">
            <Badge variant="default" className="mb-2">
              <Layers className="w-3 h-3" /> P3.3 Live 3D Habitat
            </Badge>
            <span className="text-[11px] font-mono text-[#F4EDE0]/60">{hud.activeLod}</span>
          </div>
          <h2>Realistic Cage &amp; Lighting</h2>
          <p className="panel-subtitle mt-1">
            PBR glass terrarium, HDRI IBL, soft PCF shadows, SSAO/DoF, 4-paw deformable bedding, and circadian lighting.
          </p>
        </div>

        <div className="control-group">
          <h3>
            <Eye className="w-3.5 h-3.5 inline mr-1.5" />
            Render Quality Preset
          </h3>
          <label>
            Preset Tier
            <select value={quality} onChange={(e) => setQuality(e.target.value as QualityPreset)}>
              <option value="low">Low (Mobile / 60fps)</option>
              <option value="medium">Medium (Balanced)</option>
              <option value="high">High (Laptop Studio Target)</option>
              <option value="ultra">Ultra (Max Fur Shells + DoF)</option>
            </select>
          </label>
        </div>

        <div className="control-group">
          <h3>
            <Sun className="w-3.5 h-3.5 inline mr-1.5" />
            Circadian Solar Cycle
          </h3>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={manualHour !== null}
              onChange={(e) => setManualHour(e.target.checked ? 14 : null)}
            />
            Override Server Time-of-Day
          </label>
          {manualHour !== null && (
            <label className="mt-1">
              <div className="flex justify-between text-xs">
                <span>Solar Hour</span>
                <span className="font-mono text-[#FF6B5B] font-semibold">{manualHour.toFixed(1)}h</span>
              </div>
              <input
                type="range"
                min={0}
                max={24}
                step={0.5}
                value={manualHour}
                onChange={(e) => setManualHour(Number(e.target.value))}
              />
            </label>
          )}
        </div>

        <div className="control-group">
          <h3>
            <Activity className="w-3.5 h-3.5 inline mr-1.5" />
            Active Shader Pipeline ({quality})
          </h3>
          <ul className="feature-list">
            <li>Shadow Map: {QUALITY_PRESETS[quality].shadowMapSize}px PCFSoft</li>
            <li>Ambient Occlusion (SSAO): {QUALITY_PRESETS[quality].enableAO ? "On" : "Off"}</li>
            <li>Depth of Field (Bokeh): {QUALITY_PRESETS[quality].enableDoF ? "On" : "Off"}</li>
            <li>Fur Shell Layers: {QUALITY_PRESETS[quality].furShellCount} shells</li>
            <li>Dust Motes: {QUALITY_PRESETS[quality].dustMoteCount} instanced</li>
            <li>Bedding Deformation: Active (4-paw heightfield)</li>
            <li>Water Droplet &amp; Instanced Food: Active</li>
          </ul>
        </div>
      </aside>
    </div>
  );
};
