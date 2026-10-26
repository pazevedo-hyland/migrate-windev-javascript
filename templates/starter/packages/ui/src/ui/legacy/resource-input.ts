import { dateEntryDisplay, dateEntryResult } from "../../value/date-entry";
import { decimalMaskDisplay, decimalMaskOf, decimalMaskValue } from "./decimal-entry";
import type { ResourceInput } from "./resource-state";

type TextInput = Extract<ResourceInput, { kind: "text" }>;
const compactDate = (input: TextInput) => input.inputType === "date" && ["AAAAMMJJ", "YYYYMMDD"].includes(input.returnFormat ?? "");
const compactTime = (input: TextInput) => input.inputType === "time" && ["HHmm", "HHmmSS", "HHmmSSCC"].includes(input.returnFormat ?? "");

export function resourceInputDisplay(input: TextInput): string {
  const value = input.value;
  if (value === null) return "";
  if (compactDate(input)) return dateEntryDisplay(value);
  if (compactTime(input)) {
    const size = input.returnFormat!.length;
    if (value.length !== size || !/^[0-9]+$/.test(value)) return value;
    return `${value.slice(0, 2)}:${value.slice(2, 4)}${size >= 6 ? `:${value.slice(4, 6)}` : ""}${size === 8 ? `,${value.slice(6, 8)}` : ""}`;
  }
  const mask = ["numeric", "currency"].includes(input.inputType ?? "") ? decimalMaskOf(input.inputMask) : null;
  return mask ? decimalMaskDisplay(mask, value) : value;
}

export type ResourceInputResult = { kind: "valid"; value: string | null } | { kind: "invalid" };
export function resourceInputValue(input: TextInput, text: string, edited: boolean): ResourceInputResult {
  if (!edited) return { kind: "valid", value: input.value };
  if (compactDate(input)) return dateEntryResult({ original: input.value, text, edited: true });
  if (compactTime(input)) {
    if (text === "") return { kind: "valid", value: "" };
    const size = input.returnFormat!.length;
    const pattern = size === 4 ? /^([0-9]{2}):([0-9]{2})$/ : size === 6 ? /^([0-9]{2}):([0-9]{2}):([0-9]{2})$/ : /^([0-9]{2}):([0-9]{2}):([0-9]{2}),([0-9]{2})$/;
    const parts = text.match(pattern);
    if (!parts || Number(parts[1]) > 23 || Number(parts[2]) > 59 || size >= 6 && Number(parts[3]) > 59) return { kind: "invalid" };
    return { kind: "valid", value: parts.slice(1).join("") };
  }
  if (["numeric", "currency"].includes(input.inputType ?? "")) {
    if (text === "") return { kind: "valid", value: "" };
    const mask = decimalMaskOf(input.inputMask), value = mask ? decimalMaskValue(mask, text) : /^[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)$/.test(text) ? text.replace(",", ".") : undefined;
    return value === undefined ? { kind: "invalid" } : { kind: "valid", value };
  }
  // An unknown FormatMémorisé is an opaque string, never a guessed locale conversion.
  return { kind: "valid", value: text };
}
