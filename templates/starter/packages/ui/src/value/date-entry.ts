export type DatePromptValue = string | null;
export type DateEntryDraft = { original: DatePromptValue; text: string; edited: boolean };
export type DateEntryResult = { kind: "valid"; value: DatePromptValue } | { kind: "invalid" };

function validGregorianDate(yearText: string, monthText: string, dayText: string): boolean {
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (year < 1 || year > 9999 || month < 1 || month > 12 || day < 1) return false;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day <= days[month - 1];
}

function validCompactDate(value: string): boolean {
  return value.length === 8 && /^[0-9]{8}$/.test(value)
    && validGregorianDate(value.slice(0, 4), value.slice(4, 6), value.slice(6, 8));
}

export function dateEntryDisplay(value: DatePromptValue): string {
  if (value === null || value === "") return "";
  if (value === "00000000") return "00/00/0000";
  if (!validCompactDate(value)) return value;
  return `${value.slice(6, 8)}/${value.slice(4, 6)}/${value.slice(0, 4)}`;
}

export function dateEntryInitial(value: DatePromptValue): DateEntryDraft {
  return { original: value, text: dateEntryDisplay(value), edited: false };
}

export function dateEntryChange(draft: DateEntryDraft, text: string): DateEntryDraft {
  return { original: draft.original, text, edited: true };
}

export function dateEntryResult(draft: DateEntryDraft): DateEntryResult {
  if (!draft.edited) return { kind: "valid", value: draft.original };
  if (draft.text === "") return { kind: "valid", value: "" };
  if (draft.text === "00/00/0000") return { kind: "valid", value: "00000000" };
  if (draft.text.length !== 10 || !/^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$/.test(draft.text)) return { kind: "invalid" };
  const day = draft.text.slice(0, 2);
  const month = draft.text.slice(3, 5);
  const year = draft.text.slice(6, 10);
  return validGregorianDate(year, month, day)
    ? { kind: "valid", value: `${year}${month}${day}` }
    : { kind: "invalid" };
}

export function dateCalendarValue(value: DatePromptValue): string {
  if (value === null || !validCompactDate(value)) return "";
  return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
}

export function dateCalendarText(iso: string): string | null {
  if (iso === "") return "";
  if (iso.length !== 10 || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(iso)) return null;
  const year = iso.slice(0, 4);
  const month = iso.slice(5, 7);
  const day = iso.slice(8, 10);
  return validGregorianDate(year, month, day) ? `${day}/${month}/${year}` : null;
}
