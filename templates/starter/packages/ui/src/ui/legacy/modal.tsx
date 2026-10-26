import { useEffect, useImperativeHandle, useRef, useState, type ClipboardEventHandler, type KeyboardEvent, type ReactNode, type Ref } from "react";
import type { WindowGeometry, WindowGeometryStore } from "../../application/window-geometry";
import { useUiConfig } from "../../config";
import { trapDialogTab } from "./dialog-keyboard";
import { type LegacyLayout } from "./layout";
import { WdFrame } from "./wd";
import { WindowInteraction } from "./window-interaction";

export interface WdModalHandle { close(): void; element(): HTMLDialogElement | null }

export function WdModal({ ref, layout, instance, testId, restoreTestId, onClose, onCancel, onKeyDown, onCopy, describedBy, contentSize, geometryStore: storeOverride, children }: {
  ref: Ref<WdModalHandle>; layout: LegacyLayout; instance: string; testId: string; restoreTestId: string;
  onClose: () => void; onCancel?: () => void; onKeyDown?: (event: KeyboardEvent<HTMLDialogElement>) => void;
  onCopy?: ClipboardEventHandler<HTMLDialogElement>; describedBy?: string;
  geometryStore?: WindowGeometryStore;
  contentSize?: { width: number; height: number };
  children: ReactNode | ((extent: { width: number; height: number }) => ReactNode);
}) {
  const config = useUiConfig(), windowGeometryStore = storeOverride ?? config.geometryStore;
  const size = layout.window.size;
  if (!size) throw new Error(`Modal geometry unresolved: ${layout.window.name}`);
  const resizable = layout.window.flags?.Resizable === true;
  const movableTitle = layout.window.flags?.["Title bar"] !== false || layout.window.flags?.["Move/Background"] !== false;
  const title = layout.controls.find(control => control.name === "RADTitle")?.caption ?? layout.window.title ?? layout.window.name;
  const dialog = useRef<HTMLDialogElement>(null);
  const [geometry, setGeometry] = useState<WindowGeometry>(() => {
    const saved = layout.window.flags?.["Save position"] === true ? windowGeometryStore.load(layout.window.name) : null;
    const width = contentSize?.width ?? (resizable && saved ? Math.max(size.width, Math.min(saved.width, innerWidth - 16)) : size.width);
    const height = contentSize?.height ?? (resizable && saved ? Math.max(size.height, Math.min(saved.height, innerHeight - 16)) : size.height);
    return { width, height, x: Math.max(0, Math.min(saved?.x ?? Math.round((innerWidth - width) / 2), innerWidth - width)),
      y: Math.max(0, Math.min(saved?.y ?? Math.round((innerHeight - height) / 2), innerHeight - height)),
      maximized: saved?.maximized === true && layout.window.flags?.["Maximize icon"] === true };
  });
  const [extent, setExtent] = useState({ width: innerWidth, height: innerHeight });
  const [minimized, setMinimized] = useState(false);
  const latest = useRef(geometry), focused = useRef<HTMLElement | null>(null), restoreFocus = useRef(false);
  useEffect(() => { latest.current = geometry; }, [geometry]);
  const persist = () => {
    if (layout.window.flags?.["Save position"] === true) windowGeometryStore.save(layout.window.name, latest.current);
  };
  useImperativeHandle(ref, () => ({ element: () => dialog.current, close() { persist(); dialog.current?.close(); } }));
  const fittedWidth = contentSize?.width, fittedHeight = contentSize?.height;
  const [previousFit, setPreviousFit] = useState({ width: fittedWidth, height: fittedHeight });
  if (previousFit.width !== fittedWidth || previousFit.height !== fittedHeight) {
    setPreviousFit({ width: fittedWidth, height: fittedHeight });
    if (fittedWidth !== undefined && fittedHeight !== undefined) setGeometry(previous => ({ ...previous, width: fittedWidth, height: fittedHeight,
      x: Math.max(0, Math.round((innerWidth - fittedWidth) / 2)), y: Math.max(0, Math.round((innerHeight - fittedHeight) / 2)) }));
  }
  useEffect(() => {
    const element = dialog.current!;
    // A closed, invisible host provides layout for Rnd's initial measurement.
    // Keep the existing effect order so native focus follows child input setup.
    element.style.removeProperty("visibility"); element.showModal(); element.style.removeProperty("display");
    return () => { element.close(); element.style.display = "block"; element.style.visibility = "hidden"; };
  }, []);
  useEffect(() => {
    const save = () => {
      if (layout.window.flags?.["Save position"] === true) windowGeometryStore.save(layout.window.name, latest.current);
    };
    const resize = () => {
      setExtent({ width: innerWidth, height: innerHeight });
      setGeometry(previous => ({ ...previous, x: Math.max(0, Math.min(previous.x, Math.max(innerWidth, previous.width) - previous.width)), y: Math.max(0, Math.min(previous.y, Math.max(innerHeight, previous.height) - previous.height)) }));
    };
    window.addEventListener("pagehide", save); window.addEventListener("resize", resize);
    return () => { window.removeEventListener("pagehide", save); window.removeEventListener("resize", resize); };
  }, [layout]);
  useEffect(() => {
    if (!minimized && restoreFocus.current) {
      restoreFocus.current = false;
      if (focused.current?.isConnected) focused.current.focus();
      else dialog.current?.querySelector<HTMLElement>(".wd-frame")?.focus();
    }
  }, [minimized]);
  const width = geometry.maximized ? Math.max(size.width, extent.width - 40) : geometry.width;
  const height = geometry.maximized ? Math.max(size.height, extent.height - 40) : geometry.height;
  return <dialog ref={dialog} className="wd-dialog-host wd-modal" data-testid={testId} aria-label={title} aria-describedby={describedBy} onCopy={onCopy} data-wd-movable-title={movableTitle}
    style={{ left: 0, top: 0, margin: 0, width: "100vw", height: "100vh", maxWidth: "none", maxHeight: "none", overflow: "auto", pointerEvents: "auto", display: "block", visibility: "hidden" }}
    onCancel={event => { event.preventDefault(); event.stopPropagation(); if (event.target === event.currentTarget) (onCancel ?? onClose)(); }}
    onKeyDown={event => {
      if (event.target instanceof Element && event.target.closest("dialog") !== event.currentTarget) return;
      trapDialogTab(event); onKeyDown?.(event);
    }}
    onFocusCapture={event => {
      if (event.target instanceof HTMLElement && event.target.closest("dialog") === dialog.current && event.target.closest(".wd-frame")?.closest("dialog") === dialog.current && !event.target.closest(".wd-chrome-button,.wd-workspace-edge")) focused.current = event.target;
    }}
    onPointerDown={event => {
      // Native child dialogs must never start an owning workspace/dialog title drag.
      if (event.target instanceof Element && event.target.closest("dialog") === event.currentTarget
        && event.target.closest(".wd-title,.wd-workspace-edge")) event.stopPropagation();
    }}
    >
    <div style={{ position: "relative", width: minimized ? extent.width : Math.max(extent.width, width, geometry.width),
      height: minimized ? extent.height : Math.max(extent.height, height, geometry.height) }}>
      {minimized && <button data-testid={restoreTestId} style={{ position: "absolute", left: geometry.x, top: geometry.y }}
        onClick={() => { restoreFocus.current = true; setMinimized(false); }}>{title}</button>}
      <WindowInteraction hidden={minimized} bounds={{ x: geometry.maximized ? 20 : geometry.x, y: geometry.maximized ? 20 : geometry.y, width, height }}
        minimum={contentSize ?? size} movable={movableTitle} resizable={resizable} maximized={geometry.maximized} enableUserSelectHack={false}
        showGrip={layout.window.flags?.["With grip"] === true} handleTestId={`${instance}-resize`} cornerTestId={`${instance}-resize-se`}
        keyboardResize="all" resizeTabIndex={-1} onBoundsChange={next => setGeometry(previous => ({ ...previous, ...next }))}>
        <WdFrame layout={layout} instance={instance} width={width} height={height}
          onClose={onClose} onMinimize={() => setMinimized(true)} onToggleMaximize={() => setGeometry(previous => ({ ...previous, maximized: !previous.maximized }))}>
          {typeof children === "function" ? children({ width, height }) : children}
        </WdFrame>
      </WindowInteraction>
    </div>
  </dialog>;
}
