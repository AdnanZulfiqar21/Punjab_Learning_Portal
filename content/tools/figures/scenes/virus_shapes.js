// Original 3D model after Figure 1.30: the five basic shapes of viruses.
export const title = "Basic shapes of viruses";

function mat(THREE, color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.55, flatShading: true, ...opts });
}

function icosa(THREE, r, color) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.IcosahedronGeometry(r, 0), mat(THREE, color)));
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(r, 0)), new THREE.LineBasicMaterial({ color: 0x0b4a3b }));
  g.add(edges);
  return g;
}

export function build(THREE) {
  const group = new THREE.Group();
  const teal = 0x3fa58d;
  const dark = 0x0f7a62;
  // 1. Helical: protein units coiled round a rod.
  const helical = new THREE.Group();
  for (let i = 0; i < 70; i++) {
    const a = i * 0.55;
    const y = -1.4 + i * 0.04;
    const b = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 8), mat(THREE, i % 2 ? teal : dark));
    b.position.set(Math.cos(a) * 0.42, y, Math.sin(a) * 0.42);
    helical.add(b);
  }
  const core = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 2.9, 12), mat(THREE, 0xc0392b));
  helical.add(core);
  helical.position.set(-5.2, 0, 0);
  group.add(helical);
  // 2. Icosahedral: a bare twenty-faced capsid.
  const ico = icosa(THREE, 0.9, teal);
  ico.position.set(-2.6, 0, 0);
  group.add(ico);
  // 3. Complex: a bacteriophage with an icosahedral head, a tail sheath, a base plate and fibres.
  const phage = new THREE.Group();
  const headG = icosa(THREE, 0.7, teal);
  headG.position.y = 0.9;
  phage.add(headG);
  const sheath = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.2, 1.4, 12), mat(THREE, dark));
  sheath.position.y = -0.25;
  phage.add(sheath);
  const plate = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.12, 6), mat(THREE, dark));
  plate.position.y = -1.0;
  phage.add(plate);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const fibre = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.9, 6), mat(THREE, dark));
    fibre.position.set(Math.cos(a) * 0.55, -1.3, Math.sin(a) * 0.55);
    fibre.rotation.z = Math.cos(a) * 0.7;
    fibre.rotation.x = -Math.sin(a) * 0.7;
    phage.add(fibre);
  }
  phage.position.set(0, 0, 0);
  group.add(phage);
  // 4. Enveloped: a capsid inside a translucent lipid envelope studded with spikes.
  const env = new THREE.Group();
  const inner = icosa(THREE, 0.55, teal);
  env.add(inner);
  const envelope = new THREE.Mesh(new THREE.SphereGeometry(0.95, 32, 24), new THREE.MeshStandardMaterial({ color: 0xf2c58d, transparent: true, opacity: 0.45, roughness: 0.4 }));
  env.add(envelope);
  for (let i = 0; i < 40; i++) {
    const phi = Math.acos(1 - 2 * ((i + 0.5) / 40));
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
    const dir = new THREE.Vector3(Math.sin(phi) * Math.cos(theta), Math.cos(phi), Math.sin(phi) * Math.sin(theta));
    const spike = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.3, 6), mat(THREE, 0xb26a00));
    spike.position.copy(dir.clone().multiplyScalar(1.07));
    spike.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    env.add(spike);
    const knob = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 6), mat(THREE, 0xb26a00));
    knob.position.copy(dir.clone().multiplyScalar(1.24));
    env.add(knob);
  }
  env.position.set(2.7, 0, 0);
  group.add(env);
  // 5. Non-enveloped (naked): the capsid alone, slightly smaller.
  const naked = icosa(THREE, 0.8, dark);
  naked.position.set(5.3, 0, 0);
  group.add(naked);
  return {
    group,
    camera: { position: [0.3, 1.6, 15.2], lookAt: [0.3, -0.1, 0], fov: 38 },
    turntableAxis: "y",
    labels: [
      { text: "Helical", at: [-5.2, -1.7, 0], anchor: "below" },
      { text: "Icosahedral", at: [-2.6, -1.7, 0], anchor: "below" },
      { text: "Complex (bacteriophage)", at: [0, -1.9, 0], anchor: "below" },
      { text: "Enveloped", at: [2.7, -1.7, 0], anchor: "below" },
      { text: "Non-enveloped (naked)", at: [5.3, -1.7, 0], anchor: "below" },
      { text: "Nucleic acid", at: [-5.2, 1.55, 0], anchor: "above" },
      { text: "Lipid envelope with spikes", at: [2.7, 1.5, 0], anchor: "above" },
      { text: "Tail fibres", at: [0.6, -1.3, 0], anchor: "right" },
    ],
  };
}
