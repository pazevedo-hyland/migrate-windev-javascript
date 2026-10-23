// WINDEV skin primitives driven by a generated layout (scripts/screen_layout.py → <WINDOW>.layout.json):
// positions, captions and images come from the legacy evidence, never retyped. data-testid = legacy name.
import type { ButtonHTMLAttributes, CSSProperties, KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import "./skin.css";

export type LegacyColumn = {
  name: string;
  title: string | null;
  width: number | null;
  h_align: string | null;
  flags?: Record<string, boolean> | null;
};
export type LegacyControl = {
  name: string;
  kind: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  caption?: string;
  visible?: boolean;
  image?: string;
  caption_width?: number;
  h_align?: string;
  columns?: LegacyColumn[];
};
export type LegacyLayout = {
  window: { name: string; title: string | null; size: { width: number; height: number } | null };
  controls: LegacyControl[];
};

export function controlsOf(layout: LegacyLayout) {
  const byName = new Map(layout.controls.map((c) => [c.name, c]));
  return (name: string): LegacyControl => {
    const control = byName.get(name);
    if (!control) throw new Error(`${name} is not in the ${layout.window.name} layout`);
    return control;
  };
}

/** The native window when running in Tauri; null in the browser preview and tests. */
async function appWindow() {
  if (!("__TAURI_INTERNALS__" in window)) return null;
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  return getCurrentWindow();
}

export const box = (c: LegacyControl): CSSProperties => ({ left: c.x, top: c.y, width: c.width, height: c.height });
const stem = (file?: string) => file?.replace(/\.[^.]+$/, "");

/** The window frame, title and system buttons of the skin template. Every window but the main one passes
 *  `onClose`: its close box then closes that window only, not the application's native window. */
export function WdWindow({
  layout,
  children,
  style,
  onClose,
}: {
  layout: LegacyLayout;
  children: ReactNode;
  style?: CSSProperties;
  onClose?: () => void;
}) {
  const control = controlsOf(layout);
  const size = layout.window.size ?? { width: 800, height: 600 };
  const title = control("RADTitle");
  // ADR-007: no native title bar; the skin's title is the drag area and its system buttons drive the window.
  // UNRESOLVED A-48d568 / A-ff0b05 / A-2b6ca2 (answer sheet): minimize, maximize/restore and close are the
  // template's usual actions, inferred.
  const sys = (
    name: string,
    background: string,
    action: (w: NonNullable<Awaited<ReturnType<typeof appWindow>>>) => Promise<void>,
    local?: () => void,
  ) => {
    const c = control(name);
    if (c.visible === false) return null;
    return (
      <button
        type="button"
        key={name}
        data-testid={name}
        className="wd-sysbtn"
        style={{ ...box(c), backgroundImage: `url("/skin/${background}.0.png")` }}
        onClick={() => {
          if (local) local();
          else appWindow().then((w) => w && action(w)).catch(() => undefined);
        }}
      >
        {c.image && <img src={`/skin/${stem(c.image)}.png`} alt="" />}
      </button>
    );
  };
  return (
    <div data-testid={layout.window.name} className="wd-window" style={{ width: size.width, height: size.height, ...style }}>
      <div className="wd-client" style={{ width: size.width, height: size.height }}>
        <div className="wd-titlebar" data-tauri-drag-region />
        <div data-testid="RADTitle" className="wd-title" style={box(title)} data-tauri-drag-region>
          {title.caption}
        </div>
        {sys("BTN_SYST_MINIMIZE", "MediaPlayer_Btn_Minimize_Anim", (w) => w.minimize())}
        {sys("BTN_Syst_Maximize", "MediaPlayer_Btn_Maximize_Anim", (w) => w.toggleMaximize())}
        {sys("BTN_SYST_FERMER", "MediaPlayer_Btn_Close_Anim", (w) => w.close(), onClose)}
        {children}
      </div>
    </div>
  );
}

type ButtonProps = { control: LegacyControl; label?: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>;

/** A skinned button: caption, then the 5-state icon on the right when the legacy button has one. */
export function WdButton({ control, label, style, className, ...rest }: ButtonProps) {
  const icon = stem(control.image);
  return (
    <button
      type="button"
      data-testid={control.name}
      className={`wd-btn${icon ? " with-icon" : ""}${className ? ` ${className}` : ""}`}
      style={{ ...box(control), ...style }}
      {...rest}
    >
      <span>{label ?? control.caption}</span>
      {icon && <img className="wd-icon" src={`/skin/${icon}.0.png`} alt="" />}
    </button>
  );
}

/** Caption drawn left of an edit control's box, inside its legacy width (WINDEV "Inside width"). */
export function captionSplit(control: LegacyControl) {
  const captionWidth = control.caption_width ?? 0;
  return {
    caption: captionWidth ? { left: control.x + 2, top: control.y, width: captionWidth - 2 } : null,
    field: { ...box(control), left: control.x + captionWidth, width: (control.width ?? 0) - captionWidth },
  };
}

type MessageProps = {
  title: string;
  icon: "info" | "error" | "question";
  lines: string[];
  buttons: { testid: string; label: string; onClick: () => void; autoFocus?: boolean }[];
  testid: string;
  onKeyDown?: (e: ReactKeyboardEvent) => void;
  role?: "dialog" | "alertdialog";
};

/** A WINDEV message box (Info, Error, YesNo/Dialog) drawn in the skin: framed window, icon, text, skinned buttons.
 *  It blocks the window below without dimming it, as WINDEV's modal boxes do. */
export function WdMessage({ title, icon, lines, buttons, testid, onKeyDown, role = "alertdialog" }: MessageProps) {
  const width = 360;
  const height = 120 + 18 * Math.max(0, lines.length - 1);
  return (
    <div className="wd-modal-layer">
      <div
        role={role}
        aria-modal="true"
        aria-label={lines[0]}
        data-testid={testid}
        className="wd-window wd-message"
        style={{ width, height }}
        onKeyDown={onKeyDown}
      >
        <div className="wd-client" style={{ width, height }}>
          <div className="wd-title" style={{ left: 9, top: 4, width: width - 20 }} data-tauri-drag-region>
            {title}
          </div>
          <span className={`wd-msg-icon ${icon}`} aria-hidden="true" />
          <div className="wd-msg-text">
            {lines.map((line, i) => (
              <p key={i} data-testid="DLG_line">
                {line}
              </p>
            ))}
          </div>
          <div className="wd-msg-buttons">
            {buttons.map((b) => (
              <button key={b.testid} type="button" data-testid={b.testid} className="wd-btn" autoFocus={b.autoFocus}
                onClick={b.onClick}>
                <span>{b.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
