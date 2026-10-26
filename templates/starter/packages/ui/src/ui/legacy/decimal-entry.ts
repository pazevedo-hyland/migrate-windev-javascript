import { integerMaskOf, type IntegerEdit, type IntegerMask } from "./numeric-entry";

export interface DecimalMask {
  readonly source: string;
  readonly integer: IntegerMask;
  readonly fractionCapacity: number;
  readonly signed: boolean;
  readonly groupSize: number | null;
}

export function decimalMaskOf(source: string | undefined): DecimalMask | null {
  const parts = source?.match(/^(\+?)(9+(?: +9+)*),(9+)(?![\s\S])/);
  if (!parts) return null;
  const integer = integerMaskOf(parts[2]);
  if (!integer) return null;
  const groups = parts[2].split(/ +/);

  if (groups.some(group => group.length !== groups[0].length)) return null;
  return { source: source!, integer, fractionCapacity: parts[3].length, signed: parts[1] === "+",
    groupSize: groups.length > 1 ? groups[0].length : null };
}

function groupedInteger(mask: DecimalMask, digits: string): string {
  if (!mask.groupSize) return digits;
  let result = "";
  for (let index = 0; index < digits.length; index++) {
    const separator = index > 0 && (digits.length - index) % mask.groupSize === 0;
    result += `${separator ? " " : ""}${digits[index]}`;
  }
  return result;
}

export function decimalMaskDisplay(mask: DecimalMask, canonical: string | null): string {
  if (canonical === null) return "";
  const parts = canonical.match(/^([+-]?)([0-9]+)(?:\.([0-9]+))?(?![\s\S])/);
  if (!parts) return canonical;
  return `${parts[1]}${groupedInteger(mask, parts[2])},${(parts[3] ?? "").padEnd(mask.fractionCapacity, "0")}`;
}

function draftParts(mask: DecimalMask, value: string) {
  if (!mask.groupSize && value.includes(" ")) return null;
  const parts = value.match(/^([+-]?)([0-9 ]*)(,([0-9]*))?(?![\s\S])/);
  if (!parts || (!mask.signed && parts[1])) return null;
  return { sign: parts[1], integer: parts[2].replaceAll(" ", ""), comma: parts[3] !== undefined, fraction: parts[4] ?? "" };
}

function characterOffset(value: string, position: number): number {
  return value.slice(0, position).replaceAll(" ", "").length;
}

function caretPosition(value: string, characters: number): number {
  if (characters === 0) return 0;
  let seen = 0;
  for (let index = 0; index < value.length; index++) if (value[index] !== " " && ++seen === characters) return index + 1;
  return value.length;
}

export function decimalMaskEdit(mask: DecimalMask, previous: string, candidate: string, start = candidate.length, end = start): IntegerEdit | null {
  if (candidate === previous) return { value: previous, start, end };
  const parts = draftParts(mask, candidate);
  if (!parts) return null;
  if (parts.integer.length > mask.integer.capacity || parts.fraction.length > mask.fractionCapacity) {
    const prior = draftParts(mask, previous);

    if (!prior || parts.integer.length + parts.fraction.length >= prior.integer.length + prior.fraction.length) return null;
  }
  const value = `${parts.sign}${groupedInteger(mask, parts.integer)}${parts.comma ? `,${parts.fraction}` : ""}`;
  return { value, start: caretPosition(value, characterOffset(candidate, start)), end: caretPosition(value, characterOffset(candidate, end)) };
}

export function decimalMaskValue(mask: DecimalMask, draft: string): string | undefined {
  const parts = draftParts(mask, draft);
  if (!parts || !parts.integer && !parts.fraction) return undefined;
  return `${parts.sign}${parts.integer || "0"}${parts.fraction ? `.${parts.fraction}` : ""}`;
}
