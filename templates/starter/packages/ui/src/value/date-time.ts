import { dateCalendarText, dateCalendarValue } from "./date-entry";

export type DateTimeEntryValue = string | null;
export type DateTimeEntryDraft = { original: DateTimeEntryValue; text: string; edited: boolean };
export type DateTimeEntryResult = { kind: "valid"; value: DateTimeEntryValue } | { kind: "invalid" };

type DateTimeParts = {
  date: string; hour: string; minute: string; second: string; millisecond: string;
  format: "compact14" | "compact17" | "spaced23";
};

function validDate(value: string): boolean { return dateCalendarValue(value) !== ""; }
function zeroDateTime(value: string): boolean { return value === "0".repeat(14) || value === "0".repeat(17); }

function parts(value: DateTimeEntryValue): DateTimeParts | null {
  if (value === null) return null;
  let compact: string, format: DateTimeParts["format"];
  if ((value.length === 14 || value.length === 17) && /^[0-9]+$/.test(value)) {
    compact = value; format = value.length === 14 ? "compact14" : "compact17";
  } else if (value.length === 23 && /^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}$/.test(value)) {
    compact = value.replaceAll(/[- :.]/g, ""); format = "spaced23";
  } else return null;
  const date = compact.slice(0, 8), hour = compact.slice(8, 10), minute = compact.slice(10, 12), second = compact.slice(12, 14);
  if (!validDate(date) || Number(hour) > 23 || Number(minute) > 59 || Number(second) > 59) return null;
  return { date, hour, minute, second, millisecond: compact.slice(14) || "000", format };
}

export function dateTimeEntryDisplay(value: DateTimeEntryValue): string {
  if (value === null || value === "") return "";
  if (zeroDateTime(value)) return "00/00/0000 00:00";
  const parsed = parts(value);
  if (!parsed) return value;
  return `${parsed.date.slice(6, 8)}/${parsed.date.slice(4, 6)}/${parsed.date.slice(0, 4)} ${parsed.hour}:${parsed.minute}`;
}

export function dateTimeEntryInitial(value: DateTimeEntryValue): DateTimeEntryDraft {
  return { original: value, text: dateTimeEntryDisplay(value), edited: false };
}

export function dateTimeEntryChange(draft: DateTimeEntryDraft, text: string): DateTimeEntryDraft {
  return { original: draft.original, text, edited: true };
}

export function dateTimeEntryResult(draft: DateTimeEntryDraft): DateTimeEntryResult {
  if (!draft.edited) return { kind: "valid", value: draft.original };
  if (draft.text === "") return { kind: "valid", value: "" };
  if (draft.text === "00/00/0000 00:00") return { kind: "valid", value: "0".repeat(14) };
  if (draft.text.length !== 16 || !/^[0-9]{2}\/[0-9]{2}\/[0-9]{4} [0-9]{2}:[0-9]{2}$/.test(draft.text)) return { kind: "invalid" };
  const date = `${draft.text.slice(6, 10)}${draft.text.slice(3, 5)}${draft.text.slice(0, 2)}`;
  const hour = draft.text.slice(11, 13), minute = draft.text.slice(14, 16);
  if (!validDate(date) || Number(hour) > 23 || Number(minute) > 59) return { kind: "invalid" };
  const original = parts(draft.original), second = original?.second ?? "00";
  if (original?.format === "spaced23") {
    return { kind: "valid", value: `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)} ${hour}:${minute}:${second}.${original.millisecond}` };
  }
  return { kind: "valid", value: `${date}${hour}${minute}${second}${original?.format === "compact17" ? original.millisecond : ""}` };
}

export function dateTimeCalendarValue(draft: DateTimeEntryDraft): string {
  const result = dateTimeEntryResult(draft), parsed = result.kind === "valid" ? parts(result.value) : null;
  return parsed ? dateCalendarValue(parsed.date) : "";
}

export function dateTimeCalendarChange(draft: DateTimeEntryDraft, iso: string): DateTimeEntryDraft {
  if (iso === "") return dateTimeEntryChange(draft, "");
  const localized = dateCalendarText(iso), result = dateTimeEntryResult(draft);
  const current = result.kind === "valid" ? parts(result.value) : null;
  return dateTimeEntryChange(draft, localized && current ? `${localized} ${current.hour}:${current.minute}` : draft.text);
}

export function dateTimeComparisonKey(value: DateTimeEntryValue): DateTimeEntryValue {
  if (value === null || value === "") return value;
  if (zeroDateTime(value)) return "0".repeat(17);
  const parsed = parts(value);
  return parsed ? `${parsed.date}${parsed.hour}${parsed.minute}${parsed.second}${parsed.millisecond}` : value;
}

export function isDateTimeBound(value: string): boolean { return value === "" || zeroDateTime(value) || parts(value) !== null; }

function isoDate(value: string): string | null {
  if (value.length !== 10 || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value)) return null;
  const compact = value.replaceAll("-", "");
  return validDate(compact) ? compact : null;
}

export function dateOnlyComparisonKey(value: DateTimeEntryValue): DateTimeEntryValue {
  return value === null ? null : isoDate(value) ?? value;
}

export function isDateOnlyBound(value: string): boolean {
  return value === "" || value === "00000000" || validDate(value) || isoDate(value) !== null;
}

function daysBeforeYear(year: number): number {
  const previous = year - 1;
  return previous * 365 + Math.floor(previous / 4) - Math.floor(previous / 100) + Math.floor(previous / 400);
}
function monthDays(year: number): number[] {
  return [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
}

export function shiftCalendarDate(compact8: string, days: number): string | null {
  if (!validDate(compact8) || !Number.isSafeInteger(days)) return null;
  const year = Number(compact8.slice(0, 4)), month = Number(compact8.slice(4, 6)), day = Number(compact8.slice(6, 8));
  const ordinal = daysBeforeYear(year) + monthDays(year).slice(0, month - 1).reduce((sum, count) => sum + count, 0) + day - 1 + days;
  if (!Number.isSafeInteger(ordinal) || ordinal < 0 || ordinal >= daysBeforeYear(10000)) return null;
  let low = 1, high = 10000;
  while (low + 1 < high) {
    const middle = Math.floor((low + high) / 2);
    if (daysBeforeYear(middle) <= ordinal) low = middle; else high = middle;
  }
  let remaining = ordinal - daysBeforeYear(low), targetMonth = 1;
  for (const count of monthDays(low)) { if (remaining < count) break; remaining -= count; targetMonth += 1; }
  return `${String(low).padStart(4, "0")}${String(targetMonth).padStart(2, "0")}${String(remaining + 1).padStart(2, "0")}`;
}
