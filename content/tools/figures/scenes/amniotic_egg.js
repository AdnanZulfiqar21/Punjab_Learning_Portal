// Original 3D model after Figure 1.24: an amniotic egg cut open. Shell, chorion, albumin, amnion with the embryo,
// yolk sac and allantois. Proportions are schematic.
export const title = "The amniotic egg";

function mat(THREE, color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.7, side: THREE.DoubleSide, ...opts });
}

function eggProfile(THREE, scale, n = 24) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = (i / n) * Math.PI; // 0 at the top, PI at the bottom
    const y = Math.cos(t);
    const r = Math.sin(t) * (1 + 0.18 * y); // slightly narrower at the top, like a bird's egg
    pts.push(new THREE.Vector2(Math.max(r * scale * 1.35, 0.001), y * scale * 1.8));
  }
  return pts;
}

export function build(THREE) {
  const group = new THREE.Group();
  // Shell and chorion as thin half-lathes (phiLength PI) so the inside is visible from the front.
  const shell = new THREE.Mesh(new THREE.LatheGeometry(eggProfile(THREE, 1.0), 64, Math.PI * 0.5, Math.PI), mat(THREE, 0xf4e8d2));
  group.add(shell);
  const chorion = new THREE.Mesh(new THREE.LatheGeometry(eggProfile(THREE, 0.93), 64, Math.PI * 0.5, Math.PI), mat(THREE, 0xe9c9a2));
  group.add(chorion);
  // Albumin fills the inside: a translucent full lathe slightly smaller again.
  const albumin = new THREE.Mesh(new THREE.LatheGeometry(eggProfile(THREE, 0.9), 64), mat(THREE, 0xfff5dc, { transparent: true, opacity: 0.35 }));
  group.add(albumin);
  // Yolk sac: a large yellow sphere low in the egg.
  const yolk = new THREE.Mesh(new THREE.SphereGeometry(0.95, 48, 32), mat(THREE, 0xf2b705, { roughness: 0.45 }));
  yolk.position.set(0, -0.55, 0.1);
  group.add(yolk);
  // Amnion: a translucent sac above the yolk with the embryo inside.
  const amnion = new THREE.Mesh(new THREE.SphereGeometry(0.62, 48, 32), mat(THREE, 0xa9d7ea, { transparent: true, opacity: 0.45 }));
  amnion.position.set(0.05, 0.75, 0.25);
  group.add(amnion);
  // Embryo: a curled torus with a head sphere.
  const embryo = new THREE.Mesh(new THREE.TorusGeometry(0.22, 0.09, 12, 32, Math.PI * 1.5), mat(THREE, 0xc0392b, { roughness: 0.5 }));
  embryo.position.set(0.05, 0.75, 0.3);
  embryo.rotation.set(0.4, 0.3, 0.6);
  group.add(embryo);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.14, 24, 16), mat(THREE, 0xc0392b, { roughness: 0.5 }));
  head.position.set(0.22, 0.95, 0.42);
  group.add(head);
  // Stalk from embryo to yolk sac.
  const stalk = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.5, 10), mat(THREE, 0xd98b2b));
  stalk.position.set(0.02, 0.25, 0.25);
  group.add(stalk);
  // Allantois: a flattened sac to the side, in contact with the chorion.
  const allantois = new THREE.Mesh(new THREE.SphereGeometry(0.5, 40, 28), mat(THREE, 0x9bc8a5, { transparent: true, opacity: 0.75 }));
  allantois.scale.set(0.85, 0.7, 0.8);
  allantois.position.set(-0.68, 0.3, 0.35);
  group.add(allantois);
  const allStalk = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.6, 10), mat(THREE, 0x6f9f7a));
  allStalk.position.set(-0.45, 0.3, 0.3);
  allStalk.rotation.z = Math.PI / 2;
  group.add(allStalk);
  return {
    group,
    camera: { position: [0.3, 0.9, 6.2], lookAt: [0, 0, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "Shell", at: [1.05, 1.1, 0.4], anchor: "right" },
      { text: "Chorion", at: [1.2, 0.2, 0.3], anchor: "right" },
      { text: "Albumin", at: [0.9, -1.25, 0.4], anchor: "right" },
      { text: "Amnion (fluid around the embryo)", at: [0.3, 1.45, 0.3], anchor: "above" },
      { text: "Embryo", at: [0.35, 0.95, 0.5], anchor: "right" },
      { text: "Yolk sac", at: [-0.1, -0.7, 1.0], anchor: "below" },
      { text: "Allantois", at: [-1.05, 0.3, 0.4], anchor: "left" },
    ],
  };
}
