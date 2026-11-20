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
import { applyCostumeSocketTransform } from "../rig/costumeSockets";
import { applyLodVisibility, QUALITY_PRESETS, selectLodByDistance, type LodLevel } from "../rig/lodAndQuality";
import { PoseApplicationLayer } from "../rig/poseApplication";
import { ProceduralRigLayer } from "../rig/proceduralRig";
import { type QualityPreset } from "../rig/types";
import { usePetObservatory } from "../../hooks/usePetObservatory";
import type {
  AssetManifest,
  ConnectionStatus,
  CostumeSlot,
  ManifestAssetItem,
  PetState,
  PlacementDraft,
  ShelvesLayoutState,
  WorldEvent,
} from "../../types";
import {
  consumeFoodCommand,
  consumeWaterCommand,
  equipCostumeCommand,
  fetchAssetManifest,
  fetchShelvesState,
  movePropCommand,
  offerFoodCommand,
  placePropCommand,
  refillFoodCommand,
  refillWaterCommand,
  removePropCommand,
  resetCleanCageCommand,
  unequipCostumeCommand,
} from "../../api";
import { AssetShelfDrawer } from "../../components/AssetShelfDrawer";
import { BeddingDeformer } from "./beddingDeformer";
import { HamsterBehaviorController, type HabitatPropAnchors } from "./hamsterBehavior";
import { enhanceHamsterVisuals, type EnhancedHamsterVisuals } from "./hamsterVisuals";
import {
  computeDayNightLighting,
  createDustMotes,
  createWaterDropletEffect,
} from "./environmentEffects";
import { Badge } from "@/components/ui/badge";

export interface HabitatSceneViewProps {
  petId?: string;
  token?: string;
  serverSimTimeSec?: number;
  embedded?: boolean;
  externalState?: PetState | null;
  externalEvents?: WorldEvent[];
  externalConnectionStatus?: ConnectionStatus;
  onLayoutChanged?: () => void;
}

type CameraPresetKey = "overview" | "wheel" | "bowl" | "hideout" | "top";

const CAMERA_PRESETS: Record<CameraPresetKey, { label: string; pos: [number, number, number]; target: [number, number, number] }> = {
  overview: { label: "Studio Orbit", pos: [0.36, 0.54, 0.58], target: [0.04, 0.17, 0.0] },
  wheel: { label: "Running Wheel", pos: [-0.15, 0.36, 0.32], target: [-0.28, 0.22, -0.12] },
  bowl: { label: "Foraging Spot", pos: [0.42, 0.34, 0.36], target: [0.18, 0.17, 0.06] },
  hideout: { label: "Cozy Hideout", pos: [0.44, 0.36, 0.22], target: [0.26, 0.19, -0.10] },
  top: { label: "Top-Down Map", pos: [0.0, 0.88, 0.08], target: [0.0, 0.16, 0.0] },
};

const DEFAULT_CLEAN_LAYOUT: ShelvesLayoutState = {
  pet_id: "pet_hammy_01",
  sim_time_sec: 0,
  cheek_pouch_fill: 0,
  food_level: 1.0,
  water_level: 0.75,
  equipped_costumes: {},
  offered_foods: [],
  water_sources: [
    {
      object_id: "prop_bottle_main",
      item_id: "water_bottle",
      name: "Ball-Spout Water Bottle",
      pose_xyz_m: [0.433, -0.02, 0.183],
      water_level: 0.75,
      capacity_ml: 150,
    },
  ],
  placed_items: [],
};

function disposeObject3D(obj: THREE.Object3D): void {
  obj.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.isMesh) {
      mesh.geometry?.dispose();
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const mat of mats) {
        if (mat && typeof mat.dispose === "function") {
          mat.dispose();
        }
      }
    }
  });
}

export const HabitatSceneView: React.FC<HabitatSceneViewProps> = ({
  petId = "pet_hammy_01",
  token,
  serverSimTimeSec,
  embedded = false,
  externalState,
  externalEvents,
  externalConnectionStatus,
  onLayoutChanged,
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
  const [rightPanelTab, setRightPanelTab] = useState<"shelves" | "studio">("shelves");

  // Step 6: Opt-in Shelves state & manifest
  const [manifest, setManifest] = useState<AssetManifest | null>(null);
  const manifestRef = useRef<AssetManifest | null>(null);
  manifestRef.current = manifest;

  const [layout, setLayout] = useState<ShelvesLayoutState>(DEFAULT_CLEAN_LAYOUT);
  const layoutRef = useRef<ShelvesLayoutState>(layout);
  layoutRef.current = layout;

  const [shelfBusy, setShelfBusy] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [placementDraft, setPlacementDraft] = useState<PlacementDraft | null>(null);
  const placementDraftRef = useRef<PlacementDraft | null>(placementDraft);
  placementDraftRef.current = placementDraft;

  const syncSceneLayoutRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let mounted = true;
    fetchAssetManifest()
      .then((m) => {
        if (mounted && m && Array.isArray(m.items)) setManifest(m);
      })
      .catch(() => {
        // ignore in unit test environment
      });
    fetchShelvesState(petId, token)
      .then((st) => {
        if (mounted && st && Array.isArray(st.placed_items)) {
          setLayout(st);
          setTimeout(() => syncSceneLayoutRef.current?.(), 0);
        }
      })
      .catch(() => {
        // fallback to DEFAULT_CLEAN_LAYOUT
      });
    return () => {
      mounted = false;
    };
  }, [petId, token]);

  useEffect(() => {
    syncSceneLayoutRef.current?.();
  }, [layout, placementDraft, manifest]);

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

  // Shelf Action Handlers
  const handleOfferFood = async (itemId: string, quantity: number) => {
    setShelfBusy(true);
    try {
      const res = await offerFoodCommand(petId, itemId, quantity, undefined, token);
      setLayout(res.layout);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleRefillFood = async (amountGrams: number) => {
    setShelfBusy(true);
    try {
      const res = await refillFoodCommand(petId, amountGrams, undefined, token);
      setLayout(res.layout);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleRefillWater = async (amountMl: number) => {
    setShelfBusy(true);
    try {
      const res = await refillWaterCommand(petId, amountMl, undefined, token);
      setLayout(res.layout);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleEquipCostume = async (itemId: string) => {
    setShelfBusy(true);
    try {
      const res = await equipCostumeCommand(petId, itemId, undefined, token);
      setLayout(res.layout);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleUnequipCostume = async (slot: CostumeSlot | "all") => {
    setShelfBusy(true);
    try {
      const res = await unequipCostumeCommand(petId, slot, undefined, token);
      setLayout(res.layout);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleStartPlacement = (item: ManifestAssetItem) => {
    // Pick a clean default non-overlapping spot inside cage bounds (avoiding default wheel, logs, home, and food bowl)
    const existingCount = (layout?.placed_items ?? []).length;
    const candidateSpots: Array<[number, number, number]> = [
      [-0.22, -0.12, 0.165],
      [-0.02, -0.15, 0.165],
      [0.12, -0.15, 0.165],
      [-0.04, 0.14, 0.165],
      [-0.18, 0.14, 0.165],
      [0.12, 0.14, 0.165],
    ];
    const spot = candidateSpots[existingCount % candidateSpots.length];
    setPlacementDraft({
      item,
      pose_xyz_m: [...spot],
      rotation_y_rad: 0,
    });
  };

  const handleConfirmPlacement = async () => {
    if (!placementDraft) return;
    setShelfBusy(true);
    try {
      const res = placementDraft.editingObjectId
        ? await movePropCommand(
          petId,
          placementDraft.editingObjectId,
          placementDraft.pose_xyz_m,
          placementDraft.rotation_y_rad,
          undefined,
          token
        )
        : await placePropCommand(
          petId,
          placementDraft.item.id,
          placementDraft.pose_xyz_m,
          placementDraft.rotation_y_rad,
          undefined,
          token
        );
      setLayout(res.layout);
      setPlacementDraft(null);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleRemovePlacedItem = async (objectId: string) => {
    setShelfBusy(true);
    try {
      const res = await removePropCommand(petId, objectId, undefined, token);
      setLayout(res.layout);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
    }
  };

  const handleResetCleanCage = async () => {
    setShelfBusy(true);
    try {
      const res = await resetCleanCageCommand(petId, undefined, token);
      setLayout(res.layout);
      setPlacementDraft(null);
      setStatusMessage(res.message);
      onLayoutChanged?.();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setShelfBusy(false);
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

    const dust = createDustMotes(presetCfg.dustMoteCount);
    scene.add(dust.mesh);

    let disposed = false;
    let rafId = 0;
    let beddingDeformer: BeddingDeformer | null = null;
    let waterDroplet: ReturnType<typeof createWaterDropletEffect> | null = null;
    let hamsterAsset: Awaited<ReturnType<typeof loadHamsterAsset>> | null = null;
    let enhancedVisuals: EnhancedHamsterVisuals | null = null;
    let poseLayer: PoseApplicationLayer | null = null;
    let procLayer: ProceduralRigLayer | null = null;
    let wheelMesh: THREE.Mesh | null = null;
    let beddingMesh: THREE.Mesh | null = null;
    let waterLiquidMesh: THREE.Mesh | null = null;
    let foodBowlFillMesh: THREE.Mesh | null = null;
    let foodBowlFillBaseY = 0.1465;
    let foodBowlFillHalfH = 0.01225;
    let targetWaterScaleY = 0.75;
    let targetFoodScaleY = 1.0;
    let hamsterFootOffsetY = 0;

    // Lazy-loaded dynamic asset groups (unloaded and disposed when removed from cage)
    const gltfLoader = new GLTFLoader();
    const placedGroup = new THREE.Group();
    placedGroup.name = "opt_in_placed_items_group";
    scene.add(placedGroup);

    const loadedPlacedMeshes = new Map<string, THREE.Object3D>();
    const loadedCostumeMeshes = new Map<string, { itemId: string; obj: THREE.Object3D }>();
    let previewGhostMesh: THREE.Mesh | null = null;
    let heldFoodMesh: THREE.Object3D | null = null;
    let heldFoodCurrentId: string | null = null;

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
      // Default 3D habitat includes home (hideout), logs (tunnel), food bowl, water tank, wheel, and chew block!
      hasBowl: true,
      hasWheel: true,
      hasHideout: true,
      hasTunnel: true,
      hasChew: false,
      foodLevel: 1.0,
      waterLevel: 0.75,
      dynamicObstacles: [],
      placedProps: [],
      offeredFoodTarget: null,
      onFoodConsumed: (objectId: string) => {
        consumeFoodCommand(petId, objectId || undefined, undefined, token)
          .then((res) => {
            if (!disposed) {
              setLayout(res.layout);
              setStatusMessage(res.message);
              onLayoutChanged?.();
            }
          })
          .catch(() => { });
      },
      onWaterConsumed: () => {
        consumeWaterCommand(petId, undefined, token)
          .then((res) => {
            if (!disposed) {
              setLayout(res.layout);
              onLayoutChanged?.();
            }
          })
          .catch(() => { });
      },
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

    // Synchronize lazy-loaded 3D models with authoritative ShelvesLayoutState
    const syncSceneWithLayout = () => {
      if (disposed) return;
      const curLayout = layoutRef.current;

      // 1. Sync visible water bottle & food bowl fill levels (0..1)
      const waterLvl = THREE.MathUtils.clamp(curLayout.water_level ?? 0.75, 0.0, 1.0);
      const foodLvl = THREE.MathUtils.clamp(curLayout.food_level ?? 1.0, 0.0, 1.0);
      targetWaterScaleY = waterLvl;
      targetFoodScaleY = foodLvl;
      propAnchors.waterLevel = waterLvl;
      propAnchors.foodLevel = foodLvl;
      if (waterLiquidMesh) {
        waterLiquidMesh.visible = waterLvl > 0.01;
        waterLiquidMesh.scale.y = Math.max(0.02, waterLvl);
      }
      if (foodBowlFillMesh) {
        foodBowlFillMesh.visible = foodLvl > 0.01;
        const clampedFood = Math.max(0.04, foodLvl);
        foodBowlFillMesh.scale.y = clampedFood;
        // Anchor bottom of kibble mound at bowl interior floor so eating visibly drops the top surface
        const bottomY = foodBowlFillBaseY - foodBowlFillHalfH;
        foodBowlFillMesh.position.y = bottomY + foodBowlFillHalfH * clampedFood;
      }

      // 2. Sync extra opt-in placed props, decor, water bowls & offered food models (lazy-load on add, dispose on remove)
      const desiredIds = new Set<string>();
      const nextObstacles: Array<{ id: string; pos: THREE.Vector3; radius: number }> = [];

      for (const p of curLayout?.placed_items ?? []) {
        desiredIds.add(p.object_id);
        const wx = p.pose_xyz_m[0];
        const wz = -p.pose_xyz_m[1];
        const wy = propAnchors.sampleBeddingY ? propAnchors.sampleBeddingY(wx, wz) : propAnchors.beddingY;

        if (p.item_id !== "decor_bedding_patch") {
          nextObstacles.push({
            id: p.object_id,
            pos: new THREE.Vector3(wx, wy, wz),
            radius: p.collision_radius_m || 0.045,
          });
        }

        const existingObj = loadedPlacedMeshes.get(p.object_id);
        if (existingObj) {
          existingObj.position.set(wx, wy, wz);
          existingObj.rotation.y = p.rotation_y_rad;
        } else {
          const placeholder = new THREE.Group();
          placeholder.position.set(wx, wy, wz);
          placeholder.rotation.y = p.rotation_y_rad;
          placedGroup.add(placeholder);
          loadedPlacedMeshes.set(p.object_id, placeholder);

          gltfLoader.load(`/assets/items/${p.item_id}.glb`, (gltf) => {
            if (disposed || !loadedPlacedMeshes.has(p.object_id)) {
              disposeObject3D(gltf.scene);
              return;
            }
            gltf.scene.traverse((c) => {
              if ((c as THREE.Mesh).isMesh) {
                c.castShadow = true;
                c.receiveShadow = true;
              }
            });
            placeholder.add(gltf.scene);
          });
        }
      }

      // Sync offered foods directly inside the ceramic food bowl interior (never random floor spots)
      const bowlBottomY = foodBowlFillBaseY - foodBowlFillHalfH;
      const bowlTopFillY = bowlBottomY + foodBowlFillHalfH * 2 * Math.max(0.05, foodLvl);
      let foodIdx = 0;
      for (const f of curLayout?.offered_foods ?? []) {
        if (f.quantity <= 0) continue;
        desiredIds.add(f.object_id);
        let fx = f.pose_xyz_m[0];
        let fz = -f.pose_xyz_m[1];
        // Ensure dropped food always rests cleanly inside the ceramic food bowl rim
        const dFromBowl = Math.hypot(fx - propAnchors.bowlPos.x, fz - propAnchors.bowlPos.z);
        if (dFromBowl > 0.022) {
          const ang = foodIdx * 2.3999632297;
          const rad = foodIdx === 0 ? 0.0 : Math.min(0.015, 0.007 + (foodIdx % 3) * 0.003);
          fx = propAnchors.bowlPos.x + Math.cos(ang) * rad;
          fz = propAnchors.bowlPos.z + Math.sin(ang) * rad;
        }
        const fy = bowlTopFillY + 0.004 + (foodIdx % 2) * 0.003;
        foodIdx++;

        const existingFood = loadedPlacedMeshes.get(f.object_id);
        if (existingFood) {
          existingFood.position.set(fx, fy, fz);
        } else {
          const foodHolder = new THREE.Group();
          foodHolder.position.set(fx, fy, fz);
          placedGroup.add(foodHolder);
          loadedPlacedMeshes.set(f.object_id, foodHolder);

          gltfLoader.load(`/assets/items/${f.item_id}.glb`, (gltf) => {
            if (disposed || !loadedPlacedMeshes.has(f.object_id)) {
              disposeObject3D(gltf.scene);
              return;
            }
            gltf.scene.traverse((c) => {
              if ((c as THREE.Mesh).isMesh) {
                c.castShadow = true;
                c.receiveShadow = true;
              }
            });
            foodHolder.add(gltf.scene);
          });
        }
      }

      // Unload & dispose any removed props/foods
      for (const [objId, obj3d] of Array.from(loadedPlacedMeshes.entries())) {
        if (!desiredIds.has(objId)) {
          placedGroup.remove(obj3d);
          disposeObject3D(obj3d);
          loadedPlacedMeshes.delete(objId);
        }
      }

      propAnchors.dynamicObstacles = nextObstacles;
      // Core 3D habitat props (bowl, wheel, hideout, logs/tunnel) remain active in default cage
      propAnchors.hasWheel = true;
      propAnchors.hasHideout = true;
      propAnchors.hasTunnel = true;
      propAnchors.hasBowl = true;
      propAnchors.hasChew = false;

      const firstFood = (curLayout?.offered_foods ?? []).find((f) => f.quantity > 0 && !f.spoiled);
      if (firstFood) {
        const fx = firstFood.pose_xyz_m[0];
        const fz = -firstFood.pose_xyz_m[1];
        const fy = propAnchors.sampleBeddingY ? propAnchors.sampleBeddingY(fx, fz) : propAnchors.beddingY;
        propAnchors.offeredFoodTarget = {
          objectId: firstFood.object_id,
          itemId: firstFood.item_id,
          pos: new THREE.Vector3(fx, fy, fz),
        };
      } else {
        propAnchors.offeredFoodTarget = null;
      }

      // 3. Sync equipped costumes on HamsterRig sockets (head_slot, neck_slot, back_slot)
      if (hamsterAsset) {
        const slotBoneFallbacks: Record<CostumeSlot, string[]> = {
          head_slot: ["head_slot", "head"],
          neck_slot: ["neck_slot", "neck"],
          back_slot: ["back_slot", "spine_2"],
        };
        const activeSlots: CostumeSlot[] = ["head_slot", "neck_slot", "back_slot"];
        for (const slot of activeSlots) {
          const eq = curLayout?.equipped_costumes?.[slot];
          const curLoaded = loadedCostumeMeshes.get(slot);
          if (!eq) {
            if (curLoaded) {
              curLoaded.obj.parent?.remove(curLoaded.obj);
              disposeObject3D(curLoaded.obj);
              loadedCostumeMeshes.delete(slot);
            }
          } else if (!curLoaded || curLoaded.itemId !== eq.item_id) {
            if (curLoaded) {
              curLoaded.obj.parent?.remove(curLoaded.obj);
              disposeObject3D(curLoaded.obj);
              loadedCostumeMeshes.delete(slot);
            }
            const targetBone =
              hamsterAsset.bones.get(slotBoneFallbacks[slot][0]) ||
              hamsterAsset.bones.get(slotBoneFallbacks[slot][1]);
            if (targetBone) {
              const holder = new THREE.Group();
              holder.name = `equipped_${slot}_${eq.item_id}`;
              applyCostumeSocketTransform(eq.item_id, holder);
              targetBone.add(holder);
              loadedCostumeMeshes.set(slot, { itemId: eq.item_id, obj: holder });

              gltfLoader.load(`/assets/items/${eq.item_id}.glb`, (gltf) => {
                const stillActive = loadedCostumeMeshes.get(slot);
                if (disposed || !stillActive || stillActive.itemId !== eq.item_id) {
                  disposeObject3D(gltf.scene);
                  return;
                }
                applyCostumeSocketTransform(eq.item_id, holder, gltf.scene);
                holder.add(gltf.scene);
              });
            }
          }
        }
      }

      // 4. Placement preview ghost mesh
      const draft = placementDraftRef.current;
      if (draft) {
        const r = draft.item.collision_radius_m || 0.045;
        if (!previewGhostMesh) {
          const geo = new THREE.CylinderGeometry(r, r, 0.06, 24);
          const mat = new THREE.MeshBasicMaterial({
            color: "#34d399",
            transparent: true,
            opacity: 0.38,
            wireframe: false,
          });
          previewGhostMesh = new THREE.Mesh(geo, mat);
          scene.add(previewGhostMesh);
        }
        const gx = draft.pose_xyz_m[0];
        const gz = -draft.pose_xyz_m[1];
        const gy = (propAnchors.sampleBeddingY ? propAnchors.sampleBeddingY(gx, gz) : propAnchors.beddingY) + 0.03;
        previewGhostMesh.position.set(gx, gy, gz);
        previewGhostMesh.rotation.y = draft.rotation_y_rad;
        previewGhostMesh.visible = true;
      } else if (previewGhostMesh) {
        previewGhostMesh.visible = false;
      }
    };

    syncSceneLayoutRef.current = syncSceneWithLayout;

    Promise.all([
      gltfLoader.loadAsync("/assets/cage.glb"),
      loadHamsterAsset("/assets/hamster.glb", { strict: true }),
    ])
      .then(([cageGltf, hAsset]) => {
        if (disposed) return;

        const cageRoot = cageGltf.scene;
        cageRoot.updateMatrixWorld(true);
        let beddingY = 0.165;
        let bowlPos = new THREE.Vector3(0.28, 0.165, 0.11);
        let spoutPos = new THREE.Vector3(0.433, 0.183, 0.02);

        // Keep the core 3D habitat visible by default:
        // enclosure (`cage_*`), bedding (`bedding_*`), home (`prop_hideout`), logs (`prop_tunnel_*`),
        // food bowl (`prop_bowl`), water tank (`prop_bottle_*`), running wheel (`prop_wheel_*`), and chew block (`prop_chew_block`).
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
            if (m.name === "prop_food_bowl_fill") {
              foodBowlFillMesh = m;
              foodBowlFillBaseY = m.position.y;
              m.geometry.computeBoundingBox();
              const gBox = m.geometry.boundingBox;
              if (gBox) {
                foodBowlFillHalfH = Math.max(0.006, (gBox.max.y - gBox.min.y) * 0.5);
              }
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

              // Add realistic wooden inner grip rungs & spokes to wheelMesh so drum rotation is clearly visible
              m.geometry.computeBoundingBox();
              const gBox = m.geometry.boundingBox;
              if (gBox) {
                const rad = Math.max(0.06, (gBox.max.x - gBox.min.x) * 0.48);
                const depth = Math.max(0.04, (gBox.max.y - gBox.min.y) * 0.88);
                const rungMat = new THREE.MeshStandardMaterial({
                  color: "#6b4827",
                  roughness: 0.78,
                  metalness: 0.02,
                });
                const rungGeo = new THREE.BoxGeometry(0.005, depth, 0.005);
                for (let rIdx = 0; rIdx < 12; rIdx++) {
                  const ang = (rIdx / 12) * Math.PI * 2;
                  const rung = new THREE.Mesh(rungGeo, rungMat);
                  rung.position.set(Math.cos(ang) * (rad - 0.006), 0, Math.sin(ang) * (rad - 0.006));
                  rung.rotation.y = -ang;
                  rung.castShadow = false;
                  rung.receiveShadow = true;
                  m.add(rung);
                }
                const spokeGeo = new THREE.BoxGeometry(rad * 1.92, 0.004, 0.009);
                for (let sIdx = 0; sIdx < 3; sIdx++) {
                  const spoke = new THREE.Mesh(spokeGeo, rungMat);
                  spoke.position.set(0, -depth * 0.45, 0);
                  spoke.rotation.y = (sIdx / 3) * Math.PI;
                  m.add(spoke);
                }
              }
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
            if (m.name.startsWith("prop_chew_")) {
              // Hide the small dark chew block/stick cubes so only the 5 core habitat props (home, logs, food bowl, water tank, wheel) are shown by default
              m.visible = false;
              propAnchors.hasChew = false;
              return;
            }
            if (m.name === "prop_bottle_body") {
              // Replace opaque-looking transmission shader with crystal-clear acrylic so inner water_liquid is unmistakably visible!
              m.material = new THREE.MeshPhysicalMaterial({
                color: "#e6f5ff",
                transparent: true,
                opacity: 0.24,
                roughness: 0.08,
                metalness: 0.02,
                clearcoat: 1.0,
                clearcoatRoughness: 0.06,
                depthWrite: false,
                side: THREE.DoubleSide,
              });
              m.castShadow = false;
              m.receiveShadow = false;
              m.renderOrder = 3;

              // Attach scalable inner water liquid cylinder so water level (0..1) visibly drops on drink & rises on refill
              const liqGeo = new THREE.CylinderGeometry(0.0225, 0.0225, 0.122, 24);
              liqGeo.translate(0, 0.122 * 0.5, 0); // Pivot at bottom of liquid column
              const liqMat = new THREE.MeshPhysicalMaterial({
                color: "#22b8f5",
                emissive: new THREE.Color("#0c4a6e"),
                emissiveIntensity: 0.22,
                transparent: true,
                opacity: 0.86,
                roughness: 0.12,
                clearcoat: 0.85,
                depthWrite: true,
              });
              waterLiquidMesh = new THREE.Mesh(liqGeo, liqMat);
              waterLiquidMesh.name = "water_liquid";
              waterLiquidMesh.renderOrder = 2;
              const bBox = new THREE.Box3().setFromObject(m);
              const bCenter = new THREE.Vector3();
              bBox.getCenter(bCenter);
              waterLiquidMesh.position.set(bCenter.x, bBox.min.y + 0.006, bCenter.z);
              scene.add(waterLiquidMesh);
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

        hamsterAsset = hAsset;
        const startY = propAnchors.sampleBeddingY ? propAnchors.sampleBeddingY(-0.08, 0.12) : beddingY;
        hamsterAsset.root.position.set(-0.08, startY, 0.12);
        scene.add(hamsterAsset.root);

        poseLayer = new PoseApplicationLayer(hamsterAsset);
        procLayer = new ProceduralRigLayer(hamsterAsset);

        syncSceneWithLayout();
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

      // Smoothly animate visible water bottle & food bowl fill levels
      if (waterLiquidMesh) {
        const nextY = THREE.MathUtils.lerp(waterLiquidMesh.scale.y, Math.max(0.02, targetWaterScaleY), Math.min(1, dt * 6));
        waterLiquidMesh.scale.y = nextY;
        waterLiquidMesh.visible = targetWaterScaleY > 0.01;
      }
      if (foodBowlFillMesh) {
        const nextF = THREE.MathUtils.lerp(foodBowlFillMesh.scale.y, Math.max(0.04, targetFoodScaleY), Math.min(1, dt * 6));
        foodBowlFillMesh.scale.y = nextF;
        foodBowlFillMesh.position.y = (foodBowlFillBaseY - foodBowlFillHalfH) + foodBowlFillHalfH * nextF;
        foodBowlFillMesh.visible = targetFoodScaleY > 0.01;
      }

      let activeLod: LodLevel = "LOD0";
      if (hamsterAsset && poseLayer && procLayer) {
        const effectivePetState: PetState | null = petStateRef.current
          ? {
            ...petStateRef.current,
            cheek_pouch_fill: Math.max(
              petStateRef.current.cheek_pouch_fill ?? 0,
              layoutRef.current.cheek_pouch_fill ?? 0
            ),
          }
          : null;

        const step = behaviorController.update(
          dt,
          effectivePetState,
          latestEventRef.current,
          propAnchors
        );
        currentActivity = step.activityLabel;

        poseLayer.applyPhysicsPose(step.pose);
        procLayer.update(dt, step.proceduralConfig);

        // Attach held food mesh to `food_hold_socket` (or `head`) while eating with both front paws!
        if (behaviorController.isHoldingFood && behaviorController.heldFoodItemId) {
          const targetFoodId = behaviorController.heldFoodItemId;
          if (heldFoodCurrentId !== targetFoodId) {
            if (heldFoodMesh) {
              heldFoodMesh.parent?.remove(heldFoodMesh);
              disposeObject3D(heldFoodMesh);
              heldFoodMesh = null;
            }
            heldFoodCurrentId = targetFoodId;
            const holdSocket =
              hamsterAsset.bones.get("food_hold_socket") ||
              hamsterAsset.bones.get("head");
            if (holdSocket) {
              const holder = new THREE.Group();
              holdSocket.add(holder);
              heldFoodMesh = holder;
              gltfLoader.load(`/assets/items/${targetFoodId}.glb`, (gltf) => {
                if (disposed || heldFoodMesh !== holder) {
                  disposeObject3D(gltf.scene);
                  return;
                }
                holder.add(gltf.scene);
              });
            }
          }
          if (heldFoodMesh) heldFoodMesh.visible = true;
        } else if (heldFoodMesh) {
          heldFoodMesh.visible = false;
        }

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

        // Compute true active scene mesh & triangle counts (since post-processing EffectComposer overwrites renderer.info.render with the 1-triangle fullscreen quad)
        let activeDrawCalls = 0;
        let activeTriangles = 0;
        scene.traverseVisible((obj) => {
          const mesh = obj as THREE.Mesh;
          if (mesh.isMesh && mesh.geometry) {
            activeDrawCalls += 1;
            const idx = mesh.geometry.index;
            const pos = mesh.geometry.attributes.position;
            const instanceCount = (mesh as THREE.InstancedMesh).isInstancedMesh
              ? (mesh as THREE.InstancedMesh).count
              : 1;
            if (idx) {
              activeTriangles += (idx.count / 3) * instanceCount;
            } else if (pos) {
              activeTriangles += (pos.count / 3) * instanceCount;
            }
          }
        });

        setHud((prev) => ({
          ...prev,
          fps,
          frameMs,
          drawCalls: activeDrawCalls,
          triangles: Math.round(activeTriangles),
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
      syncSceneLayoutRef.current = null;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      dust.dispose();
      waterDroplet?.dispose();
      enhancedVisuals?.dispose();
      for (const obj3d of loadedPlacedMeshes.values()) {
        disposeObject3D(obj3d);
      }
      loadedPlacedMeshes.clear();
      for (const entry of loadedCostumeMeshes.values()) {
        disposeObject3D(entry.obj);
      }
      loadedCostumeMeshes.clear();
      if (heldFoodMesh) disposeObject3D(heldFoodMesh);
      composer.dispose();
      renderer.dispose();
    };
  }, [quality]);

  return (
    <div data-testid="habitat-scene-view">
      <div
        className={
          embedded
            ? "relative w-full grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4 items-stretch xl:h-[calc(100vh-225px)] xl:min-h-[540px] xl:max-h-[700px]"
            : "phase3-layout items-stretch xl:h-[calc(100vh-105px)] xl:min-h-[600px]"
        }
      >
        {/* 3D Interactive Glass Viewport */}
        <div className="phase3-viewport-wrap group relative h-[480px] sm:h-[520px] xl:h-full">
          <div ref={mountRef} className="phase3-canvas-mount w-full h-full" />

          {/* Top-Left Telemetry Glass HUD */}
          <div className="perf-hud" data-testid="habitat-perf-hud">
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-block h-2 w-2 rounded-full bg-[#FF6B5B] animate-pulse" />
              <strong>Scene:</strong>{" "}
              <span>
                {hud.loading
                  ? "Loading cage.glb & hamster.glb..."
                  : hud.error
                    ? "ERROR"
                    : `Clean Opt-In Habitat (${(layout?.placed_items ?? []).length} props)`}
              </span>
            </div>
            <div>
              <strong>Preset:</strong> {quality.toUpperCase()} | <strong>LOD:</strong> {hud.activeLod}
            </div>
            <div>
              <strong>FPS:</strong> {hud.fps.toFixed(1)} ({hud.frameMs.toFixed(2)} ms) | <strong>Calls:</strong>{" "}
              {hud.drawCalls} | <strong>Tris:</strong> {hud.triangles.toLocaleString()}
            </div>
            <div>
              <strong>Food:</strong> {Math.round((layout.food_level ?? 1.0) * 100)}% | <strong>Water:</strong>{" "}
              {Math.round(layout.water_level * 100)}% | <strong>Cheeks:</strong>{" "}
              {Math.round(layout.cheek_pouch_fill * 100)}% | <strong>Circadian:</strong> {hud.hourOfDay.toFixed(1)}h
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
              {hud.phaseLabel === "night" ? (
                <Moon className="w-3.5 h-3.5 text-[#FF6B5B]" />
              ) : (
                <Sun className="w-3.5 h-3.5 text-[#FF6B5B]" />
              )}
              {hud.hourOfDay.toFixed(1)}h ({hud.phaseLabel.toUpperCase()})
            </Badge>
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
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${activeCamPreset === key
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
                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${isSelected
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

        {/* Right Lateral Studio Panel: Tabbed Asset Shelves + Cage & Lighting */}
        <div className="flex flex-col gap-2.5 min-w-0 xl:h-full xl:overflow-hidden">
          {/* Segmented Lateral Tab Switcher */}
          <div
            className="glass-card rounded-2xl p-1 border border-[#F4EDE0]/15 grid grid-cols-2 gap-1 shrink-0"
            role="tablist"
            aria-label="Habitat Side Panel"
          >
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "shelves"}
              onClick={() => setRightPanelTab("shelves")}
              data-testid="tab-panel-shelves"
              className={`flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
                rightPanelTab === "shelves"
                  ? "bg-[#FF6B5B] text-[#14213D] shadow-coral-glow"
                  : "text-[#F4EDE0]/75 hover:text-[#F4EDE0] hover:bg-[#F4EDE0]/10"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Asset Shelves
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={rightPanelTab === "studio"}
              onClick={() => setRightPanelTab("studio")}
              data-testid="tab-panel-studio"
              className={`flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
                rightPanelTab === "studio"
                  ? "bg-[#FF6B5B] text-[#14213D] shadow-coral-glow"
                  : "text-[#F4EDE0]/75 hover:text-[#F4EDE0] hover:bg-[#F4EDE0]/10"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              Cage &amp; Lighting
            </button>
          </div>

          {/* Internally Scrollable Lateral Panel Body */}
          <div className="flex-1 min-h-0 xl:overflow-y-auto pr-0.5">
            {rightPanelTab === "shelves" ? (
              <AssetShelfDrawer
                manifest={manifest}
                layout={layout}
                busy={shelfBusy}
                statusMessage={statusMessage}
                placementDraft={placementDraft}
                onStartPlacement={handleStartPlacement}
                onUpdatePlacementDraft={setPlacementDraft}
                onConfirmPlacement={handleConfirmPlacement}
                onOfferFood={handleOfferFood}
                onRefillFood={handleRefillFood}
                onRefillWater={handleRefillWater}
                onEquipCostume={handleEquipCostume}
                onUnequipCostume={handleUnequipCostume}
                onRemovePlacedItem={handleRemovePlacedItem}
                onResetCleanCage={handleResetCleanCage}
              />
            ) : (
              <aside className="phase3-panel flex">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="default" className="mb-2">
                      <Layers className="w-3 h-3" /> P3.3 Live 3D Habitat
                    </Badge>
                    <span className="text-[11px] font-mono text-[#F4EDE0]/60">{hud.activeLod}</span>
                  </div>
                  <h2>Realistic Cage &amp; Lighting</h2>
                  <p className="panel-subtitle mt-1">
                    PBR glass terrarium, HDRI IBL, soft PCF shadows, SSAO/DoF, 4-paw deformable bedding, and lazy-loaded opt-in shelf props.
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
                    <li>Lazy-Loaded Models in Cage: {layout.placed_items.length + layout.offered_foods.length + Object.keys(layout.equipped_costumes).length}</li>
                    <li>Bedding Deformation: Active (4-paw heightfield)</li>
                    <li>Water Level Mesh: {Math.round(layout.water_level * 100)}%</li>
                  </ul>
                </div>
              </aside>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
