import { useEffect, useId, useRef, useState } from "react";
import { resourceLayout as layout } from "./synthetic-layouts";
import { useUiConfig } from "../../config";
import { controlBox, controlOf, skinSourceImage } from "./layout";
import type { MessageController, PendingResource } from "./message-state";
import { WdButton, WdEdit } from "./wd";
import { browserMeasure, resourceGeometry, resourceTextInputGeometry } from "./dialog-metrics";
import { WdModal, type WdModalHandle } from "./modal";
import { rightAlignedResourceInput } from "./resource-state";
import { dialogLayout } from "./dialog-layout";
import { useInputSelection } from "./input-selection";
import { resourceInputDisplay, resourceInputValue } from "./resource-input";
import { CalculatorDialog } from "./calculator";

export function ResourceBox({ current, controller }: { current: PendingResource; controller: MessageController }) {
  const config = useUiConfig();
  const { id, request, model } = current;
  const selection = useInputSelection(request.input?.kind === "text" ? request.input.automaticErase : undefined);
  const ref = useRef<WdModalHandle>(null), inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null), textId = useId();
  const [input, setInput] = useState<string | boolean | null>(() => request.input?.kind === "text" ? resourceInputDisplay(request.input) : request.input?.value ?? null);
  const [edited, setEdited] = useState(false), [invalid, setInvalid] = useState(false), [calculator, setCalculator] = useState(false);
  const changeInput = (value: string | boolean) => { setInput(value); setEdited(true); setInvalid(false); };
  const size = layout.window.size!;
  const body = controlOf(layout, "LIB_INFO"), button = controlOf(layout, "BTN_1");
  const field = controlOf(layout, request.input?.kind === "checkbox" ? "INT_1" : "SAI_1");
  const icon = controlOf(layout, "ICONE");
  const multiline = request.input?.kind === "text" && !request.input.password && !rightAlignedResourceInput(request.input.inputType) && (request.input.value ?? "").includes("\r\n");

  const [fit, setFit] = useState<ReturnType<typeof resourceGeometry> | null>(null);
  useEffect(() => {
    let active = true;
    void document.fonts.ready.then(() => {
      if (!active || !ref.current) return;
      const font = getComputedStyle(ref.current.element()!.querySelector(".wd-frame")!).font;
      const measure = browserMeasure(font);

      const style = inputRef.current ? getComputedStyle(inputRef.current) : null;
      const inset = style ? [style.paddingTop, style.paddingBottom, style.borderTopWidth, style.borderBottomWidth].reduce((sum, value) => sum + parseFloat(value || "0"), 0) : 0;
      const inputSize = request.input?.kind === "text"
        ? resourceTextInputGeometry(request.input, { width: field.width!, height: field.height! }, measure, inset, multiline)
        : request.input ? { width: field.width!, height: field.height! } : undefined;
      setFit(resourceGeometry(layout, request.text, request.title, model.buttons.map(item => item.caption), measure, window.innerWidth,
        inputSize));
    });
    return () => { active = false; };
  }, [model.buttons, request.title, request.text, request.input, multiline, field.width, field.height]);
  const width = fit?.width ?? Math.max(400, size.width), extra = request.input ? field.height! : 0, height = fit?.height ?? size.height + extra;
  const total = fit?.total ?? model.buttons.length * button.width! + (model.buttons.length - 1) * 12;
  useEffect(() => {
    const dialog = ref.current!.element()!;
    if (request.input) inputRef.current?.focus();
    else dialog.querySelectorAll<HTMLButtonElement>(".wd-resource-actions button")[model.focus]?.focus();
    return () => dialog.close();
  }, [model.focus, request.input]);
  const finish = (name?: string, reason: "close" | "escape" = "close") => {
    const value = request.input?.kind === "text" ? resourceInputValue(request.input, String(input ?? ""), edited) : { kind: "valid" as const, value: edited ? input : request.input?.value };

    // remains available even for a partial typed draft; direct chrome keeps its original.
    const cancellation = !name || name === model.buttons[(request.destructive ? request.safeIndex! : request.cancelIndex) - 1].name;
    if (name && !cancellation && value.kind === "invalid") { setInvalid(true); inputRef.current?.focus(); return; }
    ref.current?.close(); controller.finish(id, name, reason, value.kind === "valid" ? value.value : input);
  };
  return <WdModal ref={ref} layout={dialogLayout(layout, request.title)} instance="resource-box-frame" testId="starter-resource"
    restoreTestId="resource-box-restore" describedBy={textId} contentSize={fit ?? { width, height }} onClose={() => finish()} onCancel={() => finish(undefined, "escape")}
    onKeyDown={event => {
      if (event.defaultPrevented) return;
      if (event.key === "Enter" && !multiline && event.target === inputRef.current && model.buttons[model.focus]) {
        event.preventDefault(); finish(model.buttons[model.focus].name);
      }
    }}>
    {({ width: actualWidth, height: actualHeight }) => <>
        <span data-testid="ICONE" data-control-path={icon.path} data-icon={model.icon?.kind === "standard" ? model.icon.name : model.icon?.kind ?? ""}
          aria-hidden="true" className="wd-resource-icon" style={{ ...controlBox(icon), left: fit?.iconX ?? icon.x, top: fit?.iconY ?? icon.y }}>
          {model.icon?.kind === "custom" ? <img src={skinSourceImage(model.icon.name, config.assets)} alt="" /> : model.icon?.kind === "standard" &&
            <span className={`wd-message-icon ${model.icon.name === "ICON_ERREUR" ? "error" : "info"}`}>
              {model.icon.name === "ICON_ERREUR" ? "×" : model.icon.name === "ICON_Question" ? "?" : "i"}
            </span>}
        </span>
        <div id={textId} className="wd-message-text" data-testid={body.name} style={{ ...controlBox(body), left: fit?.bodyX ?? body.x,
          width: (fit?.bodyWidth ?? body.width! + width - size.width) + actualWidth - width, height: fit?.textHeight ?? body.height! }}>{request.text}</div>
        {request.input && <div className="wd-resource-input" style={{ left: fit?.bodyX ?? body.x, top: fit?.inputY ?? body.y + body.height! - 6,
          width: (fit?.inputWidth ?? width - body.x - 16) + actualWidth - width, height: fit?.inputHeight ?? field.height! }}>
          {request.input.kind === "checkbox" ? <label>
            <input ref={node => { inputRef.current = node; }} data-testid="INT_1" type="checkbox" checked={Boolean(input)} onChange={event => changeInput(event.target.checked)} />{request.input.label}
          </label> : multiline ? <textarea {...selection} ref={node => { inputRef.current = node; }} className="wd-resource-edit" data-testid="SAI_1" aria-labelledby={textId}
            style={{ overflowY: fit ? "auto" : "hidden" }}
            maxLength={request.input.maxLength || undefined} value={String(input ?? "")} onChange={event => changeInput(event.target.value.replace(/\r?\n/g, "\r\n"))} />
          : request.input.inputType && request.input.inputType !== "text" ? <WdEdit control={{ ...field, x: 0, y: 0,
              width: (fit?.inputWidth ?? width - body.x - 16) + actualWidth - width, height: fit?.inputHeight ?? field.height!,
              caption_width: 0, input_type: "Text", h_align: "Right", input_mask: request.input.inputMask,
              visible: true, flags: { ...field.flags, Password: request.input.password === true } }}
            ref={node => { inputRef.current = node; }} aria-labelledby={textId} automaticErase={request.input.automaticErase}
            decimalMask={request.input.inputType === "numeric" || request.input.inputType === "currency"}
            aria-invalid={invalid || undefined} maxLength={request.input.maxLength || undefined} value={String(input ?? "")} onChange={event => changeInput(event.target.value)}
            adornment={request.input.calculator && ["numeric", "currency"].includes(request.input.inputType) ? { width: 24, content: <button type="button"
              className="wd-resource-calculator" data-testid="SAI_1__calculator" aria-label={config.labels.calculator} onClick={() => setCalculator(true)}>▦</button> } : undefined} />
          : <input {...selection} ref={node => { inputRef.current = node; }} className="wd-resource-edit" data-testid="SAI_1" aria-labelledby={textId}
            type={request.input.password ? "password" : "text"} maxLength={request.input.maxLength || undefined} value={String(input ?? "")} onChange={event => changeInput(event.target.value)} />}
        </div>}
        <div className="wd-resource-actions">
          {model.buttons.map((item, index) => <WdButton key={item.name} control={{ ...button, name: item.name, path: item.name,
            caption: item.caption }} style={{ left: (actualWidth - total) / 2 + (fit?.widths.slice(0, index).reduce((sum, value) => sum + value, 0) ?? index * button.width!) + index * 12,
              width: fit?.widths[index] ?? button.width!, top: (fit?.buttonY ?? button.y + extra) + actualHeight - height }}
            onClick={() => finish(item.name)} />)}
        </div>
        {calculator && <CalculatorDialog initial={request.input?.kind === "text" ? (() => {
          const value = resourceInputValue(request.input, String(input ?? ""), true);
          return value.kind === "valid" ? value.value ?? "" : "";
        })() : ""} close={value => {
          setCalculator(false);
          if (value !== null && request.input?.kind === "text") changeInput(resourceInputDisplay({ ...request.input, value }));
        }} />}
    </>}
  </WdModal>;
}
