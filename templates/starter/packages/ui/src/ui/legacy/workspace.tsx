import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { WdFrame } from "./wd";
import { WindowInteraction } from "./window-interaction";
import type { LegacyLayout } from "./layout";
import type { WindowGeometryStore } from "../../application/window-geometry";
import { useUiConfig } from "../../config";
import { dialogTabStops } from "./dialog-keyboard";

export interface WindowSpec { layout: LegacyLayout; content: ReactNode; key?: string; onClose?: () => void }
interface WindowEntry extends WindowSpec { id: string; x: number; y: number; width: number; height: number; z: number; minimized: boolean; maximized: boolean }
type OpenWindow = (spec: WindowSpec) => void;
const WorkspaceContext = createContext<OpenWindow | null>(null);
const WorkspaceCloseContext = createContext<(() => void) | null>(null);

export function useWorkspaceClose(override?: () => void) {

  const close = useContext(WorkspaceCloseContext);
  if (override) return override;
  if (!close) throw new Error("Workspace instance is required");
  return close;
}

function saveGeometry(store: WindowGeometryStore, entry: WindowEntry) {
  if (entry.layout.window.flags?.["Save position"] !== true) return;
  store.save(entry.layout.window.name, { x: entry.x, y: entry.y, width: entry.width, height: entry.height, maximized: entry.maximized });
}

export function useWorkspace() {
  const open = useContext(WorkspaceContext);
  if (!open) throw new Error("WdWorkspace is required");
  return { open };
}

export function WdWorkspace({ children, geometryStore: storeOverride }: { children: ReactNode; geometryStore?: WindowGeometryStore }) {
  const config = useUiConfig(), geometryStore = storeOverride ?? config.geometryStore;
  const [windows, setWindows] = useState<WindowEntry[]>([]);
  const [extent, setExtent] = useState({ width: 0, height: 0 });
  const [focusRequest, requestFocus] = useState(0);
  const canvas = useRef<HTMLDivElement>(null), launcher = useRef<HTMLDivElement>(null), sequence = useRef(0), stack = useRef(0);
  const roots = useRef(new Map<string, HTMLDivElement>()), focused = useRef(new Map<string, HTMLElement>());
  const active = windows.filter(entry => !entry.minimized).reduce<WindowEntry | null>((top, entry) => !top || entry.z > top.z ? entry : top, null);
  const activeId = active?.id;
  useEffect(() => {
    const saveOpen = () => [...windows].sort((a, b) => a.z - b.z).forEach(entry => saveGeometry(geometryStore, entry));
    window.addEventListener("pagehide", saveOpen);
    return () => window.removeEventListener("pagehide", saveOpen);
  }, [windows, geometryStore]);
  useEffect(() => {
    const element = canvas.current!;
    const update = () => {
      const width = element.clientWidth, height = element.clientHeight;
      setExtent({ width, height });
      setWindows(previous => {
        const surfaceWidth = Math.max(width, ...previous.map(entry => entry.width)), surfaceHeight = Math.max(height, ...previous.map(entry => entry.height));
        return previous.map(entry => ({ ...entry, x: Math.max(0, Math.min(entry.x, surfaceWidth - entry.width)), y: Math.max(0, Math.min(entry.y, surfaceHeight - entry.height)) }));
      });
    };
    const observer = new ResizeObserver(update);
    update(); observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!activeId) {
      if (focusRequest) launcher.current?.querySelector<HTMLElement>("button")?.focus();
      return;
    }
    const root = roots.current.get(activeId);
    if (root?.contains(document.activeElement) && !(document.activeElement as HTMLElement).closest(".wd-chrome-button")) return;
    const remembered = focused.current.get(activeId);
    if (remembered?.isConnected && !remembered.matches(":disabled") && remembered.getClientRects().length) remembered.focus();
    else (root && (dialogTabStops(root).find(element => !element.closest(".wd-chrome-button,.wd-workspace-edge")) ?? root.querySelector<HTMLElement>(".wd-frame")))?.focus();
  }, [activeId, focusRequest]);
  const activate = (id: string) => {
    if (activeId === id) return;
    const z = ++stack.current;
    setWindows(previous => previous.map(entry => entry.id === id ? { ...entry, z } : entry));
  };
  const open: OpenWindow = spec => {
    const existing = spec.key ? windows.find(entry => entry.key === spec.key) : undefined;
    if (existing) {
      const z = ++stack.current;
      setWindows(previous => previous.map(entry => entry.id === existing.id ? { ...entry, minimized: false, z } : entry));
      requestFocus(value => value + 1);
      return;
    }
    if (!spec.layout.window.size) throw new Error("Workspace window size unresolved");
    const size = spec.layout.window.size, area = canvas.current!;
    const id = `workspace-window-${++sequence.current}`, z = ++stack.current;
    const offset = windows.length % 4 * 24;
    const saved = spec.layout.window.flags?.["Save position"] === true ? geometryStore.load(spec.layout.window.name) : null;
    const resizable = spec.layout.window.flags?.Resizable === true;
    const width = saved && resizable ? Math.max(size.width, Math.min(saved.width, area.clientWidth)) : size.width;
    const height = saved && resizable ? Math.max(size.height, Math.min(saved.height, area.clientHeight)) : size.height;
    const surfaceWidth = Math.max(area.clientWidth, width, ...windows.map(entry => entry.width)), surfaceHeight = Math.max(area.clientHeight, height, ...windows.map(entry => entry.height));
    const x = Math.max(0, Math.min((saved?.x ?? Math.round((area.clientWidth - size.width) / 2)) + offset, surfaceWidth - width));
    const y = Math.max(0, Math.min((saved?.y ?? Math.round((area.clientHeight - size.height) / 2)) + offset, surfaceHeight - height));
    const maximized = saved?.maximized === true && spec.layout.window.flags?.["Maximize icon"] === true;
    setWindows(previous => [...previous, { ...spec, id, z, x, y, width, height, minimized: false, maximized }]);
  };
  const close = (id: string) => {
    const entry = windows.find(item => item.id === id);
    if (entry) { saveGeometry(geometryStore, entry); entry.onClose?.(); }
    focused.current.delete(id);
    setWindows(previous => previous.filter(entry => entry.id !== id));
    requestFocus(value => value + 1);
  };
  const minimize = (id: string) => {
    setWindows(previous => previous.map(entry => entry.id === id ? { ...entry, minimized: true } : entry));
    requestFocus(value => value + 1);
  };
  const restore = (id: string) => {
    const z = ++stack.current;
    setWindows(previous => previous.map(entry => entry.id === id ? { ...entry, minimized: false, z } : entry));
    requestFocus(value => value + 1);
  };

  // while the library owns bounded dragging/resizing inside it.
  const surfaceWidth = Math.max(extent.width, ...windows.map(entry => entry.width));
  const surfaceHeight = Math.max(extent.height, ...windows.map(entry => entry.height));
  return <WorkspaceContext.Provider value={open}><div className="wd-workspace" data-testid="workspace">
    <div ref={launcher} className="wd-workspace-launcher">{children}</div>
    <div ref={canvas} className="wd-workspace-canvas" data-testid="workspace-canvas">
      <div className="wd-workspace-surface" style={{ position: "relative", width: surfaceWidth, height: surfaceHeight }}>
        {windows.map(entry => {
          const size = entry.layout.window.size!, width = entry.maximized ? Math.max(size.width, extent.width) : entry.width,
            height = entry.maximized ? Math.max(size.height, extent.height) : entry.height;
          return <WindowInteraction key={entry.id}
            rootRef={element => { if (element) roots.current.set(entry.id, element); else roots.current.delete(entry.id); }}
            className="wd-workspace-window" hidden={entry.minimized} data-testid={entry.id} data-active={activeId === entry.id}
            style={{ zIndex: entry.z }} bounds={{ x: entry.maximized ? 0 : entry.x, y: entry.maximized ? 0 : entry.y, width, height }}
            minimum={size} maximized={entry.maximized} resizable={entry.layout.window.flags?.Resizable === true}
            movable={entry.layout.window.flags?.["Title bar"] !== false || entry.layout.window.flags?.["Move/Background"] !== false}
            showGrip={entry.layout.window.flags?.["With grip"] === true} handleTestId={`${entry.id}-resize`}
            onBoundsChange={next => setWindows(previous => previous.map(item => item.id === entry.id ? { ...item, ...next } : item))}
            onFocusCapture={event => {
              if (event.target instanceof HTMLElement && !event.target.closest(".wd-chrome-button")) focused.current.set(entry.id, event.target);
              activate(entry.id);
            }} onPointerDownCapture={() => activate(entry.id)}>
            <WdFrame layout={entry.layout} instance={`${entry.id}-frame`} width={width} height={height}
              onClose={() => close(entry.id)} onMinimize={() => minimize(entry.id)}
              onToggleMaximize={() => setWindows(previous => previous.map(item => item.id === entry.id ? { ...item, maximized: !item.maximized } : item))}>
              <WorkspaceCloseContext.Provider value={() => close(entry.id)}>{entry.content}</WorkspaceCloseContext.Provider>
            </WdFrame>
          </WindowInteraction>;
        })}
      </div>
    </div>
    <nav className="wd-workspace-tasks" aria-label={config.labels.openWindows} data-testid="workspace-tasks">
      {windows.map(entry => <button key={entry.id} type="button" data-testid={`${entry.id}-task`} aria-pressed={activeId === entry.id}
        onClick={() => restore(entry.id)}>{entry.layout.window.title ?? entry.layout.window.name} · {entry.id.replace("workspace-window-", "")}{entry.minimized ? ` (${config.labels.minimized})` : ""}</button>)}
    </nav>
  </div></WorkspaceContext.Provider>;
}
