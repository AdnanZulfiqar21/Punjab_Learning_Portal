// Original 3D model after Figure 1.4: the four basic bacterial forms.
export const title = "The four basic forms of bacteria";

function mat(THREE, color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.05 });
}

export function build(THREE) {
  const group = new THREE.Group();
  const teal = 0x0f7a62;
  const soft = 0x3fa58d;
  // coccus: sphere
  const coccus = new THREE.Mesh(new THREE.SphereGeometry(0.75, 48, 32), mat(THREE, teal));
  coccus.position.set(-4.8, 0, 0);
  group.add(coccus);
  // bacillus: capsule (a rod with rounded ends)
  const bacillus = new THREE.Mesh(new THREE.CapsuleGeometry(0.5, 1.6, 12, 32), mat(THREE, soft));
  bacillus.position.set(-1.6, 0, 0);
  bacillus.rotation.z = Math.PI / 2 - 0.35;
  group.add(bacillus);
  // vibrio: a curved rod along an arc
  const arc = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.8, -0.6, 0),
    new THREE.Vector3(-0.3, 0.3, 0),
    new THREE.Vector3(0.5, 0.65, 0),
    new THREE.Vector3(1.0, 0.45, 0),
  ]);
  const vibrio = new THREE.Mesh(new THREE.TubeGeometry(arc, 48, 0.4, 24, false), mat(THREE, teal));
  vibrio.position.set(1.6, 0, 0);
  group.add(vibrio);
  for (const t of [0, 1]) {
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.4, 24, 16), mat(THREE, teal));
    cap.position.copy(arc.getPoint(t)).add(new THREE.Vector3(1.6, 0, 0));
    group.add(cap);
  }
  // spirillum: a helix
  class Helix extends THREE.Curve {
    getPoint(t, target = new THREE.Vector3()) {
      const turns = 3;
      const a = t * Math.PI * 2 * turns;
      return target.set(t * 2.6 - 1.3, Math.cos(a) * 0.38, Math.sin(a) * 0.38);
    }
  }
  const spirillum = new THREE.Mesh(new THREE.TubeGeometry(new Helix(), 160, 0.17, 16, false), mat(THREE, soft));
  spirillum.position.set(4.8, 0, 0);
  group.add(spirillum);
  // a thin shelf under the cells gives a sense of scale and ground
  const shelf = new THREE.Mesh(new THREE.BoxGeometry(13.5, 0.05, 2.6), new THREE.MeshStandardMaterial({ color: 0xeef1f5, roughness: 1 }));
  shelf.position.set(0, -1.25, 0);
  group.add(shelf);
  return {
    group,
    camera: { position: [0, 2.4, 14.6], lookAt: [0, -0.2, 0], fov: 36 },
    turntableAxis: "y",
    labels: [
      { text: "Coccus (spherical)", at: [-4.8, -0.8, 0], anchor: "below" },
      { text: "Bacillus (rod-shaped)", at: [-1.6, -0.8, 0], anchor: "below" },
      { text: "Vibrio (comma-shaped)", at: [1.6, -0.8, 0], anchor: "below" },
      { text: "Spirillum (spiral-shaped)", at: [4.8, -0.8, 0], anchor: "below" },
    ],
  };
}
