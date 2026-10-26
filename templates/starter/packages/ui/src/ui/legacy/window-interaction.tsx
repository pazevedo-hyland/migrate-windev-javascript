import { useImperativeHandle, useRef, type ComponentPropsWithoutRef, type Ref } from "react";
import { useUiConfig } from "../../config";
import { Rnd, type HandleComponent, type HandleStyles, type RndDragCallback, type RndResizeCallback } from "react-rnd";

export interface WindowInteractionBounds { x: number; y: number; width: number; height: number }
export type WindowResizeEdge = "n" | "e" | "s" | "w" | "ne" | "nw" | "se" | "sw";
const edges: WindowResizeEdge[] = ["n", "e", "s", "w", "ne", "nw", "se", "sw"];
const directions = { n: "top", e: "right", s: "bottom", w: "left", ne: "topRight", nw: "topLeft", se: "bottomRight", sw: "bottomLeft" } as const;

type RootProps = Omit<ComponentPropsWithoutRef<"div">, "children" | "onChange" | "onResize" | "onMouseDown" | "onMouseUp">;
export interface WindowInteractionProps extends RootProps {
  bounds: WindowInteractionBounds;
  minimum: { width: number; height: number };
  movable?: boolean;
  resizable?: boolean;
  maximized?: boolean;
  showGrip?: boolean;
  enableUserSelectHack?: boolean;

  handleTestId: string;
  cornerTestId?: string;
  keyboardResize?: "corner" | "all";
  resizeTabIndex?: number;
  rootRef?: Ref<HTMLDivElement>;
  onBoundsChange: (next: WindowInteractionBounds) => void;
  children: React.ReactNode;
}

export function WindowInteraction({ bounds, minimum, movable = true, resizable = false, maximized = false,
  showGrip = false, enableUserSelectHack, handleTestId, cornerTestId, keyboardResize = "corner", resizeTabIndex = 0, rootRef,
  onBoundsChange, children, style, hidden, ...root }: WindowInteractionProps) {
  const config = useUiConfig();
  const content = useRef<HTMLDivElement>(null);
  useImperativeHandle(rootRef, () => content.current!, []);
  const canMove = movable && !maximized, canResize = resizable && !maximized;
  const ownTarget = (target: EventTarget | null) => target instanceof Element
    && target.closest("[data-wd-window-content]") === content.current
    && target.closest("dialog") === content.current?.closest("dialog");
  const move: RndDragCallback = (_event, data) => onBoundsChange({ ...bounds, x: data.x, y: data.y });
  const resize: RndResizeCallback = (_event, _direction, element, _delta, position) =>
    onBoundsChange({ ...position, width: element.offsetWidth, height: element.offsetHeight });
  const handles: HandleComponent = {}, handleStyles: HandleStyles = {};
  if (canResize) for (const edge of edges) {
    const direction = directions[edge], corner = edge.length === 2, grip = edge === "se" && showGrip;
    handleStyles[direction] = corner ? { width: grip ? 14 : 8, height: grip ? 14 : 8,
      left: edge.includes("w") ? 0 : undefined, right: edge.includes("e") ? grip ? 2 : 0 : undefined,
      top: edge.includes("n") ? 0 : undefined, bottom: edge.includes("s") ? grip ? 2 : 0 : undefined }
      : edge === "n" || edge === "s" ? { left: 8, right: 8, width: "auto", height: 4, top: edge === "n" ? 0 : undefined, bottom: edge === "s" ? 0 : undefined }
        : { top: 8, bottom: 8, height: "auto", width: 4, left: edge === "w" ? 0 : undefined, right: edge === "e" ? 0 : undefined };
    handles[direction] = <button type="button" tabIndex={edge === "se" ? resizeTabIndex : -1}
      className={`wd-workspace-edge wd-workspace-edge-${edge}${grip ? " wd-workspace-grip" : ""}`}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      data-testid={edge === "se" ? cornerTestId ?? handleTestId : `${handleTestId}-${edge}`}
      aria-label={`${config.labels.resizeWindow} (${edge})`}
      onKeyDown={event => {
        if (keyboardResize !== "all" && edge !== "se" || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key) || event.altKey || event.ctrlKey || event.metaKey) return;
        event.preventDefault(); event.stopPropagation();
        const step = event.shiftKey ? 1 : 8;
        onBoundsChange({ ...bounds, width: Math.max(minimum.width, bounds.width + (event.key === "ArrowRight" ? step : event.key === "ArrowLeft" ? -step : 0)),
          height: Math.max(minimum.height, bounds.height + (event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0)) });
      }} />;
  }
  return <Rnd {...root} hidden={hidden} data-wd-window-interaction=""
    position={{ x: bounds.x, y: bounds.y }} size={{ width: bounds.width, height: bounds.height }}
    minWidth={minimum.width} minHeight={minimum.height}
    style={{ ...style, position: "absolute", left: 0, top: 0, ...(hidden ? { display: "none" } : {}) }}
    dragHandleClassName="wd-title" cancel=".wd-chrome-button,input,textarea,select,button" bounds="parent"
    disableDragging={!canMove} enableUserSelectHack={enableUserSelectHack} enableResizing={canResize} resizeHandleComponent={handles} resizeHandleStyles={handleStyles}
    onDragStart={event => {
      if (!canMove || !ownTarget(event.target)) return false;
      event.preventDefault(); event.stopPropagation();
    }} onDrag={move} onDragStop={move}
    onResizeStart={event => { event.preventDefault(); event.stopPropagation(); }} onResize={resize} onResizeStop={resize}>
    <div ref={content} data-wd-window-content="" style={{ width: "100%", height: "100%" }}>{children}</div>
  </Rnd>;
}
