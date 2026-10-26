import type { LegacyControl, LegacyLayout } from "./layout";

function control(name: string, kind: string, x: number, y: number, width: number, height: number, caption = ""): LegacyControl {
  return { name, path: `starter-dialog/${name}`, kind, x, y, width, height, caption };
}

/** Original starter geometry. These are target defaults, not extracted WINDEV layouts. */
export const messageLayout: LegacyLayout = {
  window: { name: "starter-message", title: "Message", size: { width: 420, height: 160 },
    flags: { "Title bar": true, "Minimize icon": false, "Maximize icon": false, Resizable: false } },
  controls: [
    control("RADTitle", "Caption", 10, 5, 310, 22),
    control("LIB_INFO", "Caption", 64, 45, 330, 45),
    ...["ICON_INFORMATION", "ICON_ERREUR", "ICON_QUESTION"].map(name => control(name, "Image", 18, 48, 30, 30)),
    ...["BTN_OK", "BTN_OUI", "BTN_NON", "BTN_ANNULER"].map(name => control(name, "Button", 170, 118, 88, 28)),
    { ...control("BTN_Copier_caché", "Button", 0, 0, 1, 1), visible: false },
  ],
};

export const resourceLayout: LegacyLayout = {
  window: { name: "starter-resource", title: "Prompt", size: { width: 440, height: 184 },
    flags: { "Title bar": true, "Minimize icon": false, "Maximize icon": false, Resizable: false } },
  controls: [
    control("RADTitle", "Caption", 10, 5, 330, 22),
    control("LIB_INFO", "Caption", 64, 45, 350, 48),
    control("ICONE", "Image", 18, 48, 30, 30),
    control("BTN_1", "Button", 176, 142, 88, 28),
    control("SAI_1", "Edit control", 64, 96, 320, 28),
    control("INT_1", "Check Box", 64, 96, 320, 28),
  ],
};
