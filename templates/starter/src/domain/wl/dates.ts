/**
 * WLanguage Date / Time / DateTime / Duration functions. Storage forms: dates "YYYY-MM-DD", times "HH:MM:SS[.mmm]",
 * date-times "YYYY-MM-DDTHH:MM:SS[.mmm]", durations as integer milliseconds. An empty WLanguage date ("" or
 * "00000000") is null in storage; these helpers accept every form. Local time, like WINDEV.
 */
const pad = (n: number, width = 2) => String(n).padStart(width, "0");

export const SECOND = 1000,
  MINUTE = 60 * SECOND,
  HOUR = 60 * MINUTE,
  DAY = 24 * HOUR;

/** An empty WLanguage date: null, "", or HFSQL's "00000000". */
export const isEmptyDate = (value: unknown) => value === null || value === undefined || value === "" || value === "00000000";

export const toIsoDate = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
export const toIsoTime = (date: Date, ms = true) =>
  `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}${ms ? "." + pad(date.getMilliseconds(), 3) : ""}`;
export const toIsoDateTime = (date: Date) => `${toIsoDate(date)}T${toIsoTime(date)}`;

/** Parses "YYYY-MM-DD[THH:MM[:SS[.mmm]]]" or the WINDEV form "YYYYMMDD[HHMMSS[mmm]]" as local time. */
export function parseDateTime(value: string): Date {
  const legacy = /^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2})(\d{0,3}))?$/.exec(value);
  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?)?$/.exec(value);
  const m = legacy ?? iso;
  if (!m) throw new Error(`Invalid date: ${value}`);
  return new Date(
    Number(m[1]),
    Number(m[2]) - 1,
    Number(m[3]),
    Number(m[4] ?? 0),
    Number(m[5] ?? 0),
    Number(m[6] ?? 0),
    Number((m[7] ?? "0").padEnd(3, "0")),
  );
}

/** DateSys() / Today() as an ISO date. */
export const today = (now: Date = new Date()) => toIsoDate(now);
/** The "DD/MM/YYYY" mask ("" for an empty date). Check the project's date masks: WINDEV takes them from the project. */
export function formatDate(value: unknown): string {
  if (isEmptyDate(value)) return "";
  const d = parseDateTime(String(value));
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}
/** "DD/MM/YYYY HH:MM[:SS]". */
export function formatDateTime(value: unknown, seconds = false): string {
  if (isEmptyDate(value)) return "";
  const d = parseDateTime(String(value));
  return `${formatDate(toIsoDate(d))} ${pad(d.getHours())}:${pad(d.getMinutes())}${seconds ? ":" + pad(d.getSeconds()) : ""}`;
}
/** A typed "D/M/YYYY" to an ISO date; null when it is not a real date (31/02). */
export function parseUserDate(input: string): string | null {
  const m = /^\s*(\d{1,2})\/(\d{1,2})\/(\d{4})\s*$/.exec(input);
  if (!m) return null;
  const d = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  return d.getMonth() === Number(m[2]) - 1 ? toIsoDate(d) : null;
}
/** MyDate..Day += n: rolls over months and years. */
export function addDays(isoDate: string, days: number): string {
  const d = parseDateTime(isoDate);
  d.setDate(d.getDate() + days);
  return toIsoDate(d);
}
/** MyDate..Month += n: the day is clamped to the target month's last day (31/05 - 3 months = 28/02). Assumed: confirm. */
export function addMonths(isoDate: string, months: number): string {
  const d = parseDateTime(isoDate);
  const target = new Date(d.getFullYear(), d.getMonth() + months, 1);
  const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(d.getDate(), last));
  return toIsoDate(target);
}
/** DateToDay(d): 1 = Monday … 7 = Sunday. */
export function dayOfWeek(isoDate: string): number {
  const n = parseDateTime(isoDate).getDay();
  return n === 0 ? 7 : n;
}
/** DateDifference(from, to): whole days (daylight-saving changes do not shift it). */
export function dateDifference(from: string, to: string): number {
  const a = parseDateTime(from),
    b = parseDateTime(to);
  return Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / DAY);
}

/** DateTimeDifference(from, to) as a Duration in ms. */
export const durationBetween = (from: string, to: string) => parseDateTime(to).getTime() - parseDateTime(from).getTime();
/** DateTime + Duration. */
export const addDuration = (isoDateTime: string, ms: number) => toIsoDateTime(new Date(parseDateTime(isoDateTime).getTime() + ms));
/** A Duration's ..Hour/..Minute/..Second/..Millisecond: truncated toward zero, the sign kept apart (hours include days). */
export function durationParts(ms: number) {
  const abs = Math.abs(ms);
  return {
    sign: ms < 0 ? -1 : 1,
    hours: Math.floor(abs / HOUR),
    minutes: Math.floor((abs % HOUR) / MINUTE),
    seconds: Math.floor((abs % MINUTE) / SECOND),
    milliseconds: abs % SECOND,
  };
}
/** "HH:MM" / "HH:MM:SS" display of a Duration. */
export function formatDurationClock(ms: number, seconds = false): string {
  const p = durationParts(ms);
  return `${p.sign < 0 ? "-" : ""}${pad(p.hours)}:${pad(p.minutes)}${seconds ? ":" + pad(p.seconds) : ""}`;
}
/** A Time "HH:MM[:SS[.mmm]]" as ms since midnight (0 for an empty or invalid time). */
export function timeToMs(value: string | null | undefined): number {
  if (!value) return 0;
  const m = /^(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/.exec(value.trim());
  if (!m) return 0;
  return Number(m[1]) * HOUR + Number(m[2]) * MINUTE + Number(m[3] ?? 0) * SECOND + Number((m[4] ?? "0").padEnd(3, "0"));
}
/** ms since midnight as a Time "HH:MM:SS.mmm" (wraps at 24 h). */
export function msToTime(ms: number): string {
  const p = durationParts(((ms % DAY) + DAY) % DAY);
  return `${pad(p.hours)}:${pad(p.minutes)}:${pad(p.seconds)}.${pad(p.milliseconds, 3)}`;
}
