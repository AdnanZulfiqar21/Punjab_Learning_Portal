// Original 3D model after Figure 1.9: a simple vase-shaped sponge cut open to show its wall and central cavity.
export const title = "General structure of a sponge";

function mat(THREE, color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.7, side: THREE.DoubleSide, ...opts });
}

export function build(THREE) {
  const group = new THREE.Group();
  // Wall profile (x = radius, y = height): outer surface up, inner surface down, so the lathe has thickness.
  const outer = [[0.9, -2.2], [1.25, -1.2], [1.35, 0], [1.2, 1.3], [1.0, 2.2]];
  const inner = [[0.72, 2.2], [0.85, 1.3], [0.95, 0], [0.85, -1.2], [0.5, -2.0]];
  const pts = [...outer, ...inner].map(([x, y]) => new THREE.Vector2(x, y));
  // Half the lathe (phiLength = PI) is drawn, so the wall and the spongocoel are visible.
  const wall = new THREE.Mesh(new THREE.LatheGeometry(pts, 64, Math.PI * 0.5, Math.PI), mat(THREE, 0xe4b98a));
  group.add(wall);
  // The cut faces of the wall, as thin flat caps, make the three layers readable: outer pinacocytes (dark), mesohyl (light),
  // inner choanocyte lining (teal).
  const capShape = new THREE.Shape();
  const prof = [...outer, ...inner];
  capShape.moveTo(prof[0][0], prof[0][1]);
  for (const [x, y] of prof.slice(1)) capShape.lineTo(x, y);
  capShape.closePath();
  for (const side of [1, -1]) {
    const cap = new THREE.Mesh(new THREE.ShapeGeometry(capShape), mat(THREE, 0xf3d9bd));
    cap.rotation.y = side === 1 ? Math.PI / 2 : -Math.PI / 2;
    cap.scale.x = side;
    group.add(cap);
  }
  // Pinacocyte skin: a slightly larger, very thin dark lathe outside.
  const skin = new THREE.Mesh(
    new THREE.LatheGeometry(outer.map(([x, y]) => new THREE.Vector2(x + 0.03, y)), 64, Math.PI * 0.5, Math.PI),
    mat(THREE, 0xb98559),
  );
  group.add(skin);
  // Choanocyte lining: a thin teal layer just inside the inner wall, dotted with collar cells.
  const cyan = mat(THREE, 0x0f7a62);
  group.add(
    new THREE.Mesh(
      new THREE.LatheGeometry(inner.map(([x, y]) => new THREE.Vector2(x - 0.03, y)), 64, Math.PI * 0.5, Math.PI),
      mat(THREE, 0x2f9a7e),
    ),
  );
  for (let i = 0; i < 9; i++) {
    const t = i / 8;
    const y = -1.75 + t * 3.5;
    const r = 0.86 - Math.abs(t - 0.5) * 0.18;
    for (let k = 1; k < 12; k++) {
      const a = Math.PI * 0.5 + (k / 12) * Math.PI + (i % 2) * 0.13;
      const cell = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 6), cyan);
      cell.position.set(Math.sin(a) * (r - 0.05), y, Math.cos(a) * (r - 0.05));
      group.add(cell);
    }
  }
  // Ostia: small dark pores through the outer wall.
  const pore = mat(THREE, 0x3b2a1e);
  for (let i = 0; i < 26; i++) {
    const a = Math.PI * 0.6 + (i % 6) * 0.3 + (i % 2) * 0.08;
    const y = -1.7 + Math.floor(i / 6) * 0.85;
    const r = 1.33 - Math.abs(y) * 0.06;
    const p = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 8), pore);
    p.position.set(Math.sin(a) * r, y, Math.cos(a) * r);
    group.add(p);
  }
  // Spicules: thin needles in the mesohyl.
  const spic = mat(THREE, 0xf8f8f8);
  for (let i = 0; i < 14; i++) {
    const a = Math.PI * 0.65 + (i % 7) * 0.25;
    const y = -1.5 + (i % 5) * 0.7;
    const n = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.45, 6), spic);
    n.position.set(Math.sin(a) * 1.1, y, Math.cos(a) * 1.1);
    n.rotation.z = 0.6 * (i % 3) - 0.6;
    group.add(n);
  }
  // Water flow arrows: in through the wall, up and out through the osculum.
  const arrow = (from, to, color) => {
    const dir = new THREE.Vector3().subVectors(to, from);
    const len = dir.length();
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, len * 0.7, 8), mat(THREE, color));
    shaft.position.copy(from).add(dir.clone().multiplyScalar(0.35));
    shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
    const head = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.3, 12), mat(THREE, color));
    head.position.copy(from).add(dir.clone().multiplyScalar(0.85));
    head.quaternion.copy(shaft.quaternion);
    group.add(shaft, head);
  };
  arrow(new THREE.Vector3(0.2, -0.8, 2.1), new THREE.Vector3(0.1, -0.7, 1.0), 0x1f6fb5);
  arrow(new THREE.Vector3(0.6, 0.4, 2.1), new THREE.Vector3(0.4, 0.5, 1.0), 0x1f6fb5);
  arrow(new THREE.Vector3(0, 0.8, 0), new THREE.Vector3(0, 3.0, 0), 0x1f6fb5);
  // Base
  const base = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.4, 0.2, 48), mat(THREE, 0xcfd6de));
  base.position.y = -2.3;
  group.add(base);
  return {
    group,
    camera: { position: [0.2, 1.6, 8.6], lookAt: [0, 0, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "Osculum (water out)", at: [0, 2.45, 0], anchor: "above" },
      { text: "Ostium (water in)", at: [0.3, -0.8, 1.95], anchor: "right" },
      { text: "Pinacocyte (outer layer)", at: [-1.36, 1.0, 0], anchor: "left" },
      { text: "Mesohyl with amoeboid cells", at: [-1.15, -0.2, 0], anchor: "left" },
      { text: "Spicule", at: [-0.78, -1.3, -0.78], anchor: "left" },
      { text: "Choanocytes (collar cells)", at: [0.55, -1.3, -0.6], anchor: "right" },
      { text: "Spongocoel", at: [0, 0.3, -0.4], anchor: "right" },
    ],
  };
}
