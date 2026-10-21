// Original 3D model after Figure 11.4: sp3 hybridised methane (top) and ethane (bottom). Each carbon's four sp3
// orbitals point to the corners of a tetrahedron, 109.5 degrees apart; the shaded lobes show the sigma bonds they
// form, sp3-s with hydrogen and sp3-sp3 between the two carbons of ethane. Bond lengths to scale (C-H 1.09, C-C 1.54).
export const title = "sp3 hybridised methane and ethane";

export function build(THREE) {
  const group = new THREE.Group();
  const UP = new THREE.Vector3(0, 1, 0);
  const carbonMat = new THREE.MeshStandardMaterial({ color: 0x374151, roughness: 0.45 });
  const hydrogenMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, roughness: 0.4 });
  const stickMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.6 });
  const chLobe = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.5, transparent: true, opacity: 0.38, depthWrite: false });
  const ccLobe = new THREE.MeshStandardMaterial({ color: 0x7c3aed, roughness: 0.5, transparent: true, opacity: 0.42, depthWrite: false });

  function atom(pos, carbon) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(carbon ? 0.3 : 0.2, 32, 16), carbon ? carbonMat : hydrogenMat);
    m.position.copy(pos);
    group.add(m);
  }
  function bond(a, b, lobeMat) {
    const dir = new THREE.Vector3().subVectors(b, a);
    const len = dir.length();
    dir.normalize();
    const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
    const stick = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, len, 12), stickMat);
    stick.position.copy(mid);
    stick.quaternion.setFromUnitVectors(UP, dir);
    group.add(stick);
    const lobe = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), lobeMat);
    lobe.scale.set(0.24, len * 0.55, 0.24);
    lobe.position.copy(mid);
    lobe.quaternion.setFromUnitVectors(UP, dir);
    group.add(lobe);
  }
  // Tetrahedral directions: one straight along `axis`, three at 109.5 degrees from it, spread round by `twist`.
  function tetra(axis, twist) {
    const a = axis.clone().normalize();
    const p = Math.abs(a.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    const u = new THREE.Vector3().crossVectors(a, p).normalize();
    const v = new THREE.Vector3().crossVectors(a, u).normalize();
    const out = [];
    for (let k = 0; k < 3; k++) {
      const t = twist + (k * 2 * Math.PI) / 3;
      out.push(a.clone().multiplyScalar(-1 / 3).addScaledVector(u, (Math.sqrt(8) / 3) * Math.cos(t)).addScaledVector(v, (Math.sqrt(8) / 3) * Math.sin(t)));
    }
    return out;
  }

  // Methane, centred above.
  const CH = 1.09;
  const m0 = new THREE.Vector3(0, 1.55, 0);
  atom(m0, true);
  const mDirs = [UP.clone(), ...tetra(UP, Math.PI / 2)];
  const mH = mDirs.map((d) => m0.clone().addScaledVector(d, CH));
  for (const h of mH) {
    atom(h, false);
    bond(m0, h, chLobe);
  }
  // Angle arc between the upward bond and one of the others.
  const d1 = mDirs[1].clone().normalize();
  const arc = new THREE.Mesh(
    new THREE.TorusGeometry(0.5, 0.018, 8, 48, Math.acos(-1 / 3)),
    new THREE.MeshStandardMaterial({ color: 0xd7322f, roughness: 0.4 }),
  );
  // Torus arcs start on +x and turn towards +y: map +x onto d1 and +y onto the part of UP at right angles to d1.
  const toUp = UP.clone().addScaledVector(d1, -UP.dot(d1)).normalize();
  const basis = new THREE.Matrix4().makeBasis(d1, toUp, new THREE.Vector3().crossVectors(d1, toUp));
  arc.quaternion.setFromRotationMatrix(basis);
  arc.position.copy(m0);
  group.add(arc);

  // Ethane, below, C-C along x, staggered hydrogens.
  const CC = 1.54;
  const c1 = new THREE.Vector3(-CC / 2, -1.45, 0);
  const c2 = new THREE.Vector3(CC / 2, -1.45, 0);
  atom(c1, true);
  atom(c2, true);
  bond(c1, c2, ccLobe);
  for (const [c, axis, twist] of [[c1, new THREE.Vector3(1, 0, 0), 0], [c2, new THREE.Vector3(-1, 0, 0), Math.PI / 3]]) {
    for (const d of tetra(axis, twist)) {
      const h = c.clone().addScaledVector(d, CH);
      atom(h, false);
      bond(c, h, chLobe);
    }
  }
  return {
    group,
    camera: { position: [0, 0.9, 8.6], lookAt: [0, 0.05, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "Methane CH4: carbon is sp3", at: [0, 1.55, 0], anchor: "left" },
      { text: "Bond angle 109.5 degrees", at: [0.25, 1.95, 0], anchor: "right" },
      { text: "C-H sigma bond (sp3-s overlap)", at: [0, 2.15, 0], anchor: "above" },
      { text: "Ethane C2H6: C-C sigma bond (sp3-sp3)", at: [0, -1.45, 0], anchor: "below" },
      { text: "Six C-H sigma bonds", at: [CC / 2 + 0.25, -1.45 + 0.55, 0.2], anchor: "right" },
    ],
  };
}
