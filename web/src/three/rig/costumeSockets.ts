import * as THREE from "three";
import type { CostumeSlot } from "../../types";

export interface CostumeSocketTransform {
  slot: CostumeSlot;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
}

/**
 * Per-costume anatomical socket transforms calibrated against `ham_body_LOD0` vertices
 * and the exported glTF bone axes in `hamster.glb`.
 *
 * Note on `neck_slot` bone axes in `hamster.glb`:
 *   world_pos = (0, +0.025, +0.044)
 *   local_X -> world -X, local_Y -> world +Z (forward along neck), local_Z -> world +Y (up)
 * Without socket compensation, `costume_bow_tie` and `costume_scarf` sat buried inside the
 * hamster's throat/chest mesh. These offsets mount every costume cleanly outside the coat fur.
 */
export const COSTUME_SOCKET_TRANSFORMS: Record<string, CostumeSocketTransform> = {
  costume_bow_tie: {
    slot: "neck_slot",
    // Mount upright & forward-facing right under the chin on the outer chest fur
    position: [0.0, 0.032, -0.011],
    rotation: [Math.PI / 2 + 0.18, 0.0, Math.PI],
    scale: [1.3, 1.3, 1.3],
  },
  costume_scarf: {
    slot: "neck_slot",
    // Wrap snugly around the hamster's oval neck circumference with the knit tail draping downward
    position: [0.0, -0.004, 0.0095],
    rotation: [0.0, Math.PI, 0.0],
    scale: [1.96, 1.45, 1.32],
  },
  costume_tiny_glasses: {
    slot: "head_slot",
    // Lower from crown of head down to eye bridge (eyes at Y~0.043, Z~0.052)
    position: [0.0, -0.0125, 0.008],
    rotation: [0.0, 0.0, 0.0],
    scale: [1.55, 1.25, 1.25],
  },
  costume_party_hat: {
    slot: "head_slot",
    position: [0.0, 0.003, 0.0],
    rotation: [0.0, 0.0, 0.0],
    scale: [1.0, 1.0, 1.0],
  },
  costume_top_hat: {
    slot: "head_slot",
    position: [0.0, 0.003, 0.0],
    rotation: [0.0, 0.0, 0.0],
    scale: [1.0, 1.0, 1.0],
  },
  costume_crown: {
    slot: "head_slot",
    position: [0.0, 0.003, 0.0],
    rotation: [0.0, 0.0, 0.0],
    scale: [1.05, 1.05, 1.05],
  },
  costume_backpack: {
    slot: "back_slot",
    position: [0.0, 0.007, 0.0],
    rotation: [0.0, 0.0, 0.0],
    scale: [1.1, 1.1, 1.1],
  },
};

export function applyCostumeSocketTransform(
  itemId: string,
  holder: THREE.Object3D,
  loadedScene?: THREE.Object3D
): void {
  const cfg = COSTUME_SOCKET_TRANSFORMS[itemId];
  if (cfg) {
    holder.position.set(...cfg.position);
    holder.rotation.set(...cfg.rotation);
    holder.scale.set(...cfg.scale);
  } else {
    holder.position.set(0, 0, 0);
    holder.rotation.set(0, 0, 0);
    holder.scale.set(1, 1, 1);
  }

  if (loadedScene) {
    loadedScene.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        // Render cleanly above translucent fur halo shells (renderOrder=1)
        mesh.renderOrder = 3;
      }
    });
  }
}
