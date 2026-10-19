// Original 3D model after Figure 3.22: a gyroscope. A heavy rotor spins on an axle held by an inner gimbal ring,
// which turns inside an outer gimbal ring on a stand, so the spin axis can keep its direction. Proportions are schematic.
export const title = "A gyroscope in gimbal rings";

function mat(THREE, color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.25, ...opts });
}

export function build(THREE) {
  const group = new THREE.Group();
  // Stand: base disc, pillar and a fork holding the outer ring at top and bottom.
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.0, 0.18, 48), mat(THREE, 0x64748b));
  base.position.y = -2.05;
  group.add(base);
  const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.14, 0.55, 20), mat(THREE, 0x94a3b8));
  pillar.position.y = -1.7;
  group.add(pillar);
  // Outer gimbal: a vertical ring in the x-y plane, pivoted at top and bottom (y axis).
  const outer = new THREE.Mesh(new THREE.TorusGeometry(1.42, 0.06, 16, 96), mat(THREE, 0xd98b2b));
  group.add(outer);
  for (const y of [1.42, -1.42]) {
    const pin = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 12), mat(THREE, 0x334155));
    pin.position.y = y;
    group.add(pin);
  }
  // Inner gimbal: a ring in the y-z plane, pivoted on the outer ring at left and right (x axis).
  const inner = new THREE.Mesh(new THREE.TorusGeometry(1.15, 0.055, 16, 96), mat(THREE, 0x1f6fb5));
  inner.rotation.y = Math.PI / 2;
  group.add(inner);
  for (const x of [1.36, -1.36]) {
    const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.3, 12), mat(THREE, 0x334155));
    pin.rotation.z = Math.PI / 2;
    pin.position.x = x;
    group.add(pin);
  }
  // Rotor: a heavy disc spinning about the z axis, on an axle held by the inner ring at front and back.
  const rotor = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, 0.22, 64), mat(THREE, 0x475569, { metalness: 0.5 }));
  rotor.rotation.x = Math.PI / 2;
  group.add(rotor);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.85, 0.09, 16, 72), mat(THREE, 0x1e293b, { metalness: 0.5 }));
  group.add(rim);
  const axle = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.4, 16), mat(THREE, 0x0f172a));
  axle.rotation.x = Math.PI / 2;
  group.add(axle);
  // Spin axis and angular momentum L = I omega along the axle.
  const red = mat(THREE, 0xd7322f, { metalness: 0 });
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 1.1, 12), red);
  shaft.rotation.x = Math.PI / 2;
  shaft.position.z = 1.75;
  group.add(shaft);
  const tip = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.3, 20), red);
  tip.rotation.x = Math.PI / 2;
  tip.position.z = 2.4;
  group.add(tip);
  return {
    group,
    camera: { position: [4.1, 1.7, 5.1], lookAt: [0, -0.35, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "Rotor (spinning wheel)", at: [0.6, 0.55, 0.15], anchor: "left" },
      { text: "Spin axis: L = I omega", at: [0, 0, 2.3], anchor: "below" },
      { text: "Inner gimbal ring", at: [0, 1.15, 0], anchor: "above" },
      { text: "Outer gimbal ring", at: [1.0, 1.0, 0], anchor: "right" },
      { text: "Stand", at: [0.9, -2.0, 0], anchor: "right" },
    ],
  };
}
