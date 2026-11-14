import * as THREE from "three";
import type { LoadedHamsterAsset } from "../rig/types";

export interface EnhancedHamsterVisuals {
  syncLodVisibility: () => void;
  dispose: () => void;
}

const SOFT_SHELL_VERT_PARS = /* glsl */ `
  uniform float uShellFrac;
  uniform float uFurLength;
`;

const SOFT_SHELL_VERT_BEGIN = /* glsl */ `
  transformed += normalize(normal) * (uShellFrac * uFurLength);
  transformed.y -= uShellFrac * uShellFrac * uFurLength * 0.25;
`;

function createSoftHaloShellMaterial(shellFrac: number, furLength: number, hasVertexColors: boolean): THREE.MeshPhysicalMaterial {
  const mat = new THREE.MeshPhysicalMaterial({
    color: hasVertexColors ? "#ffffff" : "#c8894c",
    vertexColors: hasVertexColors,
    roughness: 0.92,
    metalness: 0.0,
    sheen: 1.0,
    sheenRoughness: 0.55,
    sheenColor: new THREE.Color("#fff0d8"),
    transparent: true,
    opacity: Math.max(0.04, 0.22 * (1.0 - shellFrac * 0.72)),
    depthWrite: false,
  });

  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uShellFrac = { value: shellFrac };
    shader.uniforms.uFurLength = { value: furLength };

    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>\n${SOFT_SHELL_VERT_PARS}`)
      .replace("#include <begin_vertex>", `#include <begin_vertex>\n${SOFT_SHELL_VERT_BEGIN}`);
  };
  mat.customProgramCacheKey = () => `hammy_soft_halo_v2_${shellFrac.toFixed(3)}_${hasVertexColors}`;
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
      if (m.name.includes("LOD0") || m.name.includes("LOD1")) {
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

  // 4 subtle soft halo shells for plush silhouette without sponge artifacts
  const haloCount = 4;
  const furLength = 0.0024;
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
