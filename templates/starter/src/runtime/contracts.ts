import type { ComponentProps, ReactNode } from "react";
import type { LegacyLayout, WdRadBinding, WdTable } from "@windev-migration/ui";

export interface ScreenDefinition { id: string; layout: LegacyLayout; source: string }
export type ScreenRow = Record<string, unknown>;
export type TableBinding = Omit<ComponentProps<typeof WdTable<ScreenRow>>, "control"> & { name: string };
export interface ScreenModel {
  bindings: readonly WdRadBinding[];
  tables?: readonly TableBinding[];
  status?: ReactNode;
}
/** Hooks and business operations are handwritten; generated files contain structure only. */
export type ScreenAdapter = (layout: LegacyLayout) => ScreenModel;
