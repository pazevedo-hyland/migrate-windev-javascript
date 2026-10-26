export type ResourceEditType = "text" | "numeric" | "currency" | "date" | "time";
export function rightAlignedResourceInput(type: ResourceEditType = "text") { return type === "numeric" || type === "currency" || type === "date" || type === "time"; }

export type ResourceInput = { kind: "text"; value: string | null; maxLength?: number; password?: boolean; automaticErase?: boolean; adaptWidth?: boolean; inputType?: ResourceEditType; inputMask?: string; returnFormat?: string; calculator?: boolean }
  | { kind: "checkbox"; value: boolean | null; label: string };
export interface ResourceRequest {
  title: string; text: string; buttons: { label: string; value?: number }[];
  defaultIndex: number; cancelIndex: number; input?: ResourceInput;
  destructive?: boolean; safeIndex?: number;
  icon?: { flags: number; image?: string };
}
export interface ResourceResult { result: number; input?: string | boolean | null }

export function resourceIcon(flags = 0, image = "") {
  if (!Number.isInteger(flags) || flags < -2147483648 || flags > 4294967295) throw new Error("Resource icon flags require a 32-bit integer");
  if (flags !== 0) {
    if ((flags & 0x20) && (flags & 0x10)) return { kind: "standard" as const, name: "ICON_ERREUR" };
    if (flags & 0x20) return { kind: "standard" as const, name: "ICON_Question" };
    if (flags & 0x40) return { kind: "standard" as const, name: "ICON_INFORMATION" };

    return null;
  }
  if (/[\\/]/.test(image)) throw new Error("Resource custom image requires a checked project asset name");
  return image ? { kind: "custom" as const, name: image } : null;
}

export function resourceModel(request: ResourceRequest) {
  if (!request.buttons.length || !Number.isInteger(request.cancelIndex) || request.cancelIndex < 1 || request.cancelIndex > request.buttons.length) throw new Error("Resource requires a valid cancel index");
  if (request.destructive && (!Number.isInteger(request.safeIndex) || !request.safeIndex || request.safeIndex < 1 || request.safeIndex > request.buttons.length)) throw new Error("Destructive resource requires an explicit safe index");
  const buttons = request.buttons.map((button, index) => {
    const result = button.value ?? index + 1;
    if (!Number.isSafeInteger(result)) throw new Error("Resource result must be an exact integer");
    return { name: `BTN_${index + 1}`, caption: button.label, result };
  });

  const cancel = request.destructive ? request.safeIndex! : request.cancelIndex;
  return { buttons, icon: resourceIcon(request.icon?.flags, request.icon?.image), focus: request.destructive ? cancel - 1 : request.defaultIndex - 1,
    escapeResult: buttons[cancel - 1].result,
    closeResult: request.destructive ? buttons[cancel - 1].result : request.cancelIndex };
}

export function resourceResult(request: ResourceRequest, model: ReturnType<typeof resourceModel>, button?: string, reason: "close" | "escape" = "close", input?: string | boolean | null): ResourceResult {
  const selected = button ? model.buttons.find(item => item.name === button) : null;
  if (button && !selected) throw new Error("Button is not present in this resource");
  // FermeDialogue copies input on click/Esc. Closing the window directly uses its raw default value.
  const changed = !!button || reason === "escape";
  return { result: selected?.result ?? (reason === "escape" ? model.escapeResult : model.closeResult),
    ...(request.input ? { input: changed && input !== undefined ? input : request.input.value } : {}) };
}
