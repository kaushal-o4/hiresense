import { describe, expect, it } from "vitest";
import { ARKIT, VISEME_ARKIT, VISEMES, buildRig, canonicalName, composeFace } from "./faceRig";

// morph names as they appear in the bundled Rocketbox GLBs (see avatar-src/convert_rocketbox.py)
const ROCKETBOX = [
  "AA_VI_00_Sil", "AA_VI_01_PP", "AA_VI_02_FF", "AA_VI_03_TH", "AA_VI_04_DD", "AA_VI_05_KK", "AA_VI_06_CH",
  "AA_VI_07_SS", "AA_VI_08_nn", "AA_VI_09_RR", "AA_VI_10_aa", "AA_VI_11_E", "AA_VI_12_I", "AA_VI_13_O", "AA_VI_14_U",
  "AK_09_EyeBlinkLeft", "AK_10_EyeBlinkRight", "AK_25_JawOpen", "AK_45_MouthSmileLeft", "AK_46_MouthSmileRight",
  "AK_01_BrowInnerUp",
];

describe("canonicalName", () => {
  it("maps Rocketbox, ARKit and common spellings onto one vocabulary", () => {
    expect(canonicalName("AA_VI_08_nn")).toBe("viseme:NN");
    expect(canonicalName("AK_09_EyeBlinkLeft")).toBe("eyeBlinkLeft");
    expect(canonicalName("eyeBlinkLeft")).toBe("eyeBlinkLeft");
    expect(canonicalName("blendShape1.jawOpen")).toBe("jawOpen");
    expect(canonicalName("EyeBlink_L")).toBe("eyeBlinkLeft");
    expect(canonicalName("mouthSmile_R")).toBe("mouthSmileRight");
    expect(canonicalName("viseme_aa")).toBe("viseme:AA");
    expect(canonicalName("mouthRollLower")).toBe("mouthRollLower"); // must not be read as "...Lowe" + "R"
    expect(canonicalName("Wrinkle_forehead")).toBeNull();
  });
});

describe("buildRig", () => {
  it("recognises the Rocketbox rig with all 15 visemes", () => {
    const rig = buildRig(ROCKETBOX);
    expect(rig.kind).toBe("rocketbox");
    expect(rig.visemeCount).toBe(15);
    expect(rig.hasVisemes).toBe(true);
    expect(rig.names["viseme:AA"]).toBe("AA_VI_10_aa");
    expect(rig.names.eyeBlinkLeft).toBe("AK_09_EyeBlinkLeft");
  });

  it("recognises an ARKit-52 rig (e.g. a baked MetaHuman) without visemes", () => {
    const rig = buildRig(ARKIT);
    expect(rig.kind).toBe("arkit");
    expect(rig.arkitCount).toBe(52);
    expect(rig.hasVisemes).toBe(false);
  });
});

describe("composeFace", () => {
  const rocketbox = buildRig(ROCKETBOX);
  const arkit = buildRig(ARKIT);

  it("closes the mouth completely when no audio is playing", () => {
    for (const rig of [rocketbox, arkit]) {
      const { weights, mouthActivity } = composeFace(rig, { visemes: {}, talking: false, expr: {} });
      expect(mouthActivity).toBe(0);
      expect(weights.jawOpen || 0).toBe(0);
      for (const v of VISEMES.filter((x) => x !== "sil")) expect(weights[`viseme:${v}`] || 0).toBe(0);
    }
  });

  it("spells visemes with ARKit shapes when the model has no viseme blendshapes", () => {
    const pp = composeFace(arkit, { visemes: { PP: 1 }, talking: true, amp: 0.5 }).weights;
    expect(pp.mouthPressLeft).toBeGreaterThan(0.4); // lips pressed for P/B/M
    expect(pp.jawOpen || 0).toBe(0);
    const aa = composeFace(arkit, { visemes: { AA: 1 }, talking: true, amp: 0.5 }).weights;
    expect(aa.jawOpen).toBeCloseTo(VISEME_ARKIT.AA.jawOpen, 5);
    const u = composeFace(arkit, { visemes: { U: 1 }, talking: true, amp: 0.5 }).weights;
    expect(u.mouthPucker).toBeGreaterThan(0.6); // rounded lips for OO
  });

  it("lets lip sync win over the expression layer on mouth channels", () => {
    const smiling = { smile: 0.8, press: 0.5 };
    const quiet = composeFace(arkit, { visemes: {}, talking: false, expr: smiling }).weights;
    const talking = composeFace(arkit, { visemes: { O: 1 }, talking: true, amp: 0.6, expr: smiling }).weights;
    expect(talking.mouthSmileLeft).toBeLessThan(quiet.mouthSmileLeft); // smile yields while lips are busy
    expect(talking.mouthPressLeft || 0).toBe(0); // no pressed lips while speaking
    expect(talking.mouthFunnel).toBeCloseTo(VISEME_ARKIT.O.mouthFunnel, 5); // lip shape untouched by expression
  });

  it("lets a blink close the eyes fully whatever the squint or gaze", () => {
    const w = composeFace(arkit, { blink: 1, expr: { squint: 0.4 }, gaze: { x: 0.2, y: -0.2 } }).weights;
    expect(w.eyeBlinkLeft).toBe(1);
    expect(w.eyeBlinkRight).toBe(1);
    expect(w.eyeSquintLeft || 0).toBe(0); // zero channels are omitted; the renderer treats missing as 0
  });

  it("lowers the upper lids a little when looking down, and keeps the smile asymmetric", () => {
    const w = composeFace(arkit, { gaze: { x: 0, y: -0.2 }, expr: { smile: 0.5 } }).weights;
    expect(w.eyeBlinkLeft).toBeGreaterThan(0);
    expect(w.mouthSmileRight).toBeLessThan(w.mouthSmileLeft);
  });

  it("keeps every weight within 0..1", () => {
    const w = composeFace(arkit, { visemes: { AA: 1, E: 1, SS: 1 }, talking: true, amp: 1,
      expr: { smile: 1, browUp: 1, browDown: 1, squint: 1, skeptic: 1, press: 1 }, gaze: { x: 1, y: 1 }, blink: 1,
      micro: { browUp: 1, smile: 1 } }).weights;
    for (const v of Object.values(w)) { expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThanOrEqual(1); }
  });
});
