import type { ComponentProps, ReactNode } from "react";
import type { LegacyLayout, WdRadBinding, WdTable } from "@windev-migration/ui";

export interface ScreenDefinition {
  id: string;
  layout: LegacyLayout;
  source: string;
}
export type ScreenRow = Record<string, unknown>;
export type TableBinding = Omit<ComponentProps<typeof WdTable<ScreenRow>>, "control"> & { name: string };
export interface ScreenModel {
  bindings: readonly WdRadBinding[];
  tables?: readonly TableBinding[];
  status?: ReactNode;
  /** Extra content drawn inside the window (controls the RAD kit has no kind for: agendas, images, internal windows). */
  extra?: ReactNode;
  /** Control paths drawn by `extra` (or deliberately not drawn, e.g. runtime-hidden): not reported as unbound. */
  handled?: ReadonlySet<string>;
  /** Designer flags the dossier extract missed (e.g. Password), merged into the layout: cite the U- item in the adapter. */
  flags?: Readonly<Record<string, Readonly<Record<string, boolean>>>>;
  /**
   * The window's Closing event for a close the user asks for: the frame close box, and Esc when the window's Abort
   * button has no binding. Resolve false to keep the window open (ReturnToCapture). `window.close()` does not run it.
   */
  onClosing?: () => Promise<boolean> | boolean;
  /**
   * Height of the window's menu bar, drawn by `extra` at the top of the client area. WINDEV control coordinates are
   * relative to the client area below the menu bar, so the layout's controls are drawn this much lower (checked against
   * the running legacy app: the controls start under the menu bar).
   */
  menuBarHeight?: number;
  /** MyWindow..Title at runtime (undefined: the layout's title). */
  title?: string;
}

/** `window.open({ name, child: true }, …)` = OpenChild: the child closes with the window that opened it. */
export interface OpenTarget {
  name: string;
  child?: boolean;
}

/**
 * The legacy window's runtime contract (record the pattern in the project's docs/porting.md):
 * - `params`: the arguments of Open(WIN_X, p1, p2…), in order;
 * - `close(value)`: Close() with ..ReturnedValue = value (undefined when the user closes the window);
 * - `open(name, ...params)`: Open() of another window, awaited like the blocking WLanguage call;
 *   `open({ name, child: true }, ...params)`: OpenChild (not awaited by the caller; closed with this window);
 * - `minimize()` / `maximize()`: WinSize(MyWindow, …MinSize/MaxSize) or ..WindowState = Minimized/Maximized.
 */
export interface WindowContext {
  name: string;
  params: readonly unknown[];
  close: (returned?: unknown) => void;
  open: <T = unknown>(target: string | OpenTarget, ...params: unknown[]) => Promise<T | undefined>;
  minimize: () => void;
  maximize: () => void;
}

/** Hooks and business operations are handwritten; generated files contain structure only. */
export type ScreenAdapter = (layout: LegacyLayout, window: WindowContext) => ScreenModel;
