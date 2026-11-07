import { describe, expect, it, vi } from "vitest";
import type { LegacyControl, LegacyLayout } from "@windev-migration/ui";
import { abortButtons, escapeToAbort, normalizeLayout, type FrameKeyEvent } from "./layout";
import { screens } from "../generated/screens";

const layout = (controls: Partial<LegacyControl>[]): LegacyLayout => ({
  window: { name: "WIN_T", title: "T", size: { width: 300, height: 200 } },
  controls: controls.map((c) => ({ name: c.path!, x: 0, y: 0, width: 80, height: 24, kind: "Button", ...c })) as LegacyControl[],
});

function keyEvent(key: string, found: Record<string, Partial<HTMLButtonElement> | undefined>, extra: Partial<FrameKeyEvent> = {}) {
  const event = {
    key,
    defaultPrevented: false,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    preventDefault: vi.fn(() => {
      event.defaultPrevented = true;
    }),
    currentTarget: {
      querySelector: (selector: string) => {
        const path = /data-control-path="(.*)"/.exec(selector)![1];
        const button = found[path];
        return button ? { hidden: false, disabled: false, getClientRects: () => [{}], click: vi.fn(), ...button } : null;
      },
    },
    ...extra,
  };
  return event as unknown as FrameKeyEvent & { preventDefault: ReturnType<typeof vi.fn> };
}

describe("normalizeLayout", () => {
  it("maps WINDEV kind names to RAD kinds and defaults the date edits' blocking validation", () => {
    const result = normalizeLayout(
      layout([
        { path: "STC_x", kind: "Static" },
        { path: "RADIO_x", kind: "Radio Button" },
        { path: "EDT_data", kind: "Edit control", input_type: "Date" },
        { path: "EDT_data2", kind: "Edit control", input_type: "Date", blocking_validation: "No" },
        { path: "EDT_text", kind: "Edit control", input_type: "Text" },
      ]),
    );
    expect(result.controls.map((c) => c.kind)).toEqual(["Caption", "RadioButton", "Edit control", "Edit control", "Edit control"]);
    expect(result.controls.map((c) => c.blocking_validation)).toEqual([undefined, undefined, "Yes", "No", undefined]);
  });

  it("generated layouts: complete geometry, RAD kind names, supercontainers", () => {
    for (const { layout: source } of screens) {
      for (const control of source.controls) {
        if (control.kind !== "control") {
          expect([control.path, control.width, control.height].map((v) => v == null)).toEqual([false, false, false]);
          for (const column of control.columns ?? []) expect([column.path, column.width == null]).toEqual([column.path, false]);
        }
        expect(["Static", "Radio Button"]).not.toContain(control.kind);
        if (/^(SC_\w+|Form)$/.test(control.name)) expect(control.kind).toBe("Supercontrol");
      }
    }
  });
});

describe("Esc = the Abort-type button", () => {
  const win = layout([
    { path: "BTN_Save", button_type: "Validate" } as Partial<LegacyControl>,
    { path: "BTN_Cancel", button_type: "Abort" } as Partial<LegacyControl>,
  ]);

  it("finds the Abort buttons", () => expect(abortButtons(win)).toEqual(["BTN_Cancel"]));

  it("clicks the drawn Abort button", () => {
    const click = vi.fn(),
      close = vi.fn();
    const event = keyEvent("Escape", { BTN_Cancel: { click } });
    expect(escapeToAbort(event, win, close)).toBe("click");
    expect(click).toHaveBeenCalledOnce();
    expect(close).not.toHaveBeenCalled();
    expect(event.preventDefault).toHaveBeenCalled();
  });

  it("closes through the Closing event when the Abort button is not drawn", () => {
    const close = vi.fn();
    expect(escapeToAbort(keyEvent("Escape", {}), win, close)).toBe("close");
    expect(close).toHaveBeenCalledOnce();
  });

  it("does nothing for other keys, handled keys, disabled buttons or windows without an Abort button", () => {
    const close = vi.fn(),
      click = vi.fn();
    expect(escapeToAbort(keyEvent("Enter", { BTN_Cancel: { click } }), win, close)).toBe("none");
    expect(escapeToAbort(keyEvent("Escape", { BTN_Cancel: { click } }, { defaultPrevented: true }), win, close)).toBe("none");
    expect(escapeToAbort(keyEvent("Escape", { BTN_Cancel: { click, disabled: true } }), win, close)).toBe("none");
    expect(escapeToAbort(keyEvent("Escape", {}), layout([{ path: "BTN_ok" }]), close)).toBe("none");
    expect(click).not.toHaveBeenCalled();
    expect(close).not.toHaveBeenCalled();
  });
});
