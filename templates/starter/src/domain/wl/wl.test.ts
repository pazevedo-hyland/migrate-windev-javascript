import { describe, expect, it } from "vitest";
import {
  add,
  addDays,
  addMonths,
  completeDir,
  contains,
  dateDifference,
  dayOfWeek,
  decString,
  durationBetween,
  durationParts,
  fileExtension,
  fileName,
  formatDate,
  formatDecimal,
  formatDurationClock,
  middle,
  msToTime,
  noSpace,
  numToString,
  parentDir,
  parseUserDate,
  position,
  right,
  round,
  sameKey,
  sub,
  timeToMs,
  val,
} from "./index";

describe("strings", () => {
  it("1-based positions and WINDEV defaults", () => {
    expect(noSpace("  a b  ")).toBe("a b");
    expect(position("abcabc", "c")).toBe(3);
    expect(position("abcabc", "c", 4)).toBe(6);
    expect(position("abc", "x")).toBe(0);
    expect(middle("abcdef", 2, 3)).toBe("bcd");
    expect(middle("abcdef", 4)).toBe("def");
    expect(right("abc", 0)).toBe("");
    expect(contains("Abc", "ab")).toBe(false);
    expect(contains("Abc", "ab", true)).toBe(true);
    expect(sameKey("A01  ", "A01")).toBe(true);
  });
  it("Val and NumToString", () => {
    expect(val("12,5kg")).toBe(12.5);
    expect(val("abc")).toBe(0);
    expect(numToString(7, "02d")).toBe("07");
    expect(numToString(7, "3d")).toBe("  7");
    expect(numToString(2.5, ".2f")).toBe("2.50");
  });
});

describe("decimals", () => {
  it("are exact and Round goes half away from zero", () => {
    expect(add("0.1", "0.2")).toBe("0.3");
    expect(sub("5", "7.25")).toBe("-2.25");
    expect(round("2.345", 2)).toBe("2.35");
    expect(round("-2.5", 0)).toBe("-3");
    expect(decString("1.50")).toBe("1.5");
    expect(formatDecimal("1234.5", 2)).toBe("1234,50");
    expect(formatDecimal("1234.5", 2, ".")).toBe("1234.50");
  });
});

describe("dates and durations", () => {
  it("dates", () => {
    expect(formatDate("2026-11-07")).toBe("07/11/2026");
    expect(formatDate("20261107")).toBe("07/11/2026");
    expect(formatDate("00000000")).toBe("");
    expect(parseUserDate("31/02/2026")).toBeNull();
    expect(parseUserDate("1/3/2026")).toBe("2026-03-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addMonths("2026-05-31", -3)).toBe("2026-02-28");
    expect(dayOfWeek("2026-11-08")).toBe(7);
    expect(dateDifference("2026-03-28", "2026-03-30")).toBe(2);
  });
  it("durations in ms", () => {
    expect(durationBetween("2026-11-05T08:00:00", "2026-11-05T09:15:20.600")).toBe(4520600);
    expect(durationParts(-(25 * 3600000 + 61000))).toEqual({ sign: -1, hours: 25, minutes: 1, seconds: 1, milliseconds: 0 });
    expect(formatDurationClock(4520600, true)).toBe("01:15:20");
    expect(timeToMs("06:30")).toBe(23400000);
    expect(msToTime(-1000)).toBe("23:59:59.000");
  });
});

describe("paths", () => {
  it("fExtractPath and CompleteDir", () => {
    expect(completeDir("C:\\App")).toBe("C:\\App\\");
    expect(completeDir("")).toBe("");
    expect(fileName("C:\\App\\Labels\\model.v2.wde")).toBe("model.v2");
    expect(fileExtension("C:\\App\\report.PDF")).toBe(".PDF");
    expect(fileExtension("C:\\App\\.hidden")).toBe("");
    expect(parentDir("C:\\App\\report.pdf")).toBe("C:\\App");
  });
});
