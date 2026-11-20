import * as THREE from "three";
import type { LoadedHamsterAsset } from "../rig/types";

export interface EnhancedHamsterVisuals {
  syncLodVisibility: () => void;
  dispose: () => void;
}

const SOFT_SHELL_VERT_PARS = /* glsl */ `
  uniform float uShellFrac;
  uniform float uFurLength;
  varying vec3 vFurLocalPos;
`;

const SOFT_SHELL_VERT_AFTER_MORPH = /* glsl */ `
  vFurLocalPos = transformed;
  vec3 furNrm = normalize(objectNormal);
  // Extrude cleanly along post-morph smoothed surface normal (no bind-pose Y skew)
  transformed += furNrm * (uShellFrac * uFurLength);
`;

const SOFT_SHELL_FRAG_PARS = /* glsl */ `
  uniform float uShellFrac;
  varying vec3 vFurLocalPos;

  float furHash31(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
  }

  float furValueNoise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float n000 = furHash31(i + vec3(0.0, 0.0, 0.0));
    float n100 = furHash31(i + vec3(1.0, 0.0, 0.0));
    float n010 = furHash31(i + vec3(0.0, 1.0, 0.0));
    float n110 = furHash31(i + vec3(1.0, 1.0, 0.0));
    float n001 = furHash31(i + vec3(0.0, 0.0, 1.0));
    float n101 = furHash31(i + vec3(1.0, 0.0, 1.0));
    float n011 = furHash31(i + vec3(0.0, 1.0, 1.0));
    float n111 = furHash31(i + vec3(1.0, 1.0, 1.0));
    float nx00 = mix(n000, n100, f.x);
    float nx10 = mix(n010, n110, f.x);
    float nx01 = mix(n001, n101, f.x);
    float nx11 = mix(n011, n111, f.x);
    return mix(mix(nx00, nx10, f.y), mix(nx01, nx11, f.y), f.z);
  }
`;

const SOFT_SHELL_FRAG_ALPHA = /* glsl */ `
  // Smooth plush 3D coat density + view-angle feathering so every angle & distance is velvety
  float coatFine = furValueNoise(vFurLocalPos * 210.0);
  float coatClump = furValueNoise(vFurLocalPos * 72.0);
  float strandMask = smoothstep(0.18 + uShellFrac * 0.34, 0.78 + uShellFrac * 0.16, coatFine * 0.65 + coatClump * 0.35);
  float ndotv = clamp(abs(dot(normalize(normal), normalize(vViewPosition))), 0.0, 1.0);
  // Gently feather extreme grazing silhouettes on outer shells to prevent hard stepped shell edges
  float rimSoften = mix(1.0, smoothstep(0.06, 0.42, ndotv), uShellFrac * 0.65);
  // Subtle warm sheen lift toward hair tips
  diffuseColor.rgb *= mix(0.92, 1.08, uShellFrac);
  diffuseColor.a *= mix(0.55, 1.0, strandMask) * rimSoften;
`;

function createSoftHaloShellMaterial(shellFrac: number, furLength: number, hasVertexColors: boolean): THREE.MeshPhysicalMaterial {
  const mat = new THREE.MeshPhysicalMaterial({
    color: hasVertexColors ? "#ffffff" : "#c8894c",
    vertexColors: hasVertexColors,
    roughness: 0.90,
    metalness: 0.0,
    sheen: 1.0,
    sheenRoughness: 0.52,
    sheenColor: new THREE.Color("#fff2dc"),
    transparent: true,
    opacity: Math.max(0.045, 0.24 * Math.pow(1.0 - shellFrac * 0.76, 1.15)),
    depthWrite: false,
  });

  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uShellFrac = { value: shellFrac };
    shader.uniforms.uFurLength = { value: furLength };

    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>\n${SOFT_SHELL_VERT_PARS}`)
      .replace("#include <morphtarget_vertex>", `#include <morphtarget_vertex>\n${SOFT_SHELL_VERT_AFTER_MORPH}`);

    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\n${SOFT_SHELL_FRAG_PARS}`)
      .replace("#include <normal_fragment_begin>", `#include <normal_fragment_begin>\n${SOFT_SHELL_FRAG_ALPHA}`);
  };
  mat.customProgramCacheKey = () => `hammy_soft_halo_v3_${shellFrac.toFixed(3)}_${hasVertexColors}`;
  return mat;
}

function buildWhiskersGroup(): THREE.Group {
  const group = new THREE.Group();
  group.name = "ham_procedural_whiskers";

  const whiskerMat = new THREE.LineBasicMaterial({
    color: "#f4ede2",
    transparent: true,
    opacity: 0.58,
  });

  const anglesY = [-0.28, -0.08, 0.14, 0.34];
  const anglesX = [-0.14, 0.04, 0.18];

  for (const side of [-1, 1]) {
    for (let i = 0; i < anglesY.length; i++) {
      const ay = anglesY[i];
      const ax = anglesX[i % anglesX.length];
      const len = 0.030 + (i % 2) * 0.007;
      const pts: THREE.Vector3[] = [];
      for (let s = 0; s <= 4; s++) {
        const t = s / 4;
        const x = side * (0.007 + t * len * Math.cos(ay));
        const y = -0.003 + t * len * Math.sin(ax) - t * t * 0.004;
        const z = 0.022 + t * len * Math.sin(ay) * 0.45;
        pts.push(new THREE.Vector3(x, y, z));
      }
      const geom = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(geom, whiskerMat);
      group.add(line);
    }
  }
  return group;
}

/**
 * Enhances the Blender-exported hamster asset with:
 * - Blender-baked Syrian golden-agouti & cream-belly vertex colors + velvety sheen
 * - Subtle soft translucent fur-halo shells (no jagged cutouts)
 * - Glossy obsidian bead eyes with clearcoat highlights
 * - Delicate head-tracked whiskers
 */
export function enhanceHamsterVisuals(
  asset: LoadedHamsterAsset,
  _shellCount: number = 6
): EnhancedHamsterVisuals {
  const disposables: Array<{ dispose: () => void }> = [];

  const eyeMat = new THREE.MeshPhysicalMaterial({
    color: "#040406",
    roughness: 0.02,
    metalness: 0.05,
    clearcoat: 1.0,
    clearcoatRoughness: 0.02,
    envMapIntensity: 2.5,
  });
  const noseMat = new THREE.MeshPhysicalMaterial({
    color: "#ea949b",
    roughness: 0.24,
    clearcoat: 0.75,
  });
  const earMat = new THREE.MeshPhysicalMaterial({
    color: "#6b534c",
    roughness: 0.78,
    sheen: 0.45,
    sheenColor: new THREE.Color("#b89c94"),
  });
  const pawMat = new THREE.MeshStandardMaterial({
    color: "#e6b8ae",
    roughness: 0.72,
  });
  disposables.push(eyeMat, noseMat, earMat, pawMat);

  const shellBindings: Array<{ parentMesh: THREE.Mesh; shells: THREE.Mesh[] }> = [];
  const bodyTargets: THREE.Mesh[] = [];
  let hasVertexColors = false;

  // Replace decimated LOD1's high-aspect sliver triangles with LOD0's smooth mesh geometry
  // so transitions between LOD0 and LOD1 never exhibit sharp polygonal facets or spiky fur.
  const lod0Mesh = asset.lodMeshes.LOD0;
  const lod1Mesh = asset.lodMeshes.LOD1;
  if (lod0Mesh && lod1Mesh && lod0Mesh.geometry && lod1Mesh.geometry !== lod0Mesh.geometry) {
    lod1Mesh.geometry = lod0Mesh.geometry;
    lod1Mesh.morphTargetDictionary = lod0Mesh.morphTargetDictionary;
    lod1Mesh.morphTargetInfluences = lod0Mesh.morphTargetInfluences;
    if ((lod0Mesh as THREE.SkinnedMesh).isSkinnedMesh && (lod1Mesh as THREE.SkinnedMesh).isSkinnedMesh) {
      const sm0 = lod0Mesh as THREE.SkinnedMesh;
      const sm1 = lod1Mesh as THREE.SkinnedMesh;
      sm1.bind(sm0.skeleton, sm0.bindMatrix);
    }
  }

  asset.root.traverse((obj) => {
    if (!(obj as THREE.Mesh).isMesh) return;
    const m = obj as THREE.Mesh;
    if (m.name.includes("ham_body")) {
      const hasCol = Boolean(m.geometry.attributes.color);
      hasVertexColors = hasVertexColors || hasCol;
      const bodyMat = new THREE.MeshPhysicalMaterial({
        color: hasCol ? "#ffffff" : "#c8894c",
        vertexColors: hasCol,
        roughness: 0.88,
        metalness: 0.0,
        sheen: 0.95,
        sheenRoughness: 0.62,
        sheenColor: new THREE.Color("#ffe9cc"),
      });
      disposables.push(bodyMat);
      m.material = bodyMat;
      if (m.name.includes("LOD0") || m.name.includes("LOD1") || m.name.includes("LOD2")) {
        bodyTargets.push(m);
      }
    } else if (m.name.includes("ham_eye")) {
      m.material = eyeMat;
      m.renderOrder = 2;
    } else if (m.name.includes("ham_nose")) {
      m.material = noseMat;
    } else if (m.name.includes("ham_ear")) {
      m.material = earMat;
    } else if (m.name.includes("ham_paw") || m.name.includes("ham_tail")) {
      m.material = pawMat;
    }
  });

  // 6 finely graded soft halo shells for consistent plush coat across all angles and distances
  const haloCount = 6;
  const furLength = 0.0028;
  for (const bodyMesh of bodyTargets) {
    const shells: THREE.Mesh[] = [];
    const parent = bodyMesh.parent || asset.root;
    const hasCol = Boolean(bodyMesh.geometry.attributes.color);

    for (let i = 1; i <= haloCount; i++) {
      const frac = i / haloCount;
      const shellMat = createSoftHaloShellMaterial(frac, furLength, hasCol);
      disposables.push(shellMat);

      let shellMesh: THREE.Mesh;
      if ((bodyMesh as THREE.SkinnedMesh).isSkinnedMesh) {
        const skinnedSource = bodyMesh as THREE.SkinnedMesh;
        const sm = new THREE.SkinnedMesh(bodyMesh.geometry, shellMat);
        sm.bind(skinnedSource.skeleton, skinnedSource.bindMatrix);
        sm.morphTargetDictionary = skinnedSource.morphTargetDictionary;
        sm.morphTargetInfluences = skinnedSource.morphTargetInfluences;
        shellMesh = sm;
      } else {
        shellMesh = new THREE.Mesh(bodyMesh.geometry, shellMat);
      }

      shellMesh.name = `${bodyMesh.name}_fur_halo_${i}`;
      shellMesh.position.copy(bodyMesh.position);
      shellMesh.rotation.copy(bodyMesh.rotation);
      shellMesh.scale.copy(bodyMesh.scale);
      shellMesh.castShadow = false;
      shellMesh.receiveShadow = false;
      shellMesh.visible = bodyMesh.visible;
      shellMesh.renderOrder = 1;
      parent.add(shellMesh);
      shells.push(shellMesh);
    }

    shellBindings.push({ parentMesh: bodyMesh, shells });
  }

  const headBone = asset.bones.get("head");
  const whiskers = buildWhiskersGroup();
  if (headBone) {
    headBone.add(whiskers);
  } else {
    asset.root.add(whiskers);
  }

  const syncLodVisibility = () => {
    for (const binding of shellBindings) {
      for (const s of binding.shells) {
        s.visible = binding.parentMesh.visible;
      }
    }
  };

  const dispose = () => {
    for (const binding of shellBindings) {
      for (const s of binding.shells) {
        s.parent?.remove(s);
      }
    }
    whiskers.parent?.remove(whiskers);
    whiskers.traverse((obj) => {
      if ((obj as THREE.Line).geometry) {
        (obj as THREE.Line).geometry.dispose();
      }
    });
    for (const d of disposables) {
      d.dispose();
    }
  };

  return { syncLodVisibility, dispose };
}
