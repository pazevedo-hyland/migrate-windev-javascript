import type { CSSProperties } from "react";
import { createAssetResolver, noSkinAssets, type SkinAssets } from "../../assets";

export interface LegacyColumn {
  name: string; path: string; title: string | null; width: number | null;
  h_align: string | null; flags?: Record<string, boolean> | null;
  parent?: string; input_type?: string | null; linked_item?: string | null; index?: number;
  metadata_unresolved?: boolean;
}

export interface LegacyControl {
  name: string; path: string; kind: string; x: number; y: number;
  width?: number | null; height?: number | null; caption?: string | null;
  caption_width?: number; visible?: boolean; state?: string;
  tab_order?: number | string; image?: string; background_image?: string;
  input_size?: number; input_type?: string; input_mask?: string;
  return_format?: string; calendar_button?: string; calculator_button?: string; blocking_validation?: string;
  h_align?: string; v_align?: string;
  flags?: Partial<Record<string, boolean>>;
  anchoring?: string;
  anchorRates?: { right?: number; bottom?: number; width?: number; height?: number };
  columns?: LegacyColumn[];
  table_options?: Record<string, string>;
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

export function controlBox(control: LegacyControl): CSSProperties {
  if (control.width == null || control.height == null) throw new Error(`Control geometry unresolved: ${control.path}`);
  return { left: control.x, top: control.y, width: control.width, height: control.height };
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
