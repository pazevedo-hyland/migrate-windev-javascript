import type { LegacyControl, LegacyLayout, SkinAssets } from "@windev-migration/ui";

export type PreviewLayout = LegacyLayout & { diagnostics: string[] };

const chromeNames = new Set([
  "RADTitle", "SCSystemButtons", "BTN_SYST_MINIMIZE", "BTN_Syst_Maximize",
  "BTN_SYST_FERMER", "BTN_Syst_Restore", "BTN_UMC",
]);
const renderedKinds = new Set(["Caption", "Button", "Edit control", "Check Box", "Combo Box", "RadioButton", "Table", "Shape"]);

function usableChromeGeometry(control: LegacyControl): boolean {
  return Number.isFinite(control.x) && Number.isFinite(control.y)
    && typeof control.width === "number" && Number.isFinite(control.width) && control.width > 0
    && typeof control.height === "number" && Number.isFinite(control.height) && control.height > 0;
}

/** A reversible display projection. Extraction metadata remains the source of record. */
export function preparePreviewLayout(layout: LegacyLayout, assets: SkinAssets): PreviewLayout {
  const preview = structuredClone(layout) as PreviewLayout;
  const diagnostics = Array.isArray(preview.diagnostics) ? [...preview.diagnostics] : [];
  preview.diagnostics = diagnostics;
  const configured = new Set(Object.keys(assets).map(name => name.toLowerCase()));
  const stripUnconfigured = (owner: string, target: { image?: string; background_image?: string | null }) => {
    for (const field of ["image", "background_image"] as const) {
      const name = target[field];
      if (typeof name === "string" && name !== "" && !configured.has(name.toLowerCase())) {
        delete target[field];
        diagnostics.push(`${owner}.${field}: unconfigured skin ${JSON.stringify(name)}; neutral preview`);
      }
    }
  };
  stripUnconfigured(preview.window.name, preview.window);
  preview.controls = preview.controls.filter(control => {
    const isChrome = chromeNames.has(control.name);
    if (isChrome && !usableChromeGeometry(control)) {
      diagnostics.push(`${control.path}: source chrome ${control.name} has incomplete or invalid geometry; neutral preview`);
      return false;
    }
    // Unknown kinds belong to host placeholders/adapters and retain all of their metadata.
    if (isChrome || renderedKinds.has(control.kind)) stripUnconfigured(control.path, control);
    return true;
  });
  return preview;
}
