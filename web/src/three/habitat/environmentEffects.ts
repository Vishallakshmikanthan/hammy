import * as THREE from "three";

export interface DayNightState {
  hourOfDay: number;
  phaseLabel: "day" | "dawn" | "dusk" | "night";
  keyIntensity: number;
  keyColor: THREE.Color;
  keyPosition: THREE.Vector3;
  nightLampIntensity: number;
  envIntensity: number;
  bgColor: THREE.Color;
}

export function computeDayNightLighting(hourOfDay: number): DayNightState {
  const h = ((hourOfDay % 24) + 24) % 24;
  // Sun elevation peaks at 13:00
  const sunAngle = ((h - 6) / 12) * Math.PI;
  const daylight = THREE.MathUtils.clamp(Math.sin(sunAngle), 0, 1);

  let phaseLabel: DayNightState["phaseLabel"] = "night";
  if (h >= 6 && h < 8.5) phaseLabel = "dawn";
  else if (h >= 8.5 && h < 17.5) phaseLabel = "day";
  else if (h >= 17.5 && h < 20.5) phaseLabel = "dusk";

  const dayColor = new THREE.Color("#fff5e6");
  const goldenColor = new THREE.Color("#ffb56b");
  const nightColor = new THREE.Color("#6a88b8");

  const keyColor =
    daylight > 0.35
      ? goldenColor.clone().lerp(dayColor, (daylight - 0.35) / 0.65)
      : nightColor.clone().lerp(goldenColor, daylight / 0.35);

  const keyIntensity = 0.25 + daylight * 2.15;
  const nightLampIntensity = THREE.MathUtils.clamp(1.0 - daylight * 1.4, 0.05, 1.0) * 1.35;
  const envIntensity = 0.22 + daylight * 0.72;

  const bgDay = new THREE.Color("#182747");
  const bgNight = new THREE.Color("#0B1325");
  const bgColor = bgNight.clone().lerp(bgDay, daylight);

  const elev = 0.25 + daylight * 0.75;
  const azim = (h / 24) * Math.PI * 2;
  const keyPosition = new THREE.Vector3(Math.cos(azim) * 0.65, elev, Math.sin(azim) * 0.55);

  return {
    hourOfDay: h,
    phaseLabel,
    keyIntensity,
    keyColor,
    keyPosition,
    nightLampIntensity,
    envIntensity,
    bgColor,
  };
}

export function createDustMotes(count: number, bounds = { x: 0.42, y: 0.28, z: 0.22 }) {
  const geo = new THREE.SphereGeometry(0.0011, 5, 5);
  const mat = new THREE.MeshBasicMaterial({
    color: "#fff5dc",
    transparent: true,
    opacity: 0.42,
    depthWrite: false,
  });
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.name = "dust_motes";

  const seeds = new Float32Array(count * 4);
  const dummy = new THREE.Object3D();
  for (let i = 0; i < count; i++) {
    seeds[i * 4 + 0] = (Math.random() - 0.5) * 2 * bounds.x;
    seeds[i * 4 + 1] = 0.04 + Math.random() * bounds.y;
    seeds[i * 4 + 2] = (Math.random() - 0.5) * 2 * bounds.z;
    seeds[i * 4 + 3] = 0.5 + Math.random() * 1.2;
    dummy.position.set(seeds[i * 4], seeds[i * 4 + 1], seeds[i * 4 + 2]);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }

  return {
    mesh,
    update: (timeSec: number) => {
      for (let i = 0; i < count; i++) {
        const bx = seeds[i * 4 + 0];
        const by = seeds[i * 4 + 1];
        const bz = seeds[i * 4 + 2];
        const sp = seeds[i * 4 + 3];
        dummy.position.set(
          bx + Math.sin(timeSec * 0.35 * sp + i) * 0.015,
          by + Math.cos(timeSec * 0.25 * sp + i * 0.7) * 0.012,
          bz + Math.sin(timeSec * 0.3 * sp + i * 1.3) * 0.015
        );
        const s = 0.6 + 0.5 * Math.sin(timeSec * 1.2 + i);
        dummy.scale.setScalar(s);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
      }
      mesh.instanceMatrix.needsUpdate = true;
    },
    dispose: () => {
      geo.dispose();
      mat.dispose();
    },
  };
}

export function createWaterDropletEffect(spoutWorldPos: THREE.Vector3) {
  const geo = new THREE.SphereGeometry(0.0022, 12, 12);
  const mat = new THREE.MeshPhysicalMaterial({
    color: "#e6f6ff",
    transmission: 0.9,
    roughness: 0.05,
    ior: 1.333,
    thickness: 0.004,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.name = "water_droplet_spout";
  mesh.position.copy(spoutWorldPos).add(new THREE.Vector3(0, -0.003, 0));

  return {
    mesh,
    update: (timeSec: number) => {
      const cycle = (timeSec * 0.45) % 1;
      const scale = 0.6 + 0.55 * cycle;
      mesh.scale.set(scale, scale * (1 + cycle * 0.25), scale);
      mesh.position.y = spoutWorldPos.y - 0.0025 - cycle * 0.0015;
    },
    dispose: () => {
      geo.dispose();
      mat.dispose();
    },
  };
}

export function createInstancedFoodScatter(bowlWorldPos: THREE.Vector3, count = 48) {
  const geo = new THREE.CapsuleGeometry(0.0022, 0.0045, 4, 8);
  const mat = new THREE.MeshStandardMaterial({
    color: "#c49a5c",
    roughness: 0.68,
    metalness: 0.0,
  });
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.name = "instanced_food_items";
  mesh.castShadow = true;

  const dummy = new THREE.Object3D();
  const color = new THREE.Color();
  for (let i = 0; i < count; i++) {
    const r = Math.sqrt(Math.random()) * 0.026;
    const theta = Math.random() * Math.PI * 2;
    dummy.position.set(
      bowlWorldPos.x + Math.cos(theta) * r,
      bowlWorldPos.y + 0.004 + Math.random() * 0.004,
      bowlWorldPos.z + Math.sin(theta) * r
    );
    dummy.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
    dummy.scale.setScalar(0.8 + Math.random() * 0.45);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);

    // Alternate sunflower seed dark stripe vs pellet tan
    color.set(i % 3 === 0 ? "#3f3830" : i % 3 === 1 ? "#b68e52" : "#7c8c58");
    mesh.setColorAt(i, color);
  }
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;

  return {
    mesh,
    dispose: () => {
      geo.dispose();
      mat.dispose();
    },
  };
}

