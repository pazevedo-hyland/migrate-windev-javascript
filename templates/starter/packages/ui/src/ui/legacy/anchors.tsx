import { createContext, useContext } from "react";
import type { LegacyControl } from "./layout";

export const FrameDeltaContext = createContext({ width: 0, height: 0 });

export function anchoredControl(control: LegacyControl, delta: { width: number; height: number }): LegacyControl {
  const words = (control.anchoring ?? "").toLowerCase().split(/[^a-z]+/);
  const flags = new Set(words.every(word => ["", "none", "and", "right", "bottom", "width", "height"].includes(word)) ? words : []);
  const stretchWidth = flags.has("width"), stretchHeight = flags.has("height");
  const rates = {
    right: flags.has("right") ? control.anchorRates?.right ?? (stretchWidth ? 0 : 100) : 0,
    bottom: flags.has("bottom") ? control.anchorRates?.bottom ?? (stretchHeight ? 0 : 100) : 0,
    width: stretchWidth ? control.anchorRates?.width ?? 100 : 0,
    height: stretchHeight ? control.anchorRates?.height ?? 100 : 0,
  };
  if (Object.values(rates).some(value => !Number.isFinite(value))) throw new Error(`Invalid anchor rate: ${control.path}`);
  return { ...control, x: control.x + delta.width * rates.right / 100, y: control.y + delta.height * rates.bottom / 100,
    width: control.width == null ? control.width : Math.max(0, control.width + delta.width * rates.width / 100),
    height: control.height == null ? control.height : Math.max(0, control.height + delta.height * rates.height / 100) };
}

export function useAnchoredControl(control: LegacyControl) {
  return anchoredControl(control, useContext(FrameDeltaContext));
}
