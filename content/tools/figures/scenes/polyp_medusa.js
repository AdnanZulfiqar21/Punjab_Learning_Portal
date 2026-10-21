// Original 3D model: the polyp and medusa body forms of cnidarians, each cut to show the two body layers and the
// gastrovascular cavity.
export const title = "Polyp and medusa";

function mat(THREE, color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.65, side: THREE.DoubleSide, ...opts });
}

function tentacle(THREE, from, dir, len, color) {
  const pts = [];
  for (let i = 0; i <= 6; i++) {
    const t = i / 6;
    pts.push(new THREE.Vector3(from.x + dir.x * t * len, from.y + dir.y * t * len - 0.25 * t * t, from.z + dir.z * t * len));
  }
  return new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 24, 0.06, 10, false), mat(THREE, color));
}

export function build(THREE) {
  const group = new THREE.Group();
  const epidermis = 0xe4b98a;
  const gastrodermis = 0x0f7a62;
  const mesoglea = 0xf6e7d2;
  // ---- Polyp (left): a cylinder with thickness, half cut, attached to a base.
  const polyp = new THREE.Group();
  const po = [[0.9, -1.8], [0.95, -0.5], [0.9, 1.3]];
  const pi = [[0.6, 1.3], [0.62, -0.5], [0.6, -1.5]];
  const pts = [...po, ...pi].map(([x, y]) => new THREE.Vector2(x, y));
  polyp.add(new THREE.Mesh(new THREE.LatheGeometry(pts, 48, Math.PI * 0.5, Math.PI), mat(THREE, epidermis)));
  polyp.add(new THREE.Mesh(new THREE.LatheGeometry(pi.map(([x, y]) => new THREE.Vector2(x - 0.04, y)), 48, Math.PI * 0.5, Math.PI), mat(THREE, gastrodermis)));
  const capShape = new THREE.Shape();
  capShape.moveTo(po[0][0], po[0][1]);
  for (const [x, y] of [...po.slice(1), ...pi]) capShape.lineTo(x, y);
  capShape.closePath();
  for (const side of [1, -1]) {
    const cap = new THREE.Mesh(new THREE.ShapeGeometry(capShape), mat(THREE, mesoglea));
    cap.rotation.y = side === 1 ? Math.PI / 2 : -Math.PI / 2;
    cap.scale.x = side;
    polyp.add(cap);
  }
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    polyp.add(tentacle(THREE, new THREE.Vector3(Math.cos(a) * 0.75, 1.3, Math.sin(a) * 0.75), new THREE.Vector3(Math.cos(a), 0.9, Math.sin(a)).normalize(), 1.3, epidermis));
  }
  const base = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.3, 0.18, 32), mat(THREE, 0xcfd6de));
  base.position.y = -1.9;
  polyp.add(base);
  polyp.position.set(-2.4, 0, 0);
  group.add(polyp);
  // ---- Medusa (right): a bell with thickness, half cut, mouth downward, tentacles hanging from the rim.
  const medusa = new THREE.Group();
  const bo = [];
  const bi = [];
  for (let i = 0; i <= 10; i++) {
    const t = i / 10;
    const a = t * Math.PI * 0.5;
    bo.push([Math.sin(a) * 1.7, Math.cos(a) * 1.0]);
  }
  for (let i = 10; i >= 1; i--) {
    const t = i / 10;
    const a = t * Math.PI * 0.5;
    bi.push([Math.sin(a) * 1.45, Math.cos(a) * 0.8 - 0.02]);
  }
  const bpts = [...bo, ...bi].map(([x, y]) => new THREE.Vector2(x, y));
  medusa.add(new THREE.Mesh(new THREE.LatheGeometry(bpts, 48, Math.PI * 0.5, Math.PI), mat(THREE, epidermis)));
  medusa.add(new THREE.Mesh(new THREE.LatheGeometry(bi.map(([x, y]) => new THREE.Vector2(x - 0.02, y)), 48, Math.PI * 0.5, Math.PI), mat(THREE, gastrodermis)));
  const bellCap = new THREE.Shape();
  bellCap.moveTo(bo[0][0], bo[0][1]);
  for (const [x, y] of [...bo.slice(1), ...bi]) bellCap.lineTo(x, y);
  bellCap.closePath();
  for (const side of [1, -1]) {
    const cap = new THREE.Mesh(new THREE.ShapeGeometry(bellCap), mat(THREE, mesoglea));
    cap.rotation.y = side === 1 ? Math.PI / 2 : -Math.PI / 2;
    cap.scale.x = side;
    medusa.add(cap);
  }
  // mouth tube (manubrium) hanging from the centre
  const mouth = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 0.9, 16, 1, true), mat(THREE, gastrodermis));
  mouth.position.y = -0.4;
  medusa.add(mouth);
  for (let i = 0; i < 12; i++) {
    const a = Math.PI * 0.5 + (i / 11) * Math.PI;
    if (i === 0 || i === 11) continue;
    medusa.add(tentacle(THREE, new THREE.Vector3(Math.cos(a) * 1.68, 0.05, Math.sin(a) * 1.68), new THREE.Vector3(Math.cos(a) * 0.15, -1, Math.sin(a) * 0.15).normalize(), 1.6, epidermis));
  }
  medusa.position.set(2.4, 0.4, 0);
  group.add(medusa);
  return {
    group,
    camera: { position: [0.3, 1.9, 9.8], lookAt: [0, -0.2, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "Polyp (sessile)", at: [-2.4, -2.1, 0], anchor: "below" },
      { text: "Medusa (free-swimming)", at: [2.4, -2.1, 0], anchor: "below" },
      { text: "Tentacles", at: [-3.4, 2.1, 0], anchor: "left" },
      { text: "Mouth", at: [-2.4, 1.3, 0.3], anchor: "right" },
      { text: "Epidermis", at: [-3.3, -0.3, 0.3], anchor: "left" },
      { text: "Mesoglea", at: [-2.4, -0.6, 0.9], anchor: "right" },
      { text: "Gastrodermis", at: [-2.4, 0.4, -0.56], anchor: "right" },
      { text: "Gastrovascular cavity", at: [2.4, 0.9, 0], anchor: "above" },
      { text: "Mouth (downward)", at: [2.4, -0.5, 0.2], anchor: "right" },
    ],
  };
}
