import type { UserConfig } from "vite";
import { describe, expect, it } from "vitest";
import { createAssetResolver } from "@windev-migration/ui";
import config from "../../vite.config";

describe("production build", () => {
  it("never inlines assets as data: URLs, which the skin resolver refuses", () => {
    expect(() => createAssetResolver({ Button: { source: "data:image/png;base64,iVBORw0KGgo=" } })).toThrow(/same-origin/);
    expect((config as UserConfig).build?.assetsInlineLimit).toBe(0);
  });
});
