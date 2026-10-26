import { describe, expect, it } from "vitest";
import type { LegacyControl, LegacyLayout } from "@windev-migration/ui";
import { preparePreviewLayout } from "./preview";

function control(name: string, overrides: Partial<LegacyControl> = {}): LegacyControl {
  return { name, path: `SAMPLE/${name}`, kind: "Button", x: 10, y: 40, width: 90, height: 28,
    flags: { Visible: true, "TAB Key": true }, anchoring: "Right", ...overrides };
}
function sample(controls: LegacyControl[]): LegacyLayout & { diagnostics: string[]; unknown: string[] } {
  return { window: { name: "SAMPLE", title: "Synthetic", size: { width: 420, height: 300 }, background_image: "source-frame.png", flags: { Resizable: true } },
    controls, diagnostics: ["existing extraction diagnostic"], unknown: ["retained source question"] };
}

describe("neutral preview projection", () => {
  it("deep-clones without modifying source geometry, flags, identities or diagnostics", () => {
    const source = sample([control("BTN_Action", { image: "source-icon.png", columns: [{ name: "COL_Value", path: "SAMPLE/TABLE/COL_Value", title: "Value", width: 80, h_align: "Left", flags: { Visible: true } }] })]);
    const original = structuredClone(source), preview = preparePreviewLayout(source, {});
    expect(source).toEqual(original);
    expect(preview).not.toBe(source);
    expect(preview.controls[0]).not.toBe(source.controls[0]);
    expect(preview.controls[0].flags).toEqual(source.controls[0].flags);
    expect(preview.controls[0].path).toBe(source.controls[0].path);
    expect(preview.controls[0].x).toBe(10);
    expect(preview.controls[0].columns).toEqual(source.controls[0].columns);
    preview.controls[0].columns![0].flags!.Visible = false;
    expect(source.controls[0].columns![0].flags!.Visible).toBe(true);
    expect(preview.diagnostics[0]).toBe("existing extraction diagnostic");
    expect((preview as typeof source).unknown).toEqual(source.unknown);
  });

  it("retains explicitly configured assets case-insensitively without validating their URLs", () => {
    const source = sample([control("BTN_Action", { image: "Action.PNG", background_image: "button.png" })]);
    const preview = preparePreviewLayout(source, {
      "SOURCE-FRAME.PNG": { source: "/assets/frame.png" },
      "action.png": { source: "host-validates-this-value" },
      "BUTTON.PNG": { source: "/assets/button.png" },
    });
    expect(preview.window.background_image).toBe("source-frame.png");
    expect(preview.controls[0].image).toBe("Action.PNG");
    expect(preview.controls[0].background_image).toBe("button.png");
    expect(preview.diagnostics).toEqual(source.diagnostics);
  });

  it("drops only unconfigured asset fields and records each exact reference for neutral preview", () => {
    const source = sample([control("BTN_Action", { image: "icon.png", background_image: "button.png", caption: "Keep caption" })]);
    const preview = preparePreviewLayout(source, { "icon.png": { source: "/assets/icon.png" } });
    expect(preview.window).not.toHaveProperty("background_image");
    expect(preview.controls[0].image).toBe("icon.png");
    expect(preview.controls[0]).not.toHaveProperty("background_image");
    expect(preview.controls[0].caption).toBe("Keep caption");
    expect(preview.diagnostics).toEqual([
      "existing extraction diagnostic",
      'SAMPLE.background_image: unconfigured skin "source-frame.png"; neutral preview',
      'SAMPLE/BTN_Action.background_image: unconfigured skin "button.png"; neutral preview',
    ]);
  });

  it("strips unusable exact title/group/action chrome while retaining usable exact controls", () => {
    const source = sample([
      control("RADTitle", { kind: "Caption", width: undefined }),
      control("SCSystemButtons", { kind: "Super control", height: null }),
      control("BTN_SYST_FERMER", { x: NaN }),
      control("BTN_Syst_Maximize", { height: 0 }),
      control("BTN_Syst_Restore", { width: Infinity }),
      control("BTN_SYST_MINIMIZE", { x: 350, y: 4, width: 24, height: 22 }),
      control("BTN_UMC", { y: Infinity }),
      control("BTN_SystemLikeName", { width: null }),
    ]);
    const preview = preparePreviewLayout(source, {});
    expect(preview.controls.map(item => item.name)).toEqual(["BTN_SYST_MINIMIZE", "BTN_SystemLikeName"]);
    expect(preview.controls[0]).toEqual(source.controls[5]);
    for (const name of ["RADTitle", "SCSystemButtons", "BTN_SYST_FERMER", "BTN_Syst_Maximize", "BTN_Syst_Restore", "BTN_UMC"])
      expect(preview.diagnostics).toContain(`SAMPLE/${name}: source chrome ${name} has incomplete or invalid geometry; neutral preview`);
  });

  it("leaves unknown control kinds and incomplete content geometry for host placeholders", () => {
    const unknown = control("CUSTOM_Widget", { kind: "Unknown widget", image: "opaque-source.png", width: null });
    const incomplete = control("EDT_Value", { kind: "Edit control", height: undefined });
    const preview = preparePreviewLayout(sample([unknown, incomplete]), {});
    expect(preview.controls[0]).toEqual(unknown);
    expect(preview.controls[1]).toEqual(incomplete);
    expect(preview.diagnostics.some(text => text.includes("CUSTOM_Widget"))).toBe(false);
  });
});
