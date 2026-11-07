/**
 * WLanguage string functions with their WINDEV semantics. Pure functions, no I/O. Positions are 1-based like WLanguage.
 * Confirm each one you use against the legacy app (golden values) before relying on it: see chapter 09 (WLanguage traps).
 */
const text = (value: unknown) => String(value ?? "");

/** NoSpace(s): removes leading and trailing spaces (default sNoSpace on both sides). */
export const noSpace = (value: unknown) => text(value).trim();
/** Contains(s, part): case-sensitive unless `ignoreCase` (WLanguage IgnoreCase). */
export const contains = (value: unknown, part: string, ignoreCase = false) =>
  ignoreCase ? text(value).toLowerCase().includes(part.toLowerCase()) : text(value).includes(part);
/** Position(s, part[, start]): 1-based position of `part`, 0 when not found. */
export function position(value: unknown, part: string, start = 1): number {
  const index = text(value).indexOf(part, Math.max(0, start - 1));
  return index < 0 ? 0 : index + 1;
}
/** Left(s, n). */
export const left = (value: unknown, n: number) => text(value).slice(0, Math.max(0, n));
/** Right(s, n). */
export const right = (value: unknown, n: number) => (n <= 0 ? "" : text(value).slice(-n));
/** Middle(s, start[, length]): 1-based start; without length, to the end. */
export const middle = (value: unknown, start: number, length?: number) => {
  const from = Math.max(0, start - 1);
  return length === undefined ? text(value).slice(from) : text(value).slice(from, from + Math.max(0, length));
};
/** Upper(s) / Lower(s). */
export const upper = (value: unknown) => text(value).toUpperCase();
export const lower = (value: unknown) => text(value).toLowerCase();
/** Val(s): the leading numeric part, 0 when there is none ("12,5kg" -> 12.5; "," or "." as decimal separator). */
export function val(value: unknown): number {
  const match = /^\s*[-+]?\d*(?:[.,]\d+)?/.exec(text(value));
  const n = match ? Number(match[0].replace(",", ".")) : 0;
  return Number.isFinite(n) ? n : 0;
}
/**
 * NumToString(n, format) for the integer and fixed formats: "02d" (zero-padded), "3d" (space-padded), ".2f" / "5.2f".
 * Other formats return String(n): add them, with tests, when the legacy code uses them.
 */
export function numToString(value: number, format?: string): string {
  if (!format) return String(value);
  const integer = /^0?(\d+)d$/.exec(format);
  if (integer) return String(Math.trunc(value)).padStart(Number(integer[1]), format.startsWith("0") ? "0" : " ");
  const fixed = /^\d*\.(\d+)f$/.exec(format);
  if (fixed) return value.toFixed(Number(fixed[1]));
  return String(value);
}
/** HFSQL key comparison: trailing spaces are ignored; case-sensitive unless the index says otherwise. */
export const sameKey = (a: unknown, b: unknown) => text(a).trimEnd() === text(b).trimEnd();
