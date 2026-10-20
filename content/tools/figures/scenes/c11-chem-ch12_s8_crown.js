// Original 3D model after Figure 12.7: cyclo-octasulfur, S8. Eight sulfur atoms joined by single S-S bonds in a
// puckered ring, alternately up and down, so the molecule looks like a crown. The pucker is set so that every
// S-S-S angle is 108 degrees, as in the real molecule; sizes are schematic.
export const title = "The S8 crown";

export function build(THREE) {
  const group = new THREE.Group();
  const UP = new THREE.Vector3(0, 1, 0);
  const sMat = new THREE.MeshStandardMaterial({ color: 0xeab308, roughness: 0.4, metalness: 0.05 });
  const bondMat = new THREE.MeshStandardMaterial({ color: 0xa16207, roughness: 0.5 });
  const R = 1.6;
  // For an alternating crown, cos(angle) = (4h^2 - 0.4142 R^2) / (4h^2 + 0.5858 R^2); h = 0.211 R gives 108 degrees.
  const H = 0.211 * R;
  const atoms = [];
  for (let k = 0; k < 8; k++) {
    const a = (k * Math.PI) / 4;
    atoms.push(new THREE.Vector3(R * Math.cos(a), k % 2 === 0 ? H : -H, R * Math.sin(a)));
  }
  for (const p of atoms) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.34, 32, 16), sMat);
    m.position.copy(p);
    group.add(m);
  }
  for (let k = 0; k < 8; k++) {
    const a = atoms[k];
    const b = atoms[(k + 1) % 8];
    const dir = new THREE.Vector3().subVectors(b, a);
    const len = dir.length();
    const stick = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, len, 16), bondMat);
    stick.position.copy(a).add(b).multiplyScalar(0.5);
    stick.quaternion.setFromUnitVectors(UP, dir.normalize());
    group.add(stick);
  }
  // Faint guide rings through the upper and lower atoms show the two layers of the crown.
  for (const y of [H, -H]) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(R, 0.012, 8, 96),
      new THREE.MeshStandardMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.55 }),
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = y;
    group.add(ring);
  }
  return {
    group,
    camera: { position: [0, 3.0, 6.6], lookAt: [0, -0.15, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "Four sulfur atoms up", at: [atoms[0].x, atoms[0].y + 0.3, atoms[0].z], anchor: "above" },
      { text: "Four sulfur atoms down", at: [atoms[3].x, atoms[3].y - 0.3, atoms[3].z], anchor: "below" },
      { text: "S-S single bonds", at: [(atoms[1].x + atoms[2].x) / 2, 0, (atoms[1].z + atoms[2].z) / 2], anchor: "below" },
      { text: "Bond angle 108 degrees", at: [atoms[6].x, atoms[6].y + 0.3, atoms[6].z], anchor: "above" },
    ],
  };
}
