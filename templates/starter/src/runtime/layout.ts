import type { LegacyLayout } from "@windev-migration/ui";

/**
 * Display normalization of a generated layout (the generated files stay the record; this keeps hand-made or older
 * layouts working):
 * - WINDEV kind names the RAD kit spells differently ("Static" = "Caption", "Radio Button" = "RadioButton");
 * - date edits without the "Blocking validation" detail (not in the dossier extract) get "Yes", the only value the
 *   kit's WdDateEdit/WdDateTimeEdit accept. The designer value is not in the dossier: "Yes" is an assumption;
 *   record it as a U- item in the project.
 */
const KIND_ALIASES: Record<string, string> = { Static: "Caption", "Radio Button": "RadioButton", "List box": "List Box" };
export function normalizeLayout<T extends LegacyLayout>(layout: T): T {
  return {
    ...layout,
    controls: layout.controls.map((control) => {
      let next = KIND_ALIASES[control.kind] ? { ...control, kind: KIND_ALIASES[control.kind] } : control;
      if (next.kind === "Edit control" && next.input_type === "Date" && next.blocking_validation == null)
        next = { ...next, blocking_validation: "Yes" };
      return next;
    }),
  };
}

/** The key event fields Esc handling reads (a React KeyboardEvent on the window frame). */
export interface FrameKeyEvent {
  key: string;
  defaultPrevented: boolean;
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  currentTarget: { querySelector<E extends Element = Element>(selector: string): E | null };
  preventDefault(): void;
}

/** Abort-type buttons of a window (WINDEV button type "Abort": Esc). */
export function abortButtons(layout: LegacyLayout): string[] {
  return layout.controls
    .filter((control) => control.kind === "Button" && (control as { button_type?: string }).button_type === "Abort")
    .map((control) => control.path);
}

/**
 * Esc in a window = its Abort-type button: clicks it when it is drawn and enabled; when the window has an Abort button
 * nobody drew, the window closes as by its close box (the Closing event runs). No Abort button: nothing.
 * Keys a control already handled (defaultPrevented: open combo, calendar, table search) are left alone.
 */
export function escapeToAbort(event: FrameKeyEvent, layout: LegacyLayout, requestClose: () => unknown): "click" | "close" | "none" {
  if (event.key !== "Escape" || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return "none";
  const aborts = abortButtons(layout);
  if (aborts.length === 0) return "none";
  event.preventDefault();
  for (const path of aborts) {
    const button = event.currentTarget.querySelector<HTMLButtonElement>(`button[data-control-path="${path.replace(/["\\]/g, "\\$&")}"]`);
    if (button && !button.hidden && button.getClientRects().length > 0) {
      if (button.disabled) return "none";
      button.click();
      return "click";
    }
  }
  void requestClose();
  return "close";
}
