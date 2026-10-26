import { createContext, useContext, useEffect, useId, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { messageLayout as layout } from "./synthetic-layouts";
import { useUiConfig } from "../../config";
import { controlBox, controlOf } from "./layout";
import { MessageController, type PendingMessage } from "./message-state";
import { WdButton } from "./wd";
import { ResourceBox } from "./resource-dialog";
import { browserMeasure, messageGeometry } from "./dialog-metrics";
import { messageClipboardText, writeMessageClipboard } from "./message-clipboard";
import { WdModal, type WdModalHandle } from "./modal";
import { dialogLayout } from "./dialog-layout";

type DialogService = Pick<MessageController, "open" | "resource">;
const MessageContext = createContext<DialogService | null>(null);

export function useDialogs() {
  const service = useContext(MessageContext);
  if (!service) throw new Error("DialogProvider is required");
  return { message: service.open, resource: service.resource };
}

export function DialogProvider({ children }: { children: ReactNode }) {
  const [controller] = useState(() => new MessageController());
  const current = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  useEffect(() => () => controller.cancelAll(), [controller]);
  return <MessageContext.Provider value={controller}>
    {children}
    {current?.kind === "message" && <MessageBox key={current.id} current={current} controller={controller} />}
    {current?.kind === "resource" && <ResourceBox key={current.id} current={current} controller={controller} />}
  </MessageContext.Provider>;
}

function MessageBox({ current, controller }: { current: PendingMessage; controller: MessageController }) {
  const config = useUiConfig();
  const captions = { BTN_OK: config.labels.ok, BTN_OUI: config.labels.yes, BTN_NON: config.labels.no, BTN_ANNULER: config.labels.cancel };
  const ref = useRef<WdModalHandle>(null), textId = useId();
  const { request, model, id } = current;
  const sounded = useRef(false);
  useEffect(() => {
    if (sounded.current) return;
    sounded.current = true;
    try { void Promise.resolve(config.playSound(model.type)).catch(() => undefined); } catch { /* Optional sound cannot change the awaited result. */ }
  }, [model.type]);
  const size = layout.window.size;
  if (!size) throw new Error("Message base geometry unresolved");
  const body = controlOf(layout, "LIB_INFO");
  const icon = controlOf(layout, model.icon);
  const width = controlOf(layout, "BTN_OK").width!;

  const total = width * model.buttons.length + 6 * (model.buttons.length - 1);
  const [fit, setFit] = useState<ReturnType<typeof messageGeometry> | null>(null);
  useEffect(() => {
    let active = true;
    void document.fonts.ready.then(() => {
      if (!active || !ref.current) return;
      const font = getComputedStyle(ref.current.element()!.querySelector(".wd-frame")!).font;
      setFit(messageGeometry(layout, request.text, model.buttons.length, browserMeasure(font)));
    });
    return () => { active = false; };
  }, [request.text, model.buttons.length]);
  const frameWidth = fit?.width ?? size.width, frameHeight = fit?.height ?? size.height;
  useEffect(() => {
    const dialog = ref.current!.element()!;
    dialog.querySelectorAll<HTMLButtonElement>(".wd-message-actions button")[model.focus]?.focus();
    return () => { dialog.close(); };
  }, [model.focus]);
  const finish = (button?: Parameters<MessageController["finish"]>[1]) => {
    // Close while still connected so the browser restores the opener's focus.
    ref.current?.close();
    controller.finish(id, button);
  };

  return <WdModal ref={ref} layout={dialogLayout(layout, request.title)} instance="message-box-frame" testId="starter-message"
    restoreTestId="message-box-restore" describedBy={textId} contentSize={fit ?? undefined} onClose={() => finish()}
    onCopy={event => {
      event.preventDefault(); event.clipboardData.setData("text/plain", messageClipboardText(request));
    }}>
    {({ width: actualWidth, height: actualHeight }) => <>
        <WdButton control={controlOf(layout, "BTN_Copier_caché")} tabIndex={-1} aria-hidden="true" onClick={() => { void writeMessageClipboard(request); }} />
        <span aria-hidden="true" data-testid={icon.name} className={`wd-message-icon ${model.icon === "ICON_ERREUR" ? "error" : "info"}`}
          style={{ ...controlBox(icon), top: body.y + ((fit?.textHeight ?? body.height!) - icon.height!) / 2 }}>
          {model.icon === "ICON_ERREUR" ? "×" : model.icon === "ICON_QUESTION" ? "?" : "i"}
        </span>
        <div id={textId} data-testid={body.name} className="wd-message-text" style={{ ...controlBox(body), width: (fit?.textWidth ?? body.width!) + actualWidth - frameWidth, height: fit?.textHeight ?? body.height! }}>{request.text}</div>
        <div className="wd-message-actions">
          {model.buttons.map((button, index) => <WdButton key={button.name} control={{ ...controlOf(layout, button.name),
            caption: captions[button.caption] }}
            style={{ left: (actualWidth - total) / 2 + index * (width + 6), top: (fit?.buttonY ?? controlOf(layout, button.name).y) + actualHeight - frameHeight }} onClick={() => finish(button.name)} />)}
        </div>
    </>}
  </WdModal>;
}
