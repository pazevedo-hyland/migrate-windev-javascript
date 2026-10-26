import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  UiProvider, WdButton, WdFrame, MessageController, controlOf, createAssetResolver,
  createTableLayoutStore, createWindowGeometryStore, reconcileTableLayout,
  integerMaskDisplay, integerMaskEdit, integerMaskOf, decimalMaskDisplay, decimalMaskOf,
  dateEntryInitial, dateEntryChange, dateEntryResult, dateTimeEntryInitial, dateTimeEntryChange, dateTimeEntryResult,
  resourceModel, writeClipboardText, type LegacyColumn, type LegacyControl, type LegacyLayout,
} from "./index";

function memoryStorage() {
  const entries = new Map<string, string>();
  return { getItem: (key: string) => entries.get(key) ?? null, setItem: (key: string, value: string) => { entries.set(key, value); } };
}
const base: LegacyControl = { name: "EDT_Value", path: "sample/EDT_Value", kind: "Edit control", x: 10, y: 40, width: 100, height: 28 };
const layout: LegacyLayout = { window: { name: "sample", title: "Synthetic window", size: { width: 320, height: 200 } }, controls: [base] };
const column = (name: string, flags = {}): LegacyColumn => ({ name, path: `sample/TABLE/${name}`, title: name, width: 90, h_align: "Left", flags });

describe("portable UI contracts", () => {
  it("uses qualified identity and refuses ambiguous short names", () => {
    const duplicate = { ...base, path: "other/EDT_Value" };
    const repeated = { ...layout, controls: [base, duplicate] };
    expect(controlOf(repeated, duplicate.path)).toBe(duplicate);
    expect(() => controlOf(repeated, base.name)).toThrow(/unambiguous/);
    expect(() => controlOf(layout, "missing")).toThrow();
  });

  it("renders neutral window chrome without source layouts, skins or native APIs", () => {
    const markup = renderToStaticMarkup(createElement(WdFrame, { layout, instance: "neutral", onClose() {}, onMinimize() {}, onToggleMaximize() {}, children: "Content" }));
    expect(markup).toContain("Synthetic window");
    expect(markup).toContain('aria-label="Close"');
    expect(markup).toContain('data-testid="neutral__title"');
    expect(markup).not.toContain("url(");
  });

  it("keeps simultaneous provider labels and locales independent", () => {
    const button = { ...base, name: "BTN_Action", kind: "Button", caption: "&I" };
    const render = (locale: string, close: string) => renderToStaticMarkup(createElement(UiProvider,
      { config: { namespace: locale, locale, labels: { close } }, children: createElement(WdFrame,
        { layout, instance: locale, onClose() {}, onMinimize() {}, onToggleMaximize() {}, children: createElement(WdButton, { control: button }) }) }));
    const english = render("en", "Close A"), turkish = render("tr", "Close B");
    expect(english).toContain('data-wd-mnemonic="i"');
    expect(turkish).toContain('data-wd-mnemonic="ı"');
    expect(english).toContain('aria-label="Close A"');
    expect(turkish).toContain('aria-label="Close B"');
  });

  it("isolates geometry and column preferences between unrelated app namespaces", () => {
    const storage = memoryStorage(), one = createWindowGeometryStore(storage, "one"), two = createWindowGeometryStore(storage, "two");
    const geometry = { x: 4, y: 6, width: 320, height: 200, maximized: false };
    expect(one.save("same-window", geometry)).toBe(true);
    expect(two.load("same-window")).toBeNull();
    expect(one.load("same-window")).toEqual(geometry);
    const left = createTableLayoutStore(storage, "one"), right = createTableLayoutStore(storage, "two");
    const saved = { widths: { value: 120 }, order: ["value"], hidden: [] };
    expect(left.save("same-table", saved)).toBe(true);
    expect(right.load("same-table")).toBeNull();
    expect(left.load("same-table")).toEqual({ widths: { value: 120 }, order: ["value"] });
    expect(one.save("bad", { ...geometry, width: NaN })).toBe(false);
  });

  it("reconciles stale table settings without moving columns across fixed barriers or hiding everything", () => {
    const columns = [column("fixed", { "Fixed left": true }), column("a", { Movable: true }), column("b", { Movable: true }), column("end")];
    const paths = columns.map(item => item.path);
    const result = reconcileTableLayout({ order: [paths[3], paths[2], paths[0], paths[1]], widths: { [paths[1]]: 135, stale: 55 }, hidden: [...paths, "stale"] }, columns);
    expect(result.order).toEqual([paths[0], paths[2], paths[1], paths[3]]);
    expect(result.widths).toEqual({ [paths[1]]: 135 });
    expect(result.hidden).toEqual(paths.slice(0, -1));
  });

  it("queues awaited dialogs and keeps destructive dismissal on the safe result", async () => {
    const controller = new MessageController();
    const first = controller.open({ title: "Confirm", text: "Remove synthetic item?", type: 2, destructive: true });
    const second = controller.open({ title: "Later", text: "Queued", type: 0 });
    const pending = controller.getSnapshot()!;
    expect(pending.kind).toBe("message");
    expect(pending.model.focus).toBe(1);
    controller.finish(pending.id);
    await expect(first).resolves.toBe(7);
    expect(controller.getSnapshot()?.request.title).toBe("Later");
    controller.cancelAll();
    await expect(second).resolves.toBe(1);
    expect(controller.getSnapshot()).toBeNull();
    expect(() => resourceModel({ title: "Delete", text: "Confirm", buttons: [{ label: "Delete" }, { label: "Cancel" }], defaultIndex: 1, cancelIndex: 2, destructive: true })).toThrow(/safe index/);
  });

  it("retains exact integer and decimal input including oversized originals and leading zeroes", () => {
    const integer = integerMaskOf("999 999")!;
    expect(integerMaskDisplay(integer, "001234")).toBe("001 234");
    expect(integerMaskEdit(integer, "12", "12x")).toBeNull();
    expect(integerMaskEdit(integer, "1234567", "1234567")?.value).toBe("1234567");
    const wide = integerMaskOf("9999999999999999999")!;
    expect(integerMaskEdit(wide, "", "9007199254740993123")?.value).toBe("9007199254740993123");
    const decimal = decimalMaskOf("+999 999,99")!;
    expect(decimalMaskDisplay(decimal, "1234.56789")).toBe("1 234,56789");
  });

  it("preserves NULL/opaque dates and hidden datetime precision until deliberate valid edits", () => {
    expect(dateEntryResult(dateEntryInitial(null))).toEqual({ kind: "valid", value: null });
    expect(dateEntryResult(dateEntryInitial("opaque"))).toEqual({ kind: "valid", value: "opaque" });
    expect(dateEntryResult(dateEntryChange(dateEntryInitial("20240229"), "31/02/2024"))).toEqual({ kind: "invalid" });
    const draft = dateTimeEntryInitial("20240229120455123");
    expect(dateTimeEntryResult(dateTimeEntryChange(draft, "01/03/2024 13:05"))).toEqual({ kind: "valid", value: "20240301130555123" });
  });

  it("resolves only host-allowlisted assets and rejects missing states and unsafe URLs", () => {
    const resolver = createAssetResolver({ action: { source: "/assets/action.svg", states: ["/assets/normal.svg", "/assets/hover.svg"] } });
    expect(resolver.image("ACTION", 1)).toBe("/assets/hover.svg");
    expect(() => resolver.image("missing")).toThrow(/inventory/);
    expect(() => resolver.image("action", 2)).toThrow(/state/);
    expect(() => createAssetResolver({ action: { source: "https://example.invalid/asset.png" } })).toThrow(/same-origin/);
    expect(() => createAssetResolver({ action: { source: "../private.png" } })).toThrow(/same-origin/);
  });

  it("returns clipboard failure without a native host or browser clipboard", async () => {
    await expect(writeClipboardText("Synthetic")).resolves.toBe(false);
    await expect(writeClipboardText("Synthetic", { writeText: async () => { throw new Error("Unavailable"); } })).resolves.toBe(false);
  });
});
