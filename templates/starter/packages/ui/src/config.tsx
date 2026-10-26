import { createContext, useContext, useMemo, type ReactNode } from "react";
import { createAssetResolver, noSkinAssets, type SkinAssets } from "./assets";
import type { WindowGeometryStore } from "./application/window-geometry";
import type { TableLayoutStore } from "./application/table-layout";
import { createWindowGeometryStore } from "./infrastructure/window-geometry";
import { createTableLayoutStore } from "./infrastructure/table-layout";

export const defaultLabels = {
  minimize: "Minimize", maximize: "Maximize/restore", close: "Close",
  showPassword: "Show password", hidePassword: "Hide password", calendar: "Calendar",
  openWindows: "Open windows", minimized: "minimized", resizeWindow: "Resize window",
  columns: "Columns", resetColumns: "Reset", search: "Search",
  calculator: "Calculator", value: "Value", apply: "Apply", cancel: "Cancel",
  ok: "OK", yes: "Yes", no: "No",
};
export type UiLabels = typeof defaultLabels;
export interface UiConfig {
  /** Use a distinct stable namespace for each application. */
  namespace?: string;
  locale?: string;
  labels?: Partial<UiLabels>;
  assets?: SkinAssets;
  geometryStore?: WindowGeometryStore;
  tableLayoutStore?: TableLayoutStore;
  playSound?: (type: number) => void | Promise<void>;
}
export interface ResolvedUiConfig {
  namespace: string; locale: string; labels: UiLabels; assets: SkinAssets;
  geometryStore: WindowGeometryStore; tableLayoutStore: TableLayoutStore;
  playSound: (type: number) => void | Promise<void>;
}

export function resolveUiConfig(config: UiConfig = {}, parent?: ResolvedUiConfig): ResolvedUiConfig {
  const namespace = config.namespace ?? parent?.namespace ?? "windev-migration";
  if (!namespace.trim() || /[\u0000-\u001f]/.test(namespace)) throw new Error("UI storage namespace is required");
  const locale = config.locale ?? parent?.locale ?? "en";
  // Reject an invalid locale at configuration time instead of during a key event.
  "I".toLocaleLowerCase(locale);
  const assets = config.assets ?? parent?.assets ?? noSkinAssets;
  createAssetResolver(assets);
  return { namespace, locale, assets, labels: { ...defaultLabels, ...parent?.labels, ...config.labels },
    geometryStore: config.geometryStore ?? (parent?.namespace === namespace ? parent.geometryStore : createWindowGeometryStore(undefined, namespace)),
    tableLayoutStore: config.tableLayoutStore ?? (parent?.namespace === namespace ? parent.tableLayoutStore : createTableLayoutStore(undefined, namespace)),
    playSound: config.playSound ?? parent?.playSound ?? (() => undefined) };
}

const UiContext = createContext<ResolvedUiConfig>(resolveUiConfig());

export function UiProvider({ config, children }: { config?: UiConfig; children: ReactNode }) {
  const parent = useContext(UiContext);
  const value = useMemo(() => resolveUiConfig(config, parent), [config, parent]);
  return <UiContext.Provider key={value.namespace} value={value}>{children}</UiContext.Provider>;
}
export function useUiConfig(): ResolvedUiConfig { return useContext(UiContext); }
