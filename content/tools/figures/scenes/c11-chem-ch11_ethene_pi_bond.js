// Original 3D model after Figure 11.9: bonding in ethene. Each carbon is sp2; the sp2 orbitals form the C-C sigma
// bond (purple) along the axis and four C-H sigma bonds (orange), all in one flat plane at about 120 degrees. The
// unhybridised 2p orbitals stand at right angles to that plane and overlap sideways, above and below it, to form the
// pi bond (green). Bond lengths to scale (C=C 1.34, C-H 1.09).
export const title = "Sigma and pi bonds in ethene";

export function build(THREE) {
  const group = new THREE.Group();
  const UP = new THREE.Vector3(0, 1, 0);
  const carbonMat = new THREE.MeshStandardMaterial({ color: 0x374151, roughness: 0.45 });
  const hydrogenMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, roughness: 0.4 });
  const stickMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.6 });
  const chLobe = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.5, transparent: true, opacity: 0.38, depthWrite: false });
  const ccLobe = new THREE.MeshStandardMaterial({ color: 0x7c3aed, roughness: 0.5, transparent: true, opacity: 0.45, depthWrite: false });
  const pLobe = new THREE.MeshStandardMaterial({ color: 0x16a34a, roughness: 0.5, transparent: true, opacity: 0.3, depthWrite: false });
  const piCloud = new THREE.MeshStandardMaterial({ color: 0x15803d, roughness: 0.5, transparent: true, opacity: 0.4, depthWrite: false });

  function atom(pos, carbon) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(carbon ? 0.27 : 0.18, 32, 16), carbon ? carbonMat : hydrogenMat);
    m.position.copy(pos);
    group.add(m);
  }
  function bond(a, b, lobeMat) {
    const dir = new THREE.Vector3().subVectors(b, a);
    const len = dir.length();
    dir.normalize();
    const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
    const stick = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, len, 12), stickMat);
    stick.position.copy(mid);
    stick.quaternion.setFromUnitVectors(UP, dir);
    group.add(stick);
    const lobe = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), lobeMat);
    lobe.scale.set(0.22, len * 0.55, 0.22);
    lobe.position.copy(mid);
    lobe.quaternion.setFromUnitVectors(UP, dir);
    group.add(lobe);
  }

  // The molecular plane is horizontal (x-z); the 2p orbitals point along y.
  const CC = 1.34;
  const CH = 1.09;
  const c1 = new THREE.Vector3(-CC / 2, 0, 0);
  const c2 = new THREE.Vector3(CC / 2, 0, 0);
  atom(c1, true);
  atom(c2, true);
  bond(c1, c2, ccLobe);
  for (const [c, sx] of [[c1, -1], [c2, 1]]) {
    for (const sz of [-1, 1]) {
      const h = c.clone().add(new THREE.Vector3(sx * CH * Math.cos(Math.PI / 3), 0, sz * CH * Math.sin(Math.PI / 3)));
      atom(h, false);
      bond(c, h, chLobe);
    }
    // Unhybridised 2p orbital on this carbon: one lobe above the plane, one below.
    for (const sy of [-1, 1]) {
      const lobe = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), pLobe);
      lobe.scale.set(0.3, 0.55, 0.3);
      lobe.position.copy(c).add(new THREE.Vector3(0, sy * 0.6, 0));
      group.add(lobe);
    }
  }
  // Sideways overlap of the two 2p orbitals: the pi bond, above and below the plane.
  for (const sy of [-1, 1]) {
    const cloud = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 20), piCloud);
    cloud.scale.set(1.05, 0.3, 0.34);
    cloud.position.set(0, sy * 0.68, 0);
    group.add(cloud);
  }
  // A faint square showing the plane of the six atoms.
  const plane = new THREE.Mesh(
    new THREE.PlaneGeometry(3.6, 2.6),
    new THREE.MeshStandardMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false }),
  );
  plane.rotation.x = -Math.PI / 2;
  group.add(plane);
  return {
    group,
    camera: { position: [0, 2.3, 5.6], lookAt: [0, -0.05, 0], fov: 40 },
    turntableAxis: "y",
    labels: [
      { text: "pi bond: sideways overlap of 2p orbitals (above)", at: [0, 0.9, 0], anchor: "above" },
      { text: "pi bond (below the plane)", at: [0.4, -0.85, 0], anchor: "below" },
      { text: "C-C sigma bond (sp2-sp2)", at: [0.2, 0, 0], anchor: "right" },
      { text: "C-H sigma bond (sp2-s)", at: [-CC / 2 - CH * 0.5, 0, CH * 0.866], anchor: "left" },
      { text: "All six atoms in one plane", at: [1.6, 0, -1.1], anchor: "right" },
    ],
  };
}
