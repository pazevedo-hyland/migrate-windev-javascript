import type { CSSProperties } from "react";
import { createAssetResolver, noSkinAssets, type SkinAssets } from "../../assets";

export interface LegacyColumn {
  name: string; path: string; title: string | null; width: number | null;
  h_align: string | null; flags?: Record<string, boolean> | null;
  parent?: string; input_type?: string | null; linked_item?: string | null; index?: number;
  metadata_unresolved?: boolean;
}

/** A font as the legacy source stores it (a Windows LOGFONT): negative height = pixels. */
export interface LegacyFont {
  face: string; height: number; weight: number; points?: number;
  italic?: boolean; underline?: boolean; strikeout?: boolean;
  /** Text colour `#rrggbb`, when the source holds an explicit one. */
  colour?: string;
  /** How the text is aligned, as the font's own record says (`left`, `center`, `right`, `justified`; `top`, `center`, `bottom`). */
  h_align?: string; v_align?: string;
}
/** A frame of a control as the source stores it: border type code, colours `#rrggbb` (no background = none set). */
export interface LegacyFrame { type: number; border_colour: string; background?: string }
export interface LegacyControl {
  name: string; path: string; kind: string; x: number; y: number;
  width?: number | null; height?: number | null; caption?: string | null;
  caption_width?: number; visible?: boolean; state?: string;
  tab_order?: number | string; image?: string; background_image?: string;
  input_size?: number; input_type?: string; input_mask?: string;
  return_format?: string; calendar_button?: string; calculator_button?: string; blocking_validation?: string;
  h_align?: string; v_align?: string;
  flags?: Partial<Record<string, boolean>>;
  /** WINDEV plane (0 = every plane); a window shows one plane at a time. */
  plane?: number;
  anchoring?: string;
  anchorRates?: { right?: number; bottom?: number; width?: number; height?: number };
  columns?: LegacyColumn[];
  table_options?: Record<string, string>;
  /** The control's own font from the source; absent = the skin's default. */
  font?: LegacyFont;
  /** Every font of the control in source order (one per button state, caption then input area…). */
  fonts?: LegacyFont[];
  /** The skin style the control was created from, e.g. `170 AquaBlue.BTN_Ok`; absent = a custom style. */
  style?: string;
  /** The control's frames in source order; which part each one draws is not named. */
  frames?: LegacyFrame[];
}
export interface LegacyLayout {
  window: { name: string; title: string | null; size: { width: number; height: number } | null; background_image?: string | null; flags?: Record<string, boolean> };
  controls: LegacyControl[];
}

export function controlOf(layout: LegacyLayout, key: string): LegacyControl {
  const exact = layout.controls.find(control => control.path === key);
  if (exact) return exact;
  const matches = layout.controls.filter(control => control.name === key);
  if (matches.length !== 1) throw new Error(`Control needs an unambiguous qualified path: ${key}`);
  return matches[0];
}

/** CSS for a source font: face, pixel size, weight, style and colour. Nothing when the layout has none. */
export function fontStyle(font: LegacyFont | undefined): CSSProperties {
  if (!font) return {};
  const decoration = [font.underline && "underline", font.strikeout && "line-through"].filter(Boolean).join(" ");
  return {
    fontFamily: `"${font.face}", sans-serif`,
    ...(font.height < 0 ? { fontSize: -font.height } : {}),
    fontWeight: font.weight,
    ...(font.italic ? { fontStyle: "italic" } : {}),
    ...(decoration ? { textDecoration: decoration } : {}),
    ...(font.colour ? { color: font.colour } : {}),
  };
}

export function controlBox(control: LegacyControl): CSSProperties {
  if (control.width == null || control.height == null) throw new Error(`Control geometry unresolved: ${control.path}`);
  return { left: control.x, top: control.y, width: control.width, height: control.height, ...fontStyle(control.font) };
}

export function skinSourceImage(name: string, assets: SkinAssets = noSkinAssets): string {
  return createAssetResolver(assets).source(name);
}
export function skinImage(name: string, state = 0, assets: SkinAssets = noSkinAssets): string {
  return createAssetResolver(assets).image(name, state);
}
export function buttonSkin(control: LegacyControl, assets: SkinAssets = noSkinAssets): CSSProperties {
  return createAssetResolver(assets).button(control);
}
