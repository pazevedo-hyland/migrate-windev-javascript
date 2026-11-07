import { createContext, useContext, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { WdFrame } from "./wd";
import { WindowInteraction } from "./window-interaction";
import type { LegacyLayout } from "./layout";
import type { WindowGeometryStore } from "../../application/window-geometry";
import { useUiConfig } from "../../config";
import { dialogTabStops } from "./dialog-keyboard";

/**
 * `onCloseRequest`: the window's closing event for the close box (false keeps the window open, like ReturnToCapture);
 * closing by code (`useWorkspaceWindow().close()`, `useWorkspace().close(key)`) does not ask.
 * `onKeyDown`: keys the window's controls did not stop (bubbling to the frame).
 */
export interface WindowSpec {
  layout: LegacyLayout; content: ReactNode; key?: string; onClose?: () => void;
  onCloseRequest?: () => boolean | Promise<boolean>; onKeyDown?: (event: KeyboardEvent<HTMLElement>) => void;
}
interface WindowEntry extends WindowSpec { id: string; x: number; y: number; width: number; height: number; z: number; minimized: boolean; maximized: boolean; title?: string }
type OpenWindow = (spec: WindowSpec) => void;
export interface WorkspaceApi { open: OpenWindow; close: (key: string) => void }
/** The controls of the window that renders the caller (stable for the window's lifetime). */
export interface WorkspaceWindow {
  close(): void;
  /** Close box behaviour: runs `onCloseRequest`, closes when it allows; resolves whether the window closed. */
  requestClose(): Promise<boolean>;
  minimize(): void;
  maximize(): void;
  restore(): void;
  /** ..Title at runtime; undefined restores the layout's title. */
  setTitle(title: string | undefined): void;
}
const WorkspaceContext = createContext<WorkspaceApi | null>(null);
const WorkspaceCloseContext = createContext<(() => void) | null>(null);
const WorkspaceWindowContext = createContext<WorkspaceWindow | null>(null);

export function useWorkspaceWindow(): WorkspaceWindow {
  const controls = useContext(WorkspaceWindowContext);
  if (!controls) throw new Error("Workspace instance is required");
  return controls;
}

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

export function useWorkspace(): WorkspaceApi {
  const api = useContext(WorkspaceContext);
  if (!api) throw new Error("WdWorkspace is required");
  return api;
}

export function WdWorkspace({ children, geometryStore: storeOverride }: { children: ReactNode; geometryStore?: WindowGeometryStore }) {
  const config = useUiConfig(), geometryStore = storeOverride ?? config.geometryStore;
  const [windows, setWindows] = useState<WindowEntry[]>([]);
  const [extent, setExtent] = useState({ width: 0, height: 0 });
  const [focusRequest, requestFocus] = useState(0);
  const canvas = useRef<HTMLDivElement>(null), launcher = useRef<HTMLDivElement>(null), sequence = useRef(0), stack = useRef(0);
  const roots = useRef(new Map<string, HTMLDivElement>()), focused = useRef(new Map<string, HTMLElement>());
  // Latest entries for callbacks that outlive a render (window controls, closes from other windows' events).
  const current = useRef<WindowEntry[]>(windows);
  current.current = windows;
  const closed = useRef(new Set<string>()), asking = useRef(new Set<string>());
  const controls = useRef(new Map<string, WorkspaceWindow>());
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
    const existing = spec.key ? current.current.find(entry => entry.key === spec.key && !closed.current.has(entry.id)) : undefined;
    if (existing) {
      const z = ++stack.current;
      setWindows(previous => previous.map(entry => entry.id === existing.id ? { ...entry, minimized: false, z } : entry));
      requestFocus(value => value + 1);
      return;
    }
    if (!spec.layout.window.size) throw new Error("Workspace window size unresolved");
    const size = spec.layout.window.size, area = canvas.current!;
    const id = `workspace-window-${++sequence.current}`, z = ++stack.current;
    const offset = current.current.length % 4 * 24;
    const saved = spec.layout.window.flags?.["Save position"] === true ? geometryStore.load(spec.layout.window.name) : null;
    const resizable = spec.layout.window.flags?.Resizable === true;
    const width = saved && resizable ? Math.max(size.width, Math.min(saved.width, area.clientWidth)) : size.width;
    const height = saved && resizable ? Math.max(size.height, Math.min(saved.height, area.clientHeight)) : size.height;
    const surfaceWidth = Math.max(area.clientWidth, width, ...current.current.map(entry => entry.width)), surfaceHeight = Math.max(area.clientHeight, height, ...current.current.map(entry => entry.height));
    const x = Math.max(0, Math.min((saved?.x ?? Math.round((area.clientWidth - size.width) / 2)) + offset, surfaceWidth - width));
    const y = Math.max(0, Math.min((saved?.y ?? Math.round((area.clientHeight - size.height) / 2)) + offset, surfaceHeight - height));
    const maximized = saved?.maximized === true && spec.layout.window.flags?.["Maximize icon"] === true;
    const entry = { ...spec, id, z, x, y, width, height, minimized: false, maximized };
    current.current = [...current.current, entry];
    setWindows(previous => [...previous, entry]);
  };
  const close = (id: string) => {
    if (closed.current.has(id)) return;
    const entry = current.current.find(item => item.id === id);
    if (!entry) return;
    closed.current.add(id);
    saveGeometry(geometryStore, entry); entry.onClose?.();
    focused.current.delete(id); controls.current.delete(id);
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
  const requestClose = async (id: string) => {
    const entry = current.current.find(item => item.id === id);
    if (!entry || closed.current.has(id) || asking.current.has(id)) return false;
    asking.current.add(id);
    let allowed = true;
    try { allowed = entry.onCloseRequest ? await entry.onCloseRequest() : true; } finally { asking.current.delete(id); }
    if (allowed) latest.current.close(id);
    return allowed;
  };
  const latest = useRef({ open, close, requestClose, minimize, restore });
  latest.current = { open, close, requestClose, minimize, restore };
  const windowControls = (id: string): WorkspaceWindow => {
    let found = controls.current.get(id);
    if (!found) {
      const update = (patch: (entry: WindowEntry) => Partial<WindowEntry>) => setWindows(previous => {
        let changed = false;
        const next = previous.map(entry => {
          if (entry.id !== id) return entry;
          const values = patch(entry);
          if (Object.keys(values).every(key => Object.is(entry[key as keyof WindowEntry], values[key as keyof WindowEntry]))) return entry;
          changed = true;
          return { ...entry, ...values };
        });
        return changed ? next : previous;
      });
      found = {
        close: () => latest.current.close(id),
        requestClose: () => latest.current.requestClose(id),
        minimize: () => latest.current.minimize(id),
        maximize: () => update(() => ({ maximized: true, minimized: false })),
        restore: () => { update(() => ({ maximized: false })); latest.current.restore(id); },
        setTitle: title => update(entry => entry.title === title ? {} : { title }),
      };
      controls.current.set(id, found);
    }
    return found;
  };
  const api = useRef<WorkspaceApi | null>(null);
  api.current ??= {
    open: spec => latest.current.open(spec),
    close: key => { for (const entry of current.current.filter(item => item.key === key)) latest.current.close(entry.id); },
  };

  // while the library owns bounded dragging/resizing inside it.
  const surfaceWidth = Math.max(extent.width, ...windows.map(entry => entry.width));
  const surfaceHeight = Math.max(extent.height, ...windows.map(entry => entry.height));
  return <WorkspaceContext.Provider value={api.current}><div className="wd-workspace" data-testid="workspace">
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
            <WdFrame layout={entry.layout} instance={`${entry.id}-frame`} width={width} height={height} title={entry.title}
              onClose={() => void requestClose(entry.id)} onMinimize={() => minimize(entry.id)} onKeyDown={entry.onKeyDown}
              onToggleMaximize={() => setWindows(previous => previous.map(item => item.id === entry.id ? { ...item, maximized: !item.maximized } : item))}>
              <WorkspaceWindowContext.Provider value={windowControls(entry.id)}>
                <WorkspaceCloseContext.Provider value={windowControls(entry.id).close}>{entry.content}</WorkspaceCloseContext.Provider>
              </WorkspaceWindowContext.Provider>
            </WdFrame>
          </WindowInteraction>;
        })}
      </div>
    </div>
    <nav className="wd-workspace-tasks" aria-label={config.labels.openWindows} data-testid="workspace-tasks">
      {windows.map(entry => <button key={entry.id} type="button" data-testid={`${entry.id}-task`} aria-pressed={activeId === entry.id}
        onClick={() => restore(entry.id)}>{entry.title ?? entry.layout.window.title ?? entry.layout.window.name} · {entry.id.replace("workspace-window-", "")}{entry.minimized ? ` (${config.labels.minimized})` : ""}</button>)}
    </nav>
  </div></WorkspaceContext.Provider>;
}
