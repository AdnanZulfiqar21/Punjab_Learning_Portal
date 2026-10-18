// Original 3D model after Figure 1.2: an archaeal membrane lipid (ether linkages, branched chains) beside a
// bacterial/eukaryotic lipid (ester linkages, unbranched chains). Ball-and-stick, not to molecular scale.
export const title = "Membrane lipids of Archaea compared with Bacteria and Eukarya";

const C = { glycerol: 0x0f7a62, phosphate: 0xb26a00, oxygen: 0xc0392b, carbon: 0x5b6b7a, branch: 0x8aa2b4 };

function ball(THREE, r, color, x, y, z) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 32, 24), new THREE.MeshStandardMaterial({ color, roughness: 0.45 }));
  m.position.set(x, y, z);
  return m;
}
function stick(THREE, a, b, r = 0.08, color = 0x9aa5b1) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const len = dir.length();
  const geo = new THREE.CylinderGeometry(r, r, len, 16);
  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color, roughness: 0.6 }));
  m.position.copy(a).add(dir.clone().multiplyScalar(0.5));
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  return m;
}

/** One lipid: a glycerol head with a phosphate, two chains hanging down. `branched` adds side groups and an ether O. */
function lipid(THREE, x, branched) {
  const g = new THREE.Group();
  const head = new THREE.Vector3(x, 2.6, 0);
  g.add(ball(THREE, 0.55, C.glycerol, head.x, head.y, head.z));
  const phos = new THREE.Vector3(x, 3.7, 0);
  g.add(ball(THREE, 0.42, C.phosphate, phos.x, phos.y, phos.z));
  g.add(stick(THREE, head, phos, 0.1));
  for (const side of [-0.75, 0.75]) {
    const linkO = new THREE.Vector3(x + side, 1.7, 0);
    g.add(stick(THREE, head, linkO, 0.09));
    g.add(ball(THREE, 0.3, C.oxygen, linkO.x, linkO.y, linkO.z)); // the O of the ether or ester linkage
    let prev = linkO;
    if (!branched) {
      // ester: a carbonyl oxygen on the first chain carbon
      const c1 = new THREE.Vector3(x + side, 0.9, 0);
      g.add(stick(THREE, prev, c1, 0.09));
      g.add(ball(THREE, 0.3, C.carbon, c1.x, c1.y, c1.z));
      const dbl = new THREE.Vector3(x + side * 1.55, 0.95, 0);
      g.add(stick(THREE, c1, dbl, 0.12, C.oxygen));
      g.add(ball(THREE, 0.24, C.oxygen, dbl.x, dbl.y, dbl.z));
      prev = c1;
    }
    const n = 6;
    for (let i = 0; i < n; i++) {
      const zig = (i % 2 === 0 ? 0.18 : -0.18) * (branched ? 1 : 1);
      const c = new THREE.Vector3(x + side + zig, prev.y - 0.75, 0);
      g.add(stick(THREE, prev, c, 0.09));
      g.add(ball(THREE, 0.28, C.carbon, c.x, c.y, c.z));
      if (branched && i % 2 === 1) {
        const br = new THREE.Vector3(c.x + side * 0.7, c.y + 0.15, 0.35);
        g.add(stick(THREE, c, br, 0.08, C.branch));
        g.add(ball(THREE, 0.22, C.branch, br.x, br.y, br.z));
      }
      prev = c;
    }
  }
  return g;
}

export function build(THREE) {
  const group = new THREE.Group();
  group.add(lipid(THREE, -2.6, true));
  group.add(lipid(THREE, 2.6, false));
  // a faint divider between the two molecules
  const divider = new THREE.Mesh(
    new THREE.BoxGeometry(0.04, 9, 0.04),
    new THREE.MeshStandardMaterial({ color: 0xd9dee6, roughness: 1 }),
  );
  divider.position.set(0, -0.4, -0.5);
  group.add(divider);
  return {
    group,
    camera: { position: [0.6, 0.6, 13.2], lookAt: [0, 0.4, 0], fov: 38 },
    turntableAxis: "y",
    labels: [
      { text: "Archaea", at: [-2.6, 4.7, 0], anchor: "above" },
      { text: "Bacteria and Eukarya", at: [2.6, 4.7, 0], anchor: "above" },
      { text: "Phosphate group", at: [2.6, 3.7, 0], anchor: "right" },
      { text: "Glycerol", at: [2.6, 2.6, 0], anchor: "right" },
      { text: "Ether linkage", at: [-1.85, 1.7, 0], anchor: "right" },
      { text: "Branched chain", at: [-3.35, -1.6, 0], anchor: "left" },
      { text: "Ester linkage", at: [3.35, 1.7, 0], anchor: "right" },
      { text: "Unbranched chain", at: [3.35, -2.0, 0], anchor: "right" },
    ],
  };
}
