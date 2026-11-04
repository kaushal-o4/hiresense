import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { expressionFor, profileFor, storedQuality } from "./avatarStates";
import { buildRig, composeFace, VISEMES } from "./faceRig";
import { Blinker, Gaze, HeadMotion, Micro } from "./motion";

// 3D interviewer renderer. Model-agnostic: works with
//   * the bundled Microsoft Rocketbox characters (MIT, frontend/avatar-src/convert_rocketbox.py), and
//   * high-detail characters with ARKit-52 blendshapes, e.g. MetaHumans converted by
//     frontend/avatar-src/convert_metahuman.py (see frontend/avatar-src/METAHUMAN_GUIDE.md).
// `hdModelUrl` is tried first (unless quality is "performance" or `lite`); if it is missing or fails to load,
// `modelUrl` is used, so the interview never breaks because an optional asset is absent.
//
// Every frame: lip sync (from the audio actually playing) -> faceRig.composeFace (fixed layer priority:
// lips > speech motion > expression > eyes > idle) -> morph targets; motion.js drives gaze, blinks, head/body
// and micro-expressions. `mode` is the avatar state (voice/avatarStates.js); `interviewer` picks the personality.

export const AVATAR_URL = "/avatars/interviewer.glb";

// Rendering presets (names/labels: avatarStates.AVATAR_QUALITY). "balanced" is the default: soft shadows and
// skin shading at 60 fps (30 fps looked choppy in head and lip motion; the laptop's Intel GPU, which Chrome renders
// on, holds 60 with p95 18 ms). frameMs is a whole number of 60 Hz display frames, so frames are evenly spaced.
const QUALITY = {
  high: { pixelRatio: 2, antialias: true, shadows: 2048, skin: true, frameMs: 1000 / 60, anisotropy: 8 },
  balanced: { pixelRatio: 1.25, antialias: true, shadows: 1024, skin: true, frameMs: 1000 / 60, anisotropy: 4 },
  performance: { pixelRatio: 1, antialias: false, shadows: 0, skin: false, frameMs: 1000 / 30, anisotropy: 2 },
};
// The shadow map is redrawn every SHADOW_EVERY frames: the head moves a few millimetres in that time, which is not
// visible in a soft shadow, and it removes a whole extra render pass from most frames.
const SHADOW_EVERY = 3;
// Adaptive quality: when frames keep arriving late (measured over ADAPT_WINDOW_MS; the GPU may be shared with the
// local AI model) the frame rate drops to an even 30 fps first, then the resolution steps down, and finally shadows
// are turned off. Never steps back up mid-session.
const ADAPT_WINDOW_MS = 2500;
const ADAPT_SLOW = 1.4; // average frame gap > 1.4x the target = too slow
const MIN_PIXEL_RATIO = 0.75;

// Bone names across rigs (Rocketbox "Bip01_*", MetaHuman / UE5 skeleton, Mixamo-style).
const BONES = {
  head: ["Bip01_Head", "head", "Head"],
  neck: ["Bip01_Neck", "neck_02", "neck_01", "Neck"],
  spine: ["Bip01_Spine2", "spine_05", "spine_04", "Spine2"],
  eyeL: ["Bip01_LEye", "FACIAL_L_Eye", "LeftEye", "eye_l"],
  eyeR: ["Bip01_REye", "FACIAL_R_Eye", "RightEye", "eye_r"],
  lip: ["Bip01_MUpperLip", "Bip01_MJaw", "FACIAL_C_Jaw", "jaw"],
};

// Rocketbox meshes rest in an A-pose. These rotations (radians, on top of the rest pose) give a relaxed seated
// interviewer: upper arms down at the sides (local Y, mirrored) and slightly forward (local Z negative), elbows
// bent (forearm Z), forearms turned inward (forearm X, mirrored) so the hands rest loosely clasped at the waist.
// Checked from the front, side and 3/4 views (an earlier front-only tuning swung the arms behind the back).
const ARM_POSE = {
  "Bip01_L_UpperArm": [0, 0.78, -0.22], "Bip01_R_UpperArm": [0, -0.78, -0.22],
  "Bip01_L_Forearm": [0.65, 0, -1.0], "Bip01_R_Forearm": [-0.65, 0, -1.0],
};

// Per-interviewer lighting and set: a soft key light, a gentle fill, a rim light for separation, and a dim,
// defocused interview room behind (CSS, so it costs nothing to render). Colours are approximate Kelvin tints.
const LOOK = {
  aria: { // warm, low-key, intimate
    key: [0xffd2a6, 2.7, [-1.3, 1.9, 2.1]], fill: [0x9fb2d4, 0.32, [1.8, 0.9, 1.6]], rim: [0xffc58e, 1.5, [0.9, 2.2, -2.4]],
    hemi: 0.22, env: 0.32, exposure: 1.0,
    room: "radial-gradient(ellipse 60% 55% at 22% 30%, rgba(214,160,96,.30), transparent 70%), radial-gradient(ellipse 30% 40% at 82% 38%, rgba(255,196,120,.16), transparent 70%), radial-gradient(ellipse at 50% 40%, #3a2c20 0%, #1d1611 55%, #0c0907 100%)",
  },
  victor: { // neutral key, deep shadows, cool rim, a hint of red in the room
    key: [0xfff0e2, 2.5, [1.4, 1.8, 2.0]], fill: [0x8392ab, 0.22, [-1.8, 0.8, 1.5]], rim: [0xcfdcff, 1.8, [-1.0, 2.2, -2.4]],
    hemi: 0.16, env: 0.28, exposure: 1.0,
    room: "radial-gradient(ellipse 45% 50% at 86% 14%, rgba(150,22,34,.42), transparent 70%), radial-gradient(ellipse at 50% 42%, #2a2a31 0%, #15151a 55%, #08080a 100%)",
  },
  marcus: { // hard-edged, cool steel
    key: [0xf4f6ff, 2.4, [1.2, 2.0, 2.2]], fill: [0x8a98b0, 0.3, [-1.8, 0.9, 1.6]], rim: [0xe0e8ff, 1.5, [-0.8, 2.2, -2.4]],
    hemi: 0.2, env: 0.32, exposure: 1.0,
    room: "radial-gradient(ellipse 50% 40% at 18% 20%, rgba(150,170,200,.18), transparent 70%), radial-gradient(ellipse at 50% 42%, #2c333c 0%, #181d23 55%, #0b0e11 100%)",
  },
  elena: { // soft, bright, composed
    key: [0xfff1e4, 2.3, [-1.2, 1.9, 2.2]], fill: [0xd8d0f0, 0.55, [1.8, 0.9, 1.6]], rim: [0xffffff, 1.2, [0.8, 2.2, -2.4]],
    hemi: 0.35, env: 0.45, exposure: 1.02,
    room: "radial-gradient(ellipse 55% 50% at 78% 28%, rgba(220,205,240,.35), transparent 70%), radial-gradient(ellipse at 50% 40%, #6b6478 0%, #463f52 55%, #241f2b 100%)",
  },
};

// Skin: three.js has no true subsurface scattering, so light "wraps" past the shadow terminator with a warm red
// tint - the soft, blood-lit falloff that separates skin from plastic. Patched into the standard PBR lighting.
const LAMBERT = "reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );";
const SKIN_LIGHTS = THREE.ShaderChunk.lights_physical_pars_fragment.includes(LAMBERT)
  ? THREE.ShaderChunk.lights_physical_pars_fragment.replace(LAMBERT, `${LAMBERT}
	float hsWrap = saturate( ( dot( geometryNormal, directLight.direction ) + 0.5 ) / 1.5 );
	reflectedLight.directDiffuse += max( hsWrap - dotNL, 0.0 ) * vec3( 0.9, 0.3, 0.18 ) * directLight.color * BRDF_Lambert( material.diffuseColor );`)
  : null;

function skinMaterial(src, withScatter) {
  const m = new THREE.MeshPhysicalMaterial({
    name: src.name, map: src.map, normalMap: src.normalMap, roughnessMap: src.roughnessMap, aoMap: src.aoMap,
    color: src.color, roughness: Math.max(0.45, Math.min(0.6, src.roughness ?? 0.55)), metalness: 0,
    specularIntensity: 0.5, // skin reflects ~2.8% at normal incidence; full-strength specular looks oily
    sheen: 0.22, sheenRoughness: 0.85, sheenColor: new THREE.Color(0.95, 0.8, 0.75), // fine vellus hair at grazing angles
  });
  if (src.normalMap) m.normalScale.copy(src.normalScale);
  if (withScatter && SKIN_LIGHTS) {
    m.onBeforeCompile = (shader) => {
      shader.fragmentShader = shader.fragmentShader.replace("#include <lights_physical_pars_fragment>", SKIN_LIGHTS);
    };
    m.customProgramCacheKey = () => "hs-skin";
  }
  return m;
}

function upgradeMaterials(root, q, maxAniso) {
  let hasMouth = false;
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.frustumCulled = false;
    if (/teeth|tongue|mouth|saliva/i.test(o.name)) hasMouth = true;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const next = mats.map((m) => {
      const n = `${m.name} ${o.name}`;
      if (/teeth|tongue/i.test(n)) hasMouth = true;
      if (m.map) m.map.anisotropy = Math.min(q.anisotropy, maxAniso);
      if (/opacity|hair|lash|brow|fuzz|peach/i.test(n)) { // alpha-card hair, lashes, brows
        m.alphaTest = 0.4; m.transparent = false; m.depthWrite = true; m.side = THREE.DoubleSide;
        m.alphaToCoverage = q.antialias; // soft, anti-aliased strand edges instead of jagged cut-outs
        m.roughness = Math.max(m.roughness ?? 0.5, 0.45); m.metalness = 0;
        return m;
      }
      if (/cornea|eye(?!lash|brow)/i.test(n) && !/shell|occlusion/i.test(n)) { // wet eyes: crisp catch-lights
        m.roughness = 0.06; m.metalness = 0;
        return m;
      }
      if (/eyeshell|occlusion|cartilage/i.test(n)) return m;
      if (/head|face|skin/i.test(n)) return skinMaterial(m, q.skin);
      if (/body/i.test(n)) return skinMaterial(m, false); // Rocketbox bodies carry clothes in the same texture
      return m;
    });
    o.material = Array.isArray(o.material) ? next : next[0];
    o.castShadow = !!q.shadows;
    o.receiveShadow = !!q.shadows;
  });
  return hasMouth;
}

const smooth = (cur, target, rate, dt) => cur + (target - cur) * (1 - Math.exp(-rate * dt));
const tmpQ = new THREE.Quaternion(); // reused every frame (no per-frame garbage -> no GC pauses)
const tmpE = new THREE.Euler();
const findBone = (bones, key) => BONES[key].map((n) => bones[n]).find(Boolean) || null;

export default function Avatar3D({
  getVisemes, mode = "idle", interviewer = "aria", modelUrl = AVATAR_URL, hdModelUrl = null, quality = null,
  className = "", onFailed, lite = false, testHook = true, label = "AI interviewer",
}) {
  const host = useRef(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const whoRef = useRef(interviewer);
  whoRef.current = interviewer;
  const visRef = useRef(getVisemes); // read every frame, so a changed callback takes effect immediately
  visRef.current = getVisemes;
  const [status, setStatus] = useState("loading");
  const qName = lite ? "performance" : (QUALITY[quality] ? quality : storedQuality());

  useEffect(() => {
    const el = host.current;
    const q = QUALITY[qName];
    let disposed = false;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: q.antialias, alpha: true, powerPreference: lite ? "low-power" : "high-performance" });
    } catch {
      setStatus("failed");
      onFailed?.("WebGL is not available in this browser.");
      return undefined;
    }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let frameMs = lite ? 1000 / 20 : q.frameMs;
    const look = LOOK[whoRef.current] || LOOK.aria;
    let pixelRatio = Math.min(window.devicePixelRatio, q.pixelRatio);
    renderer.setPixelRatio(pixelRatio);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = look.exposure;
    if (q.shadows) {
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.shadowMap.autoUpdate = false; // redrawn every SHADOW_EVERY frames (see the loop)
    }
    el.appendChild(renderer.domElement);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = look.env;
    const camera = new THREE.PerspectiveCamera(24, 1, 0.05, 50);
    scene.add(new THREE.HemisphereLight(0xfff4ea, 0x1c222b, look.hemi));
    const light = ([color, intensity, pos]) => {
      const l = new THREE.DirectionalLight(color, intensity);
      l.position.set(...pos);
      scene.add(l);
      scene.add(l.target);
      return l;
    };
    const key = light(look.key);
    const fill = light(look.fill);
    const rim = light(look.rim);
    if (q.shadows) {
      key.castShadow = true;
      key.shadow.mapSize.set(q.shadows, q.shadows);
      key.shadow.bias = -0.0004;
      key.shadow.normalBias = 0.015;
      key.shadow.radius = 4;
    }

    const st = { rig: null, meshes: [], bones: {}, rest: {}, vis: {}, ex: {}, lastMode: null, visible: true,
      gaze: new Gaze(), blink: new Blinker(), motion: new HeadMotion(Math.floor(Math.random() * 1000)), micro: new Micro() };
    let loadedUrl = null;
    if (testHook) window.__avatar3d = { status: "loading", model: hdModelUrl && q !== QUALITY.performance ? hdModelUrl : modelUrl };

    const resize = () => {
      const w = el.clientWidth || 1;
      const h = el.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();
    // don't render while scrolled out of view
    const io = new IntersectionObserver(([e]) => { st.visible = e.isIntersecting; });
    io.observe(el);

    const onLoaded = (gltf, url) => {
      if (disposed) return;
      loadedUrl = url;
      const root = gltf.scene;
      scene.add(root);
      const hasMouth = upgradeMaterials(root, q, renderer.capabilities.getMaxAnisotropy());
      const morphNames = new Set();
      root.traverse((o) => {
        if (o.isBone) st.bones[o.name] = o;
        // glTF splits a model into one mesh per material; all of them share the blendshapes
        if (o.isMesh && o.morphTargetDictionary && Object.keys(o.morphTargetDictionary).length) {
          st.meshes.push(o);
          Object.keys(o.morphTargetDictionary).forEach((n) => morphNames.add(n));
        }
      });
      st.rig = buildRig([...morphNames]);
      const armRest = {};
      const poseArm = (name, x, y, z) => {
        const b = st.bones[name];
        if (!b) return false;
        armRest[name] = armRest[name] || b.quaternion.clone();
        b.quaternion.copy(armRest[name]).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z)));
        return true;
      };
      for (const [name, [x, y, z]] of Object.entries(ARM_POSE)) poseArm(name, x, y, z);
      for (const k of ["head", "neck", "spine", "eyeL", "eyeR"]) {
        const b = findBone(st.bones, k);
        if (b) { st[k] = b; st.rest[k] = b.quaternion.clone(); }
      }
      root.updateMatrixWorld(true);
      // Rocketbox has no inner mouth surface, so an open mouth would show the background through the head.
      // A dark cavity just behind the lips, attached to the head bone, covers that. Models with real teeth and a
      // tongue (e.g. MetaHumans) don't need it.
      const lip = findBone(st.bones, "lip");
      if (!hasMouth && lip && st.head) {
        const p = new THREE.Vector3();
        lip.getWorldPosition(p);
        const cavity = new THREE.Mesh(new THREE.SphereGeometry(0.024, 24, 16),
          new THREE.MeshBasicMaterial({ color: 0x2a0f12 }));
        cavity.scale.set(1.1, 0.95, 0.9);
        cavity.position.set(p.x, p.y - 0.012, p.z - 0.03);
        st.head.attach(cavity);
      }
      // head-and-shoulders framing, eyes near the upper third, camera slightly below eye level
      const head = new THREE.Vector3();
      (st.head || root).getWorldPosition(head);
      const eyes = new THREE.Vector3();
      if (st.eyeL) st.eyeL.getWorldPosition(eyes);
      else eyes.set(head.x, head.y + 0.08, head.z);
      const target = new THREE.Vector3(head.x, eyes.y - 0.11, head.z);
      camera.position.set(head.x, eyes.y - 0.04, head.z + 1.45);
      camera.lookAt(target);
      for (const l of [key, fill, rim]) { l.position.add(target); l.target.position.copy(target); }
      if (q.shadows) {
        const c = key.shadow.camera;
        c.left = -0.45; c.right = 0.45; c.top = 0.45; c.bottom = -0.45; c.near = 0.5; c.far = 6;
        c.updateProjectionMatrix();
      }
      setStatus("ready");
      if (!testHook) return;
      window.__avatar3d = { status: "ready", model: url, mode: () => modeRef.current, quality: qName,
        rig: st.rig.kind, morphs: morphNames.size, visemes: st.rig.visemeCount, arkit: st.rig.arkitCount,
        // test hooks (used by tests_e2e): current viseme weights, a pose helper, forced channel weights
        visemeWeights: () => ({ ...st.vis }), poseArm, force: (map) => { st.force = map; },
        adaptive: () => ({ fps: Math.round(1000 / frameMs), pixelRatio, shadows: renderer.shadowMap.enabled, steps: adapt.steps }),
        camera: (dy, dist) => { camera.position.set(head.x, eyes.y - 0.02 + dy, head.z + dist); camera.lookAt(target); },
        // orbit around the body (yaw in radians, 0 = front) to check the pose from the side
        orbit: (yaw, dy, dist) => {
          const c = new THREE.Vector3(head.x, eyes.y - 0.3 + dy, head.z);
          camera.position.set(c.x + Math.sin(yaw) * dist, c.y, c.z + Math.cos(yaw) * dist);
          camera.lookAt(c);
        } };
    };
    // the bundled models are meshopt-compressed with WebP textures (frontend/avatar-src/compress_avatars.py)
    const load = (url, fallback) => new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(url, (g) => onLoaded(g, url), undefined, (err) => {
      if (disposed) return;
      if (fallback) {
        console.info(`[avatar] ${url} unavailable, using ${fallback}`);
        load(fallback, null);
        return;
      }
      setStatus("failed");
      if (testHook) window.__avatar3d = { status: "failed", model: url, error: String(err?.message || err) };
      onFailed?.("The 3D interviewer could not be loaded.");
    });
    if (hdModelUrl && q !== QUALITY.performance) load(hdModelUrl, modelUrl);
    else load(modelUrl, null);

    const setMorph = (name, w) => {
      for (const m of st.meshes) {
        const i = m.morphTargetDictionary[name];
        if (i !== undefined) m.morphTargetInfluences[i] = w;
      }
    };
    const turn = (k, [x, y, z]) => {
      const b = st[k];
      if (b) b.quaternion.copy(st.rest[k]).multiply(tmpQ.setFromEuler(tmpE.set(x, y, z)));
    };

    // adaptive quality (see ADAPT_*): sum of frame gaps in the current window
    const adapt = { start: 0, frames: 0, gaps: 0, steps: 0 };
    const stepDown = () => {
      if (frameMs < 1000 / 30 - 1) frameMs = 1000 / 30;
      else if (pixelRatio > MIN_PIXEL_RATIO + 0.01) {
        pixelRatio = Math.max(MIN_PIXEL_RATIO, Math.round(pixelRatio * 0.8 * 100) / 100);
        renderer.setPixelRatio(pixelRatio);
        resize();
      } else if (renderer.shadowMap.enabled) {
        renderer.shadowMap.enabled = false;
        scene.traverse((o) => {
          if (!o.isMesh) return;
          o.castShadow = false;
          o.receiveShadow = false;
          (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { m.needsUpdate = true; });
        });
      } else return;
      adapt.steps += 1;
      console.info(`[avatar] frames too slow; lowered quality (${Math.round(1000 / frameMs)} fps, pixel ratio ${pixelRatio}, shadows ${renderer.shadowMap.enabled ? "on" : "off"})`);
    };

    let last = performance.now();
    let frameNo = 0;
    let raf;
    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      // Frames are capped at the preset rate (frameMs) to leave CPU/GPU time for the local speech and AI models. rAF
      // timestamps jitter by a few ms, so a frame that is due "almost now" is drawn now: a strict threshold skipped
      // it to the next display frame and made the spacing uneven (visible judder).
      if (now - last < frameMs - 4) return;
      if (document.hidden || !st.visible) { last = now; adapt.start = 0; return; } // hidden: don't burn CPU/GPU
      const gap = now - last;
      const dt = Math.min(0.05, gap / 1000);
      last = now;
      if (st.rig && !lite) {
        if (!adapt.start) adapt.start = now + 3000; // let shaders compile and the model settle first
        else if (now >= adapt.start) {
          adapt.frames += 1;
          adapt.gaps += gap;
          if (now - adapt.start >= ADAPT_WINDOW_MS) {
            if (adapt.gaps / adapt.frames > frameMs * ADAPT_SLOW) stepDown();
            adapt.start = now;
            adapt.frames = 0;
            adapt.gaps = 0;
          }
        }
      }
      const t = now / 1000;
      if (st.rig) {
        const m = modeRef.current;
        const prof = profileFor(whoRef.current);
        const ex = expressionFor(whoRef.current, m);
        const k = (reduced ? 0.25 : 1) * prof.motion; // head-motion scale (reduced-motion users get very little)
        if (m !== st.lastMode) {
          if (ex.nodOnEnter && !reduced) st.motion.nodOnce(); // acknowledge the answer with one nod
          st.lastMode = m;
        }
        // ---- 1. lip sync: the audio actually playing (null when silent -> mouth returns to rest), in any state
        const v = visRef.current?.() || null;
        const amp = v?.amp ?? 0;
        const talking = !!v;
        for (const id of VISEMES) {
          const target = v ? (v.weights[id] || 0) * (id === "sil" ? 1 : Math.min(1, 0.35 + amp * 0.75)) : 0;
          st.vis[id] = smooth(st.vis[id] || 0, target, 26, dt);
        }
        // ---- 3. expression targets, blended smoothly between states
        for (const [name, rate] of [["smile", 3], ["browUp", 5], ["browDown", 3], ["squint", 3], ["skeptic", 4],
          ["press", 4], ["lookUp", 4], ["lookSide", 4], ["tilt", 2], ["lean", 2.5]]) {
          st.ex[name] = smooth(st.ex[name] ?? 0, ex[name] || 0, rate, dt);
        }
        // ---- 4. eyes
        const gaze = st.gaze.update(t, dt, m, { talking, base: { x: st.ex.lookSide, y: st.ex.lookUp } });
        if (gaze.saccade > 0.15 && Math.random() < 0.5) st.blink.trigger(t);
        const blink = st.blink.update(t, prof.blinkEvery, { listening: m === "listening", speaking: talking });
        const micro = reduced ? {} : st.micro.update(t, dt, m, { amp, talking, warmth: prof.warmth ?? 0.5,
          expressiveness: prof.expressiveness ?? 1 });
        const { weights } = composeFace(st.rig, { visemes: st.vis, amp, talking, expr: st.ex, gaze, blink, micro });
        for (const [c, name] of Object.entries(st.rig.names)) setMorph(name, weights[c] || 0);
        if (!st.rig.has("eyeLookUpLeft") && st.eyeL) { // rigs without gaze shapes: rotate the eye bones
          turn("eyeL", [-gaze.y * 0.35, gaze.x * 0.45, 0]);
          turn("eyeR", [-gaze.y * 0.35, gaze.x * 0.45, 0]);
        }
        // ---- head, neck, breathing
        const hm = st.motion.update(t, dt, { amp, talking, scale: k, nodSize: prof.nodSize,
          nodRate: reduced ? 0 : ex.nodRate, lean: st.ex.lean });
        hm.head[2] += st.ex.tilt;
        turn("head", hm.head);
        turn("neck", hm.neck);
        turn("spine", reduced ? [hm.spine[0] * 0.3, 0, 0] : hm.spine);
        if (st.force) for (const [c, w] of Object.entries(st.force)) setMorph(st.rig.names[c] || c, w); // test hook only
      }
      if (renderer.shadowMap.enabled && frameNo % SHADOW_EVERY === 0) renderer.shadowMap.needsUpdate = true;
      frameNo += 1;
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      scene.traverse((o) => {
        o.geometry?.dispose?.();
        const mats = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
        mats.forEach((m) => { Object.values(m).forEach((x) => x?.isTexture && x.dispose()); m.dispose(); });
      });
      key.shadow?.map?.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      if (testHook && window.__avatar3d?.model === loadedUrl) window.__avatar3d = { status: "disposed", model: loadedUrl };
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelUrl, hdModelUrl, qName]);

  const look = LOOK[interviewer] || LOOK.aria;
  return (
    <div className={`relative overflow-hidden ${className}`} data-avatar-mode={mode} data-avatar-status={status}
      data-interviewer={interviewer} data-avatar-quality={qName} style={{ background: look.room }}>
      {/* defocused practical lights in the room behind (bokeh) */}
      <div className="pointer-events-none absolute inset-0 opacity-70" aria-hidden="true"
        style={{ background: "radial-gradient(circle at 12% 62%, rgba(255,214,160,.10) 0 3%, transparent 6%), radial-gradient(circle at 90% 70%, rgba(255,230,190,.08) 0 4%, transparent 8%), linear-gradient(0deg, rgba(0,0,0,.35) 0 18%, transparent 40%)", filter: "blur(8px)" }} />
      <div ref={host} className="absolute inset-0" role="img" aria-label={`${label}, ${mode}`} />
      {status === "loading" && <p className="absolute inset-x-0 bottom-1/2 text-center text-sm text-slate-600">Loading…</p>}
    </div>
  );
}
