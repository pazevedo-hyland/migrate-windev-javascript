import type { LegacyLayout } from "./layout";

export function dialogLayout(source: LegacyLayout, title: string): LegacyLayout {
  return { ...source, window: { ...source.window, title },
    controls: source.controls.map(control => control.name === "RADTitle" ? { ...control, caption: title } : control) };
}
