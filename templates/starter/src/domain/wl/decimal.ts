import Decimal from "decimal.js";

/**
 * Exact arithmetic for HFSQL Decimal / Currency items. Values are strings ("12.345") in storage and across IPC, never
 * JavaScript numbers. WLanguage Round(x, n) rounds half away from zero (Round(-2.5) = -3): ROUND_HALF_UP in decimal.js.
 */
const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_UP });
export type DecimalInput = string | number | Decimal | null | undefined;

/** A decimal from storage or input ("" and null = 0; "," accepted as the separator). */
export function dec(value: DecimalInput): Decimal {
  if (value === null || value === undefined || value === "") return new D(0);
  if (typeof value === "string") return new D(value.trim().replace(",", ".") || "0");
  return new D(value);
}
/** Canonical string for storage: no exponent, no trailing zeros ("1.50" -> "1.5"). */
export function decString(value: DecimalInput): string {
  const d = dec(value);
  return d.isZero() ? "0" : d.toFixed();
}
export const add = (...values: DecimalInput[]) => decString(values.reduce<Decimal>((sum, v) => sum.plus(dec(v)), new D(0)));
export const sub = (a: DecimalInput, b: DecimalInput) => decString(dec(a).minus(dec(b)));
export const mul = (a: DecimalInput, b: DecimalInput) => decString(dec(a).times(dec(b)));
/** a / b; 0 when b is 0. WLanguage raises an error on division by zero: check what the legacy code expects. */
export const div = (a: DecimalInput, b: DecimalInput) => decString(dec(b).isZero() ? 0 : dec(a).div(dec(b)));
/** Round(x, n). */
export const round = (value: DecimalInput, places = 0) => decString(dec(value).toDecimalPlaces(places, D.ROUND_HALF_UP));
export const cmp = (a: DecimalInput, b: DecimalInput) => dec(a).comparedTo(dec(b));
export const isZero = (value: DecimalInput) => dec(value).isZero();

/** The Windows regional decimal separator (WINDEV numeric displays follow it); "," when it cannot be read. */
export function systemDecimalSeparator(): "," | "." {
  try {
    return new Intl.NumberFormat().formatToParts(1.5).find((part) => part.type === "decimal")?.value === "." ? "." : ",";
  } catch {
    return ",";
  }
}
/** Display like a numeric mask: fixed places when given, with the given separator (the UI kit's decimalSeparator()). */
export function formatDecimal(value: DecimalInput, places?: number, separator: "," | "." = ","): string {
  const d = dec(value);
  const fixed = places === undefined ? d.toFixed() : d.toFixed(places, D.ROUND_HALF_UP);
  return separator === "," ? fixed.replace(".", ",") : fixed;
}
