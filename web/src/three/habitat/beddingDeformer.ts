import * as THREE from "three";

export class BeddingDeformer {
  private readonly restPositions: Float32Array;
  private readonly posAttr: THREE.BufferAttribute;
  private readonly invMatrix = new THREE.Matrix4();
  private readonly localPaw = new THREE.Vector3();

  constructor(private readonly mesh: THREE.Mesh) {
    this.posAttr = mesh.geometry.getAttribute("position") as THREE.BufferAttribute;
    this.restPositions = new Float32Array(this.posAttr.array as Float32Array);
    mesh.updateWorldMatrix(true, false);
    this.invMatrix.copy(mesh.matrixWorld).invert();
  }

  /**
   * Depress bedding vertices near paw world positions with a subtle pushed-up rim.
   */
  public deformAtPaws(pawWorldPositions: THREE.Vector3[], radius = 0.028, depth = 0.007): void {
    this.mesh.updateWorldMatrix(true, false);
    this.invMatrix.copy(this.mesh.matrixWorld).invert();

    const localPaws = pawWorldPositions.map((wp) => this.localPaw.copy(wp).applyMatrix4(this.invMatrix).clone());
    const arr = this.posAttr.array as Float32Array;
    const count = this.posAttr.count;
    const r2 = radius * radius;
    const rimR = radius * 1.45;
    const rimR2 = rimR * rimR;

    for (let i = 0; i < count; i++) {
      const ix = i * 3;
      const rx = this.restPositions[ix];
      const ry = this.restPositions[ix + 1];
      const rz = this.restPositions[ix + 2];

      let deltaY = 0;
      for (const lp of localPaws) {
        const dx = rx - lp.x;
        const dz = rz - lp.z;
        const d2 = dx * dx + dz * dz;
        if (d2 < r2) {
          const t = 1 - Math.sqrt(d2) / radius;
          deltaY -= depth * t * t;
        } else if (d2 < rimR2) {
          const u = (Math.sqrt(d2) - radius) / (rimR - radius);
          deltaY += depth * 0.22 * Math.sin(u * Math.PI);
        }
      }

      // Accumulate gentle persistent trail blended with rest height
      const targetY = ry + deltaY;
      arr[ix] = rx;
      arr[ix + 1] = THREE.MathUtils.lerp(arr[ix + 1], targetY, 0.35);
      arr[ix + 2] = rz;
    }

    this.posAttr.needsUpdate = true;
    this.mesh.geometry.computeVertexNormals();
  }
}

