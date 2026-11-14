import * as THREE from "three";
import type { FurParams } from "./types";

const SHELL_VERTEX_SHADER = /* glsl */ `
  uniform float uShellIndex;
  uniform float uShellCount;
  uniform float uHairLength;
  uniform float uGravityDroop;
  uniform float uWindStrength;
  uniform float uTime;

  varying vec2 vUv;
  varying vec3 vWorldNormal;
  varying vec3 vWorldPos;
  varying float vShellFrac;

  void main() {
    vUv = uv;
    float h = uShellCount > 1.0 ? uShellIndex / (uShellCount - 1.0) : 0.0;
    vShellFrac = h;

    vec3 pos = position;
    vec3 nrm = normalize(normal);

    // Extrude along normal
    pos += nrm * (h * uHairLength);

    // Gravity droop increases quadratically toward hair tips
    vec3 worldNrm = normalize(mat3(modelMatrix) * nrm);
    float bend = h * h;
    pos.y -= uGravityDroop * uHairLength * 0.65 * bend;

    // Optional wind (0 by default)
    if (uWindStrength > 0.001) {
      float sway = sin(uTime * 3.5 + pos.x * 25.0 + pos.z * 20.0) * 0.5 + 0.5;
      pos.x += uWindStrength * uHairLength * 0.45 * bend * sway;
      pos.z += uWindStrength * uHairLength * 0.25 * bend * cos(uTime * 2.7 + pos.y * 18.0);
    }

    vec4 worldPos = modelMatrix * vec4(pos, 1.0);
    vWorldPos = worldPos.xyz;
    vWorldNormal = worldNrm;
    gl_Position = projectionMatrix * viewMatrix * worldPos;
  }
`;

const SHELL_FRAGMENT_SHADER = /* glsl */ `
  uniform float uDensity;
  uniform float uClumping;
  uniform float uRimLightStrength;
  uniform vec3 uLightDir;
  uniform vec3 uRootColor;
  uniform vec3 uTipColor;
  uniform vec3 uRimColor;

  varying vec2 vUv;
  varying vec3 vWorldNormal;
  varying vec3 vWorldPos;
  varying float vShellFrac;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  vec2 clumpOffset(vec2 uv, float scale) {
    vec2 g = floor(uv * scale);
    vec2 f = fract(uv * scale);
    float rx = hash21(g) - 0.5;
    float ry = hash21(g + 17.3) - 0.5;
    vec2 center = vec2(0.5 + rx * 0.4, 0.5 + ry * 0.4);
    return mix(f, center, uClumping * vShellFrac * 0.72);
  }

  void main() {
    // Base skin shell (index 0) is always opaque
    if (vShellFrac > 0.001) {
      vec2 clumped = clumpOffset(vUv, uDensity * 0.22);
      vec2 cellUv = vUv * uDensity + (clumped - 0.5) * uClumping * 2.2;
      vec2 cellId = floor(cellUv);
      vec2 local = fract(cellUv) - 0.5;

      float strandRand = hash21(cellId);
      float strandHeight = 0.35 + 0.65 * strandRand;
      if (vShellFrac > strandHeight) {
        discard;
      }

      float dist = length(local);
      float thickness = mix(0.46, 0.10, vShellFrac / max(strandHeight, 0.01));
      if (dist > thickness) {
        discard;
      }
    }

    vec3 N = normalize(vWorldNormal);
    vec3 V = normalize(cameraPosition - vWorldPos);
    vec3 L = normalize(uLightDir);

    // Soft wrapped diffuse + self-shadowing from root to tip
    float ndl = dot(N, L) * 0.5 + 0.5;
    float ao = mix(0.32, 1.0, pow(vShellFrac, 0.75));
    vec3 baseCol = mix(uRootColor, uTipColor, smoothstep(0.15, 0.95, vShellFrac));

    // Kajiya-Kay style anisotropic rim/backlight translucency
    float fresnel = pow(1.0 - max(dot(N, V), 0.0), 2.6);
    float backScatter = pow(max(dot(-V, L), 0.0), 2.0) * 0.6 + 0.4;
    vec3 rim = uRimColor * fresnel * uRimLightStrength * backScatter * mix(0.25, 1.0, vShellFrac);

    vec3 color = baseCol * (0.28 + 0.72 * ndl) * ao + rim;
    gl_FragColor = vec4(color, 1.0);
  }
`;

const FIN_VERTEX_SHADER = /* glsl */ `
  uniform float uHairLength;
  uniform float uGravityDroop;
  uniform float uWindStrength;
  uniform float uTime;

  varying vec2 vUv;
  varying vec3 vWorldNormal;
  varying vec3 vWorldPos;

  void main() {
    vUv = uv;
    vec3 pos = position;
    float h = uv.y;
    float bend = h * h;

    pos.y -= uGravityDroop * uHairLength * 0.55 * bend;
    if (uWindStrength > 0.001) {
      pos.x += uWindStrength * uHairLength * 0.4 * bend * sin(uTime * 3.5 + pos.z * 20.0);
    }

    vec4 worldPos = modelMatrix * vec4(pos, 1.0);
    vWorldPos = worldPos.xyz;
    vWorldNormal = normalize(mat3(modelMatrix) * normal);
    gl_Position = projectionMatrix * viewMatrix * worldPos;
  }
`;

const FIN_FRAGMENT_SHADER = /* glsl */ `
  uniform float uDensity;
  uniform float uRimLightStrength;
  uniform vec3 uLightDir;
  uniform vec3 uRootColor;
  uniform vec3 uTipColor;
  uniform vec3 uRimColor;

  varying vec2 vUv;
  varying vec3 vWorldNormal;
  varying vec3 vWorldPos;

  float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
  }

  void main() {
    float xGrid = vUv.x * uDensity * 0.6;
    float id = floor(xGrid);
    float localX = abs(fract(xGrid) - 0.5);
    float hRand = 0.4 + 0.6 * hash11(id);

    if (vUv.y > hRand) discard;
    float taper = mix(0.45, 0.04, vUv.y / hRand);
    if (localX > taper) discard;

    vec3 N = normalize(vWorldNormal);
    vec3 V = normalize(cameraPosition - vWorldPos);
    vec3 L = normalize(uLightDir);
    float ndl = abs(dot(N, L)) * 0.6 + 0.4;
    float fresnel = pow(1.0 - abs(dot(N, V)), 1.8);

    vec3 col = mix(uRootColor, uTipColor, vUv.y);
    vec3 rim = uRimColor * fresnel * uRimLightStrength * vUv.y;
    float alpha = (1.0 - smoothstep(hRand * 0.65, hRand, vUv.y)) * 0.92;
    gl_FragColor = vec4(col * ndl + rim, alpha);
  }
`;

export function createShellFurGroup(
  baseGeometry: THREE.BufferGeometry,
  params: FurParams
): {
  group: THREE.Group;
  updateUniforms: (next: FurParams, timeSec: number) => void;
  dispose: () => void;
} {
  const group = new THREE.Group();
  group.name = "fur_shell_group";

  const materials: THREE.ShaderMaterial[] = [];
  const meshes: THREE.Mesh[] = [];
  const lightDir = new THREE.Vector3(0.6, 0.85, 0.5).normalize();
  const rootColor = new THREE.Color("#6b4423");
  const tipColor = new THREE.Color("#d9a15b");
  const rimColor = new THREE.Color("#ffe7c2");

  const buildShells = (count: number) => {
    for (const m of meshes) group.remove(m);
    for (const mat of materials) mat.dispose();
    meshes.length = 0;
    materials.length = 0;

    for (let i = 0; i < count; i++) {
      const mat = new THREE.ShaderMaterial({
        vertexShader: SHELL_VERTEX_SHADER,
        fragmentShader: SHELL_FRAGMENT_SHADER,
        uniforms: {
          uShellIndex: { value: i },
          uShellCount: { value: count },
          uHairLength: { value: params.hairLength },
          uDensity: { value: params.density },
          uClumping: { value: params.clumping },
          uGravityDroop: { value: params.gravityDroop },
          uWindStrength: { value: params.windStrength },
          uRimLightStrength: { value: params.rimLightStrength },
          uTime: { value: 0 },
          uLightDir: { value: lightDir },
          uRootColor: { value: rootColor },
          uTipColor: { value: tipColor },
          uRimColor: { value: rimColor },
        },
        side: i === 0 ? THREE.FrontSide : THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(baseGeometry, mat);
      mesh.castShadow = i === 0;
      mesh.receiveShadow = i === 0;
      materials.push(mat);
      meshes.push(mesh);
      group.add(mesh);
    }
  };

  buildShells(params.shellCount);

  return {
    group,
    updateUniforms: (next: FurParams, timeSec: number) => {
      if (next.shellCount !== materials.length) {
        buildShells(next.shellCount);
      }
      for (const mat of materials) {
        mat.uniforms.uHairLength.value = next.hairLength;
        mat.uniforms.uDensity.value = next.density;
        mat.uniforms.uClumping.value = next.clumping;
        mat.uniforms.uGravityDroop.value = next.gravityDroop;
        mat.uniforms.uWindStrength.value = next.windStrength;
        mat.uniforms.uRimLightStrength.value = next.rimLightStrength;
        mat.uniforms.uTime.value = timeSec;
      }
    },
    dispose: () => {
      for (const mat of materials) mat.dispose();
    },
  };
}

export function createSilhouetteFinsMesh(
  baseGeometry: THREE.BufferGeometry,
  params: FurParams
): {
  mesh: THREE.Mesh;
  updateUniforms: (next: FurParams, timeSec: number) => void;
  dispose: () => void;
} {
  // Build silhouette fin quads extruded along triangle edges of the base geometry
  const posAttr = baseGeometry.getAttribute("position");
  const normAttr = baseGeometry.getAttribute("normal");
  const idx = baseGeometry.getIndex();

  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];

  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const na = new THREE.Vector3();
  const nb = new THREE.Vector3();
  const edge = new THREE.Vector3();
  const finNormal = new THREE.Vector3();
  const seenEdges = new Set<string>();

  const triCount = idx ? idx.count / 3 : posAttr.count / 3;
  const maxFins = Math.min(triCount * 3, 2400);
  let finCount = 0;

  const addEdgeFin = (i0: number, i1: number) => {
    if (finCount >= maxFins) return;
    const key = i0 < i1 ? `${i0}_${i1}` : `${i1}_${i0}`;
    if (seenEdges.has(key)) return;
    seenEdges.add(key);

    a.fromBufferAttribute(posAttr, i0);
    b.fromBufferAttribute(posAttr, i1);
    na.fromBufferAttribute(normAttr, i0).normalize();
    nb.fromBufferAttribute(normAttr, i1).normalize();

    edge.subVectors(b, a);
    if (edge.lengthSq() < 1e-8) return;
    finNormal.crossVectors(edge, na).normalize();

    const aTip = a.clone().addScaledVector(na, params.hairLength);
    const bTip = b.clone().addScaledVector(nb, params.hairLength);

    const baseVert = positions.length / 3;
    positions.push(a.x, a.y, a.z, b.x, b.y, b.z, bTip.x, bTip.y, bTip.z, aTip.x, aTip.y, aTip.z);
    for (let k = 0; k < 4; k++) {
      normals.push(finNormal.x, finNormal.y, finNormal.z);
    }
    uvs.push(0, 0, 1, 0, 1, 1, 0, 1);
    indices.push(baseVert, baseVert + 1, baseVert + 2, baseVert, baseVert + 2, baseVert + 3);
    finCount++;
  };

  for (let t = 0; t < triCount; t++) {
    const i0 = idx ? idx.getX(t * 3) : t * 3;
    const i1 = idx ? idx.getX(t * 3 + 1) : t * 3 + 1;
    const i2 = idx ? idx.getX(t * 3 + 2) : t * 3 + 2;
    if (t % 2 === 0) {
      addEdgeFin(i0, i1);
      addEdgeFin(i1, i2);
    }
  }

  const finGeo = new THREE.BufferGeometry();
  finGeo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  finGeo.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  finGeo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  finGeo.setIndex(indices);

  const finMat = new THREE.ShaderMaterial({
    vertexShader: FIN_VERTEX_SHADER,
    fragmentShader: FIN_FRAGMENT_SHADER,
    uniforms: {
      uHairLength: { value: params.hairLength },
      uDensity: { value: params.density },
      uGravityDroop: { value: params.gravityDroop },
      uWindStrength: { value: params.windStrength },
      uRimLightStrength: { value: params.rimLightStrength },
      uTime: { value: 0 },
      uLightDir: { value: new THREE.Vector3(0.6, 0.85, 0.5).normalize() },
      uRootColor: { value: new THREE.Color("#6b4423") },
      uTipColor: { value: new THREE.Color("#d9a15b") },
      uRimColor: { value: new THREE.Color("#ffe7c2") },
    },
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  });

  const mesh = new THREE.Mesh(finGeo, finMat);
  mesh.name = "fur_silhouette_fins";
  mesh.renderOrder = 2;

  return {
    mesh,
    updateUniforms: (next: FurParams, timeSec: number) => {
      finMat.uniforms.uHairLength.value = next.hairLength;
      finMat.uniforms.uDensity.value = next.density;
      finMat.uniforms.uGravityDroop.value = next.gravityDroop;
      finMat.uniforms.uWindStrength.value = next.windStrength;
      finMat.uniforms.uRimLightStrength.value = next.rimLightStrength;
      finMat.uniforms.uTime.value = timeSec;
    },
    dispose: () => {
      finGeo.dispose();
      finMat.dispose();
    },
  };
}

export async function detectWebGPUSupport(): Promise<{
  supported: boolean;
  adapterName?: string;
  reason?: string;
}> {
  if (typeof navigator === "undefined" || !("gpu" in navigator)) {
    return { supported: false, reason: "navigator.gpu is unavailable in this browser" };
  }
  try {
    const gpu = (navigator as unknown as { gpu: { requestAdapter: () => Promise<unknown> } }).gpu;
    const adapter = (await gpu.requestAdapter()) as { info?: { device?: string; description?: string } } | null;
    if (!adapter) {
      return { supported: false, reason: "WebGPU adapter request returned null" };
    }
    return {
      supported: true,
      adapterName: adapter.info?.description || adapter.info?.device || "WebGPU Adapter",
    };
  } catch (err) {
    return { supported: false, reason: err instanceof Error ? err.message : String(err) };
  }
}

export function createStrandInstancedMesh(
  baseGeometry: THREE.BufferGeometry,
  params: FurParams,
  strandCount = 12000
): {
  mesh: THREE.InstancedMesh;
  updateUniforms: (next: FurParams, timeSec: number) => void;
  dispose: () => void;
} {
  // Tapered strand geometry (3 segments) for WebGPU / Instanced strand rendering
  const strandGeo = new THREE.ConeGeometry(0.00045, params.hairLength, 3, 2);
  strandGeo.translate(0, params.hairLength * 0.5, 0);

  const strandMat = new THREE.MeshStandardMaterial({
    color: "#c88d4b",
    roughness: 0.65,
    metalness: 0.0,
  });

  const mesh = new THREE.InstancedMesh(strandGeo, strandMat, strandCount);
  mesh.name = "fur_strands_instanced";

  const posAttr = baseGeometry.getAttribute("position");
  const normAttr = baseGeometry.getAttribute("normal");
  const vCount = posAttr.count;
  const dummy = new THREE.Object3D();
  const up = new THREE.Vector3(0, 1, 0);
  const pos = new THREE.Vector3();
  const nrm = new THREE.Vector3();
  const quat = new THREE.Quaternion();

  for (let i = 0; i < strandCount; i++) {
    const vi = (i * 7919) % vCount;
    pos.fromBufferAttribute(posAttr, vi);
    nrm.fromBufferAttribute(normAttr, vi).normalize();
    quat.setFromUnitVectors(up, nrm);
    dummy.position.copy(pos);
    dummy.quaternion.copy(quat);
    dummy.scale.set(1, 0.8 + ((i % 13) / 13) * 0.4, 1);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }
  mesh.instanceMatrix.needsUpdate = true;

  return {
    mesh,
    updateUniforms: (next: FurParams) => {
      const scaleY = next.hairLength / 0.012;
      mesh.scale.setScalar(1);
      strandMat.roughness = THREE.MathUtils.clamp(0.85 - next.rimLightStrength * 0.2, 0.2, 0.95);
      void scaleY;
    },
    dispose: () => {
      strandGeo.dispose();
      strandMat.dispose();
    },
  };
}

