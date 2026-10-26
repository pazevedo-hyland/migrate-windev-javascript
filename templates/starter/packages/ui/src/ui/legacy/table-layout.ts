import { useEffect, useRef, useState } from "react";
import type { TableLayout, TableLayoutStore } from "../../application/table-layout";
import { useUiConfig } from "../../config";
import type { LegacyColumn, LegacyControl } from "./layout";

export function reconcileTableLayout(saved: TableLayout | null, columns: LegacyColumn[]): TableLayout {
  const visible = columns.filter(column => column.flags?.Visible !== false), allowed = new Set(visible.map(column => column.path));
  const widths = Object.fromEntries(Object.entries(saved?.widths ?? {}).filter(([key]) => allowed.has(key)));
  const rank = new Map((saved?.order ?? []).map((key, index) => [key, index]));
  const order: string[] = [], segment: LegacyColumn[] = [];
  const flush = () => {
    segment.sort((a, b) => (rank.get(a.path) ?? Infinity) - (rank.get(b.path) ?? Infinity));
    order.push(...segment.map(column => column.path)); segment.length = 0;
  };
  for (const column of visible) {
    if (column.flags?.Movable === true && column.flags?.["Fixed left"] !== true) segment.push(column);
    else { flush(); order.push(column.path); }
  }
  flush();
  const hidden = (saved?.hidden ?? []).filter(key => allowed.has(key));

  if (hidden.length === visible.length) hidden.pop();
  return { widths, order, ...(hidden.length ? { hidden } : {}) };
}

export function useTableLayout(control: LegacyControl, settingsKey: string, storeOverride?: TableLayoutStore) {
  const config = useUiConfig();
  const store = storeOverride ?? config.tableLayoutStore;
  if (!settingsKey || !control.columns) throw new Error("Table layout requires a qualified settings key and source columns");
  const enabled = control.flags?.["Saves col. config."] === true;
  const [layout, setLayout] = useState(() => reconcileTableLayout(enabled ? store.load(settingsKey) : null, control.columns!));
  const dirty = useRef(false);
  useEffect(() => { if (enabled && dirty.current) store.save(settingsKey, layout); }, [enabled, layout, settingsKey, store]);
  return {
    columnWidths: layout.widths, columnOrder: layout.order, hiddenColumns: layout.hidden ?? [],
    onColumnWidthsChange: (widths: Record<string, number>) => { dirty.current = true; setLayout(previous => ({ ...previous, widths })); },
    onColumnOrderChange: (order: string[]) => { dirty.current = true; setLayout(previous => ({ ...previous, order })); },
    onHiddenColumnsChange: (hidden: string[]) => { dirty.current = true; setLayout(previous => reconcileTableLayout({ ...previous, hidden }, control.columns!)); },
    resetLayout: () => { dirty.current = true; setLayout(reconcileTableLayout(null, control.columns!)); },
  };
}
