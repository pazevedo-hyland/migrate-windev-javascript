import type { CSSProperties } from "react";

/** A host supplies authorized image URLs explicitly; no images ship with this package. */
export interface SkinAsset { source: string; states?: readonly string[] }
export type SkinAssets = Readonly<Record<string, SkinAsset>>;
export const noSkinAssets: SkinAssets = Object.freeze({});

function checkedUrl(url: string): string {
  // Relative/same-origin files only. Deliberate host-controlled allowlisting precedes rendering.
  if (typeof url !== "string" || !url || /[\\\u0000-\u0020"'<>]/.test(url) || /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(url)
    || url.split(/[/?#]/).includes("..")) throw new Error("Skin assets require a safe same-origin URL");
  return url;
}

export function createAssetResolver(inventory: SkinAssets = noSkinAssets) {
  const assets = new Map<string, SkinAsset>();
  for (const [name, asset] of Object.entries(inventory)) {
    const key = name.toLowerCase();
    if (!key || assets.has(key)) throw new Error("Skin asset names must be unique, ignoring case");
    if (!asset || typeof asset.source !== "string" || (asset.states !== undefined && (!Array.isArray(asset.states) || !asset.states.length)))
      throw new Error("Invalid skin asset inventory");
    assets.set(key, { source: checkedUrl(asset.source), ...(asset.states ? { states: asset.states.map(checkedUrl) } : {}) });
  }
  const get = (name: string) => {
    const asset = assets.get(name.toLowerCase());
    if (!asset) throw new Error(`Skin image absent from checked inventory: ${name}`);
    return asset;
  };
  return {
    source(name: string): string { return get(name).source; },
    image(name: string, state = 0): string {
      if (!Number.isInteger(state) || state < 0) throw new Error("Invalid skin state index");
      const asset = get(name);
      if (!asset.states) return asset.source;
      if (state >= asset.states.length) throw new Error(`Undeclared skin state: ${name}/${state}`);
      return asset.states[state];
    },
    button(control: { image?: string; background_image?: string }): CSSProperties {
      const result: Record<string, string> = {};
      for (const [prefix, name] of [["background", control.background_image], ["icon", control.image]] as const) {
        if (!name) continue;
        const asset = get(name), count = asset.states?.length ?? 1;
        for (let state = 0; state < 5; state++) {
          const index = count === 1 ? 0 : count === 2 ? [0, 1, 1, 0, 0][state] : state;
          if (asset.states && index >= count) throw new Error(`Undeclared skin state: ${name}/${state}`);
          result[`--wd-${prefix}-${state}`] = `url("${asset.states?.[index] ?? asset.source}")`;
        }
      }
      return result as CSSProperties;
    },
  };
}
