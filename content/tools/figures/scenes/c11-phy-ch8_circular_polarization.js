// Original 3D model after Figure 8.4(b): circularly polarized light. The electric field vector keeps the same size
// and turns steadily as the wave moves, so its tip traces a helix around the direction of travel. Schematic.
export const title = "Circular polarization";

export function build(THREE) {
  const group = new THREE.Group();
  const L = 6;
  const R = 0.85;
  const turns = 2;
  const axisMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.6 });
  const axis = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, L + 0.8, 12), axisMat);
  axis.rotation.z = Math.PI / 2;
  group.add(axis);
  const tip = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.3, 16), axisMat);
  tip.rotation.z = -Math.PI / 2;
  tip.position.x = L / 2 + 0.5;
  group.add(tip);
  // Helix traced by the tip of E.
  const pts = [];
  for (let i = 0; i <= 400; i++) {
    const t = i / 400;
    const a = t * turns * Math.PI * 2;
    pts.push(new THREE.Vector3(-L / 2 + t * L, R * Math.cos(a), R * Math.sin(a)));
  }
  const helix = new THREE.Mesh(
    new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 400, 0.035, 8, false),
    new THREE.MeshStandardMaterial({ color: 0x7c3aed, roughness: 0.4 }),
  );
  group.add(helix);
  // Electric field vectors from the axis to the helix.
  const red = new THREE.MeshStandardMaterial({ color: 0xd7322f, roughness: 0.45 });
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const a = t * turns * Math.PI * 2;
    const x = -L / 2 + t * L;
    const dir = new THREE.Vector3(0, Math.cos(a), Math.sin(a));
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, R - 0.14, 8), red);
    shaft.position.set(x, 0, 0).addScaledVector(dir, (R - 0.14) / 2);
    shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    group.add(shaft);
    const head = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.16, 12), red);
    head.position.set(x, 0, 0).addScaledVector(dir, R - 0.08);
    head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    group.add(head);
  }
  // A faint end ring showing the circle the tip follows.
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(R, 0.015, 8, 64),
    new THREE.MeshStandardMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.6 }),
  );
  ring.rotation.y = Math.PI / 2;
  ring.position.x = L / 2;
  group.add(ring);
  return {
    group,
    camera: { position: [0.6, 2.2, 8.0], lookAt: [0.3, 0.35, 0], fov: 40 },
    turntableAxis: "x",
    labels: [
      { text: "Direction of travel", at: [L / 2 + 0.5, 0, 0], anchor: "below" },
      { text: "E keeps its size and turns", at: [-1.5, R * Math.cos(1.5 * Math.PI), R * Math.sin(1.5 * Math.PI)], anchor: "above" },
      { text: "Tip of E traces a helix", at: [1.5, R * Math.cos(3 * Math.PI), R * Math.sin(3 * Math.PI)], anchor: "below" },
    ],
  };
}
