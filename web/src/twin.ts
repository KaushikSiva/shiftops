import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import URDFLoader, { type URDFRobot } from "urdf-loader";

export class FacilityTwin {
  private scene = new THREE.Scene();
  private renderer: THREE.WebGLRenderer;
  private camera: THREE.PerspectiveCamera;
  private robot: URDFRobot | null = null;
  private joints: string[] = [];
  private pose: number[] = [
    1,
    1,
    0.793,
    1,
    0,
    0,
    0,
    ...[-0.1, 0, 0, 0.3, -0.2, 0, -0.1, 0, 0, 0.3, -0.2, 0],
  ];
  private route: THREE.Group = new THREE.Group();
  private hazard: THREE.Group = new THREE.Group();
  private target = new THREE.Group();
  private controls: OrbitControls;
  private routeKey = "";
  private frame = 0;
  private lastRender = 0;
  private reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  constructor(
    private container: HTMLElement,
    facility: any,
  ) {
    this.scene.background = new THREE.Color("#ebece7");
    this.scene.fog = new THREE.Fog("#ebece7", 27, 60);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    container.appendChild(this.renderer.domElement);
    this.renderer.domElement.setAttribute(
      "aria-label",
      "Live 3D facility twin. Drag to orbit and scroll to zoom.",
    );
    this.camera = new THREE.PerspectiveCamera(36, 1, 0.1, 150);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(17, -12, 18);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(6.4, 4.5, 0);
    this.controls.enableDamping = !this.reduce;
    this.controls.maxPolarAngle = Math.PI * 0.48;
    this.controls.minDistance = 8;
    this.controls.maxDistance = 42;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x626b76, 2.7));
    const sun = new THREE.DirectionalLight(0xfff5df, 3);
    sun.position.set(-8, -5, 22);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, {
      left: -18,
      right: 18,
      top: 18,
      bottom: -18,
      near: 0.5,
      far: 60,
    });
    sun.shadow.bias = -0.0003;
    this.scene.add(sun);
    this.box(6.5, 5, -0.22, 14, 11, 0.4, "#d1d4cd");
    this.box(6.5, 5, -0.008, 13, 10, 0.05, "#f4f2ea");
    const grid = new THREE.GridHelper(13, 26, 0xdadcd5, 0xe4e5de);
    grid.rotation.x = Math.PI / 2;
    grid.position.set(6.5, 5, 0.021);
    this.scene.add(grid);
    this.box(6.5, 10.3, 0.3, 13.7, 0.13, 0.6, "#babfb7");
    this.box(-0.3, 5, 0.3, 0.13, 10.7, 0.6, "#babfb7");
    // Floor route markings, warehouse fixtures and mechanical units share backend geometry.
    for (let y = 0.8; y < 9; y += 0.7)
      this.box(6, y, 0.03, 0.06, 0.35, 0.015, "#d8c68c");
    for (const fixture of facility.fixtures) {
      const [x, y, w, d, h] = fixture.box;
      if (fixture.kind === "rack") {
        for (const a of [-1, 1])
          for (const b of [-1, 1])
            this.box(
              x + a * (w - 0.09),
              y + b * (d - 0.09),
              h / 2,
              0.12,
              0.12,
              h,
              "#39484b",
            );
        for (const z of [0.15, 0.95, 1.75]) {
          this.box(x, y, z, w * 2, d * 2, 0.1, "#777f77");
          for (const dx of [-0.48, 0.48])
            for (const dy of [-0.85, 0, 0.85])
              this.box(x + dx, y + dy, z + 0.28, 0.8, 0.65, 0.45, "#baaa89");
        }
      } else {
        this.box(x, y, h / 2, w * 2, d * 2, h, "#8c9c99");
        this.box(
          x,
          y - d - 0.018,
          h * 0.65,
          w * 1.6,
          0.04,
          h * 0.43,
          "#485a58",
        );
        for (let k = 0; k < 6; k++)
          this.box(
            x - w * 0.7 + k * w * 0.28,
            y - d - 0.045,
            h * 0.65,
            0.04,
            0.02,
            h * 0.35,
            "#a2b0a9",
          );
        this.box(
          x + w * 0.73,
          y - d - 0.05,
          h * 0.82,
          0.08,
          0.03,
          0.08,
          "#e8794d",
        );
      }
      this.label(fixture.name.toUpperCase(), x, y + d + 0.28, 0.04, 0.95);
    }
    this.label("LOADING / 01", 2, 0.1, 0.04, 1.2);
    this.label("MECHANICAL / 03", 10.5, 9.7, 0.65, 1.45);
    this.label("G1 DOCK", 1, 2, 0.04, 0.9);
    this.label("HARBOR WORKS", 6.3, -0.58, 0.07, 2.6);
    this.ring(1, 1, 0.6, "#566e65", 0.04);
    this.scene.add(this.hazard);
    this.scene.add(this.route);
    this.scene.add(this.target);
    const [hx, hy, hw, hd] = facility.blockage.box;
    const mat = new THREE.MeshStandardMaterial({
      color: "#dc8752",
      transparent: true,
      opacity: 0.65,
    });
    const block = new THREE.Mesh(
      new THREE.BoxGeometry(hw * 2, hd * 2, 0.22),
      mat,
    );
    block.position.set(hx, hy, 0.12);
    this.hazard.add(block);
    for (const x of [-hw, hw]) {
      const cone = new THREE.Mesh(
        new THREE.ConeGeometry(0.13, 0.4, 12),
        new THREE.MeshStandardMaterial({ color: "#ed713b" }),
      );
      cone.rotation.x = Math.PI / 2;
      cone.position.set(hx + x, hy, 0.3);
      this.hazard.add(cone);
    }
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this.animate();
    this.loadRobot().catch((e) => {
      container.dispatchEvent(
        new CustomEvent("twin-error", { detail: String(e) }),
      );
    });
  }
  private box(
    x: number,
    y: number,
    z: number,
    w: number,
    d: number,
    h: number,
    color: string,
  ) {
    const m = new THREE.Mesh(
      new THREE.BoxGeometry(w, d, h),
      new THREE.MeshStandardMaterial({ color, roughness: 0.8 }),
    );
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true;
    this.scene.add(m);
    return m;
  }
  private ring(
    x: number,
    y: number,
    r: number,
    color: string,
    z: number,
    group: THREE.Group | THREE.Scene = this.scene,
  ) {
    const m = new THREE.Mesh(
      new THREE.RingGeometry(r - 0.035, r, 60),
      new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }),
    );
    m.position.set(x, y, z);
    group.add(m);
  }
  private label(text: string, x: number, y: number, z: number, width: number) {
    const c = document.createElement("canvas");
    c.width = 768;
    c.height = 80;
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = "#5c6865";
    ctx.font = "500 34px monospace";
    ctx.textAlign = "center";
    ctx.fillText(text, 384, 52);
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(width, width / 9.6),
      new THREE.MeshBasicMaterial({
        map: new THREE.CanvasTexture(c),
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    m.position.set(x, y, z);
    this.scene.add(m);
  }
  private async loadRobot() {
    const manager = new THREE.LoadingManager();
    const loaded = new Promise<void>((resolve, reject) => {
      manager.onLoad = () => resolve();
      manager.onError = (url) =>
        reject(new Error("Robot asset unavailable: " + url));
    });
    void loaded.catch(() => {});
    const loader = new URDFLoader(manager);
    loader.parseCollision = false;
    const [robot, resp] = await Promise.all([
      loader.loadAsync("/assets/g1/g1_12dof.urdf"),
      fetch("/assets/g1/joints.json"),
    ]);
    if (!resp.ok) throw Error("Missing joint mapping");
    this.joints = await resp.json();
    await loaded;
    robot.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.castShadow = o.receiveShadow = true;
        const m = o.material as THREE.MeshPhongMaterial;
        o.material = new THREE.MeshStandardMaterial({
          color: m.color,
          metalness: 0.28,
          roughness: 0.4,
        });
      }
    });
    this.robot = robot;
    this.scene.add(robot);
    this.setPose(this.pose, true);
  }
  private setPose(p: number[], snap = false) {
    if (!this.robot) return;
    const a = snap || this.reduce ? 1 : 0.3;
    this.robot.position.lerp(new THREE.Vector3(p[0], p[1], p[2]), a);
    this.robot.quaternion.slerp(
      new THREE.Quaternion(p[4], p[5], p[6], p[3]),
      a,
    );
    this.joints.forEach((n, i) => this.robot!.setJointValue(n, p[i + 7]));
  }
  update(m: any) {
    this.pose = m?.pose || this.pose;
    this.hazard.visible = m ? m.blocked : true;
    const key = JSON.stringify(m?.route || []);
    if (key !== this.routeKey) {
      this.routeKey = key;
      this.clear(this.route);
      this.clear(this.target);
      const points = (m?.route || []).map(
        (p: number[]) => new THREE.Vector3(p[0], p[1], 0.07),
      );
      if (points.length > 1) {
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(points),
          new THREE.LineDashedMaterial({
            color: "#e5663c",
            dashSize: 0.18,
            gapSize: 0.12,
          }),
        );
        line.computeLineDistances();
        this.route.add(line);
        for (const p of points)
          this.ring(p.x, p.y, 0.1, "#e5663c", 0.08, this.route);
        const end = points.at(-1)!;
        this.ring(end.x, end.y, 0.48, "#e5663c", 0.09, this.target);
      }
    }
  }
  private clear(group: THREE.Group) {
    for (const child of [...group.children]) {
      group.remove(child);
      const c = child as THREE.Mesh;
      c.geometry?.dispose();
      if (c.material && !Array.isArray(c.material)) c.material.dispose();
    }
  }
  resetCamera() {
    this.camera.position.set(17, -12, 18);
    this.controls.target.set(6.4, 4.5, 0);
  }
  focusRobot() {
    this.controls.target.set(this.pose[0], this.pose[1], 0.8);
    this.camera.position.set(this.pose[0] + 5, this.pose[1] - 6, 5);
  }
  private resize() {
    const w = this.container.clientWidth,
      h = this.container.clientHeight;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.fov = w / h < 1 ? 50 : 36;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }
  private animate = () => {
    this.frame = requestAnimationFrame(this.animate);
    if (this.container.offsetParent === null) return;
    const now = performance.now();
    if (now - this.lastRender < 33) return;
    this.lastRender = now;
    this.setPose(this.pose);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };
}
