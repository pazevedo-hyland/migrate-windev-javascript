import { createContext, useContext, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useUiConfig, useWorkspace, useWorkspaceWindow } from "@windev-migration/ui";
import { screens } from "../generated/screens";
import { adapters } from "../adapters";
import { Screen, type ScreenHooks } from "./Screen";
import { preparePreviewLayout } from "./preview";
import { escapeToAbort, normalizeLayout } from "./layout";
import type { OpenTarget, ScreenAdapter, ScreenDefinition, WindowContext } from "./contracts";

type Opener = <T = unknown>(target: string | OpenTarget, ...params: unknown[]) => Promise<T | undefined>;
const OpenerContext = createContext<Opener | null>(null);

export function findScreen(name: string, definitions: readonly ScreenDefinition[] = screens): ScreenDefinition {
  const definition = definitions.find((item) => item.id.toLowerCase() === name.toLowerCase());
  if (!definition) throw new Error(`Unknown window: ${name}`);
  return definition;
}

export { normalizeLayout, normalizeLayout as normalizeKinds, escapeToAbort } from "./layout";

/**
 * Dev-only test hook (non-legacy, `npm run dev` / flows): `globalThis.__appWindows` opens a window as if from another
 * one (OpenChild) and reaches an open window's context, so click-through flows can drive the runtime.
 */
const devWindows = new Map<string, { context: WindowContext; setTitle: (title: string | undefined) => void }>();

/** Per-window runtime state shared by the frame callbacks and the hosted adapter. */
interface WindowRuntime extends ScreenHooks {
  returned?: unknown;
  requestClose?: () => Promise<boolean>;
}

/** Hosts one window's adapter; gives it Close(value), minimize/maximize and its title, bound to its workspace frame. */
function WindowHost({
  definition,
  adapter,
  params,
  runtime,
  open,
}: {
  definition: ScreenDefinition;
  adapter?: ScreenAdapter;
  params: readonly unknown[];
  runtime: WindowRuntime;
  open: Opener;
}) {
  const frame = useWorkspaceWindow();
  runtime.requestClose = frame.requestClose;
  const context = useMemo<WindowContext>(
    () => ({
      name: definition.id,
      params,
      open,
      close: (value) => {
        runtime.returned = value;
        frame.close();
      },
      minimize: frame.minimize,
      maximize: frame.maximize,
    }),
    [definition.id, params, open, runtime, frame],
  );
  runtime.setTitle = frame.setTitle;
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    devWindows.set(definition.id, { context, setTitle: frame.setTitle });
    return () => {
      devWindows.delete(definition.id);
    };
  }, [definition.id, context, frame]);
  return <Screen definition={definition} adapter={adapter} window={context} hooks={runtime} />;
}

/**
 * Opens legacy windows by name (WLanguage Open/OpenChild/OpenSister). One instance per window name, like WINDEV's
 * default: opening an open window brings it to the front. The promise resolves with ..ReturnedValue on close.
 * OpenChild (`{ name, child: true }`): the child closes when the window that opened it closes.
 */
export function WindowManager({
  children,
  definitions = screens,
  registry = adapters,
}: {
  children: ReactNode;
  definitions?: readonly ScreenDefinition[];
  registry?: Record<string, ScreenAdapter>;
}) {
  const workspace = useWorkspace();
  const { assets } = useUiConfig();
  const childrenOf = useRef(new Map<string, Set<string>>());
  const modalCount = useRef(new Map<string, number>());
  const setBlocked = (name: string, delta: number) => {
    const count = Math.max(0, (modalCount.current.get(name) ?? 0) + delta);
    modalCount.current.set(name, count);
    const host = document.querySelector<HTMLElement>(`section[data-layout="${name}"]`)?.closest<HTMLElement>(".wd-workspace-window");
    if (host) host.inert = count > 0;
  };
  const self = useRef<<T>(target: string | OpenTarget, parent: string | null, params: unknown[]) => Promise<T | undefined>>(null!);
  self.current = <T,>(target: string | OpenTarget, parent: string | null, params: unknown[]) =>
    new Promise<T | undefined>((resolve) => {
      const { name, child = false } = typeof target === "string" ? { name: target } : target;
      const definition = findScreen(name, definitions);
      const layout = preparePreviewLayout(normalizeLayout(definition.layout), assets);
      const runtime: WindowRuntime = {};
      const adapter = Object.hasOwn(registry, definition.id) ? registry[definition.id] : undefined;
      const key = definition.id;
      if (child && parent) {
        const set = childrenOf.current.get(parent) ?? new Set<string>();
        set.add(key);
        childrenOf.current.set(parent, set);
      }
      // Open() from a window is modal: the opener takes no input (clicks, keys, focus) until this window closes.
      const blocked = !child && parent && parent !== key ? parent : null;
      if (blocked) setBlocked(blocked, +1);
      workspace.open({
        key,
        layout,
        content: (
          <WindowHost
            definition={{ ...definition, layout }}
            adapter={adapter}
            params={params}
            runtime={runtime}
            open={(next, ...p) => self.current(next, key, p)}
          />
        ),
        onCloseRequest: () => (runtime.closing ? runtime.closing() : true),
        onKeyDown: (event) => escapeToAbort(event, layout, () => runtime.requestClose?.()),
        onClose: () => {
          if (blocked) setBlocked(blocked, -1);
          resolve(runtime.returned as T | undefined);
          const owned = childrenOf.current.get(key);
          childrenOf.current.delete(key);
          for (const set of childrenOf.current.values()) set.delete(key);
          for (const childKey of owned ?? []) workspace.close(childKey);
        },
      });
    });
  const opener = useMemo<Opener>(
    () =>
      (target, ...params) =>
        self.current(target, null, params),
    [],
  );
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const hook = globalThis as { __appWindows?: unknown };
    hook.__appWindows = {
      open: (target: string | OpenTarget, parent: string | null, ...params: unknown[]) => void self.current(target, parent, params),
      get: (name: string) => devWindows.get(name),
    };
    return () => {
      delete hook.__appWindows;
    };
  }, []);
  return <OpenerContext.Provider value={opener}>{children}</OpenerContext.Provider>;
}

export function useOpenWindow(): Opener {
  const open = useContext(OpenerContext);
  if (!open) throw new Error("WindowManager is required");
  return open;
}
