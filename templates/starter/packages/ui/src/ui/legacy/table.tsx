import { getCoreRowModel, useReactTable, type ColumnSizingState } from "@tanstack/react-table";
import { observeElementOffset, useVirtualizer } from "@tanstack/react-virtual";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent, type ReactNode } from "react";
import { controlBox, type LegacyColumn, type LegacyControl } from "./layout";
import "./skin.css";
import { useUiConfig } from "../../config";
import { useAnchoredControl } from "./anchors";

export function WdTable<T>({ control: sourceControl, rows, rowId, cell, selectedId, onSelect, onActivate, onSort, onColumnSearch, rowHeight, showHeaders = true, configureColumns = false, designerOptions = false, hiddenColumns = [], onHiddenColumnsChange, onResetColumns, columnWidths, onColumnWidthsChange, columnOrder, onColumnOrderChange }: {
  control: LegacyControl; rows: T[]; rowId: (row: T) => string;
  cell: (row: T, column: LegacyColumn) => ReactNode;
  selectedId: string | null; onSelect: (id: string) => void;
  onActivate?: (id: string) => void; onSort?: (column: LegacyColumn) => void;
  onColumnSearch?: (column: LegacyColumn, term: string) => void;
  configureColumns?: boolean; hiddenColumns?: string[]; onHiddenColumnsChange?: (hidden: string[]) => void;
  onResetColumns?: () => void;
  designerOptions?: boolean; rowHeight?: number; showHeaders?: boolean;
  columnWidths?: ColumnSizingState; onColumnWidthsChange?: (widths: ColumnSizingState) => void;
  columnOrder?: string[]; onColumnOrderChange?: (order: string[]) => void;
}) {
  const config = useUiConfig();
  const [localWidths, setLocalWidths] = useState<ColumnSizingState>({});
  const widths = columnWidths ?? localWidths;
  const [localOrder, setLocalOrder] = useState<string[]>([]);
  const [searchColumn, setSearchColumn] = useState<string | null>(null), [searchTerm, setSearchTerm] = useState("");
  const [configurationOpen, setConfigurationOpen] = useState(false);
  const order = columnOrder ?? localOrder;
  const draggedColumn = useRef<string | null>(null), keyboardFocus = useRef<HTMLElement | null>(null);
  useEffect(() => { keyboardFocus.current?.focus(); keyboardFocus.current = null; }, [order]);
  if ((columnOrder == null) !== (onColumnOrderChange == null)) throw new Error("Controlled column order requires both state and callback");
  if ((columnWidths == null) !== (onColumnWidthsChange == null)) throw new Error("Controlled column widths require both state and callback");
  const control = useAnchoredControl(sourceControl);
  if (!control.columns) throw new Error(`Table columns unresolved: ${control.path}`);
  const sourceColumns = control.columns;
  const container = useRef<HTMLDivElement>(null);
  const duplicateIds = useMemo(() => {
    const ids = rows.map(rowId); return new Set(ids).size !== ids.length;
  }, [rows, rowId]);
  if (duplicateIds) throw new Error(`Duplicate table row identity: ${control.path}`);
  const columns = useMemo(() => sourceColumns.filter(column => column.flags?.Visible !== false).map(column => {
    if (column.width == null) throw new Error(`Column width unresolved: ${column.path}`);
    return { id: column.path, size: column.width, minSize: Math.min(24, column.width),
      maxSize: Number.MAX_SAFE_INTEGER, enableResizing: column.flags?.["Adjustable width"] === true };
  }), [sourceColumns]);
  const table = useReactTable({ data: rows, columns, getRowId: rowId, getCoreRowModel: getCoreRowModel(),
    manualSorting: true, autoResetAll: false, enableRowSelection: false, columnResizeMode: "onChange", state: { columnSizing: widths, columnOrder: order, columnVisibility: Object.fromEntries(hiddenColumns.map(key => [key, false])) },
    onColumnOrderChange: update => {
      if (onColumnOrderChange) onColumnOrderChange(typeof update === "function" ? update(order) : update);
      else setLocalOrder(update);
    },
    onColumnSizingChange: update => {
      if (onColumnWidthsChange) onColumnWidthsChange(typeof update === "function" ? update(widths) : update);
      else setLocalWidths(update);
    } });
  const displayed = table.getRowModel().rows;
  const options = designerOptions ? control.table_options : undefined;

  const sourceRowHeight = options?.row_height && /^[0-9]+$/.test(options.row_height) ? Number(options.row_height) + 1 : undefined;
  const effectiveRowHeight = rowHeight ?? sourceRowHeight;

  const virtualized = displayed.length > 500;
  const header = useRef<HTMLTableSectionElement>(null), [measuredHeaderHeight, setMeasuredHeaderHeight] = useState(23);
  const firstRow = useRef<HTMLTableRowElement>(null);
  const requestedRowHeight = effectiveRowHeight ?? 19;
  const [measuredRowHeight, setMeasuredRowHeight] = useState<{ requested: number; actual: number } | null>(null);
  const itemHeight = measuredRowHeight?.requested === requestedRowHeight ? measuredRowHeight.actual : requestedRowHeight;
  const headerHeight = showHeaders ? measuredHeaderHeight : 0;
  useLayoutEffect(() => {
    const element = header.current;
    if (!virtualized || !showHeaders || !element) return;
    const update = () => setMeasuredHeaderHeight(element.getBoundingClientRect().height);
    update();
    const observer = new ResizeObserver(update); observer.observe(element);
    return () => observer.disconnect();
  }, [virtualized, showHeaders]);
  const itemKey = useCallback((index: number) => displayed[index].id, [displayed]);
  // Hidden hosts report zero offsets without changing their retained native scroll position.
  const observeOffset = useCallback<typeof observeElementOffset>((instance, notify) => observeElementOffset(instance, (offset, scrolling) => {
    if (instance.scrollElement && instance.scrollElement.clientHeight > 0) notify(offset, scrolling);
  }), []);
  const virtualizer = useVirtualizer({ count: displayed.length, getScrollElement: () => container.current,
    estimateSize: () => itemHeight, getItemKey: itemKey, enabled: virtualized,
    overscan: 8, paddingStart: headerHeight, scrollPaddingStart: headerHeight, useFlushSync: false, observeElementOffset: observeOffset });
  const virtualRows = virtualizer.getVirtualItems();
  const rendered = virtualized ? virtualRows.map(item => displayed[item.index]) : displayed;
  const topSpace = virtualized && virtualRows.length ? virtualRows[0].start - headerHeight : 0;
  // Keep the full scroll extent while observers initialize or a window is restored.
  const bottomSpace = virtualized ? virtualizer.getTotalSize() - (virtualRows.at(-1)?.end ?? headerHeight) : 0;
  const firstRenderedId = rendered[0]?.id;
  useLayoutEffect(() => {
    const element = firstRow.current;
    if (!virtualized || !element) return;
    const update = () => {
      const actual = element.getBoundingClientRect().height;
      if (actual > 0) setMeasuredRowHeight(previous => previous?.requested === requestedRowHeight && previous.actual === actual ? previous : { requested: requestedRowHeight, actual });
    };
    update();
    const observer = new ResizeObserver(update); observer.observe(element);
    return () => observer.disconnect();
  }, [virtualized, requestedRowHeight, firstRenderedId]);
  useLayoutEffect(() => {
    if (virtualized) virtualizer.measure();
  }, [virtualized, virtualizer, itemHeight]);
  useEffect(() => {
    if (virtualized) {
      const index = displayed.findIndex(row => row.id === selectedId);
      if (index >= 0) virtualizer.scrollToIndex(index, { align: "auto" });
    } else container.current?.querySelector('tr[aria-selected="true"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selectedId, rows, displayed, virtualized, virtualizer, headerHeight, itemHeight]);
  const scrollbarMode = (value: string | undefined) => value === "Always visible" ? "scroll" as const : value === "Automatic" ? "auto" as const : undefined;
  const columnOf = (id: string) => sourceColumns.find(column => column.path === id)!;
  const moveColumn = (from: string, to: string) => {
    const next = table.getAllLeafColumns().map(column => column.id), start = next.indexOf(from), end = next.indexOf(to);
    if (start < 0 || end < 0 || start === end) return false;
    if (next.slice(Math.min(start, end), Math.max(start, end) + 1).some(id => columnOf(id).flags?.Movable !== true || columnOf(id).flags?.["Fixed left"] === true)) return false;
    next.splice(start, 1); next.splice(end, 0, from); table.setColumnOrder(next); return true;
  };
  return <div ref={container} data-testid={control.name} data-control-path={control.path} className={`wd-table${designerOptions ? " wd-table-designer" : ""}`}
    onContextMenu={event => {
      if (showHeaders || !configureColumns || options?.column_context_menu !== "Yes" || !onHiddenColumnsChange) return;
      event.preventDefault(); setConfigurationOpen(true);
    }}
    hidden={(control.visible ?? control.flags?.Visible) === false} style={{ ...controlBox(control), ...(effectiveRowHeight ? { backgroundImage: `repeating-linear-gradient(to bottom, transparent 0 ${effectiveRowHeight - 1}px, #e0e2e4 ${effectiveRowHeight - 1}px ${effectiveRowHeight}px)` } : {}), overflowY: scrollbarMode(options?.vertical_scrollbar), overflowX: scrollbarMode(options?.horizontal_scrollbar), touchAction: options?.touch_scrolling === "No" ? "none" : undefined }} tabIndex={String(control.tab_order) === "-1" ? -1 : 0}
    onKeyDown={event => {
      if (event.target !== event.currentTarget) return;
      const index = displayed.findIndex(row => row.id === selectedId);
      if (event.key === "Enter" && index >= 0 && onActivate) { event.preventDefault(); onActivate(displayed[index].id); }

      const next = index + (event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0);
      if (index >= 0 && next !== index && next >= 0 && next < displayed.length) {
        event.preventDefault(); onSelect(displayed[next].id);
      }
    }}>
    {configureColumns && control.flags?.["Saves col. config."] === true && onHiddenColumnsChange && <div className="wd-table-tools"
      onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setConfigurationOpen(false); container.current?.focus(); } }}>
      <button hidden={!showHeaders} type="button" data-testid={`${control.name}__columns`} aria-label={config.labels.columns} aria-expanded={configurationOpen} onClick={() => setConfigurationOpen(value => !value)}>▾</button>
      {configurationOpen && <div className="wd-column-settings" role="group" aria-label={config.labels.columns}>
        {table.getAllLeafColumns().map(column => <label key={column.id}><input type="checkbox" checked={column.getIsVisible()}
          disabled={column.getIsVisible() && table.getVisibleLeafColumns().length === 1}
          onChange={event => {
            if (searchColumn === column.id && !event.target.checked) { setSearchColumn(null); onColumnSearch?.(columnOf(column.id), ""); }
            onHiddenColumnsChange(event.target.checked ? hiddenColumns.filter(key => key !== column.id) : [...hiddenColumns, column.id]);
          }} />{columnOf(column.id).title}</label>)}
        {onResetColumns && <button type="button" onClick={() => { onResetColumns(); setConfigurationOpen(false); container.current?.focus(); }}>{config.labels.resetColumns}</button>}
      </div>}
    </div>}
    <div className="wd-table-grid" aria-hidden="true" style={{ width: table.getTotalSize(), top: showHeaders ? undefined : 0 }}>
      {table.getVisibleLeafColumns().map(column => <span key={column.id} style={{ width: column.getSize() }} />)}
    </div>
    <table aria-label={control.caption ?? control.name} aria-rowcount={virtualized ? displayed.length + (showHeaders ? 1 : 0) : undefined} style={{ width: table.getTotalSize() }}>
      <colgroup>{table.getVisibleLeafColumns().map(column => <col key={column.id} style={{ width: column.getSize() }} />)}</colgroup>
      <thead ref={header} hidden={!showHeaders}>{table.getHeaderGroups().map(group => <tr key={group.id}>{group.headers.map(header => {
        const column = header.column;
        const source = columnOf(column.id);
        const movable = source.flags?.Movable === true && source.flags?.["Fixed left"] !== true;
        const captionProps = { draggable: movable,
          onMouseEnter: (event: MouseEvent<HTMLElement>) => {
            const element = event.currentTarget;
            if (options?.truncated_tooltip === "Yes" && element.scrollWidth > element.clientWidth) element.title = element.textContent ?? "";
            else element.removeAttribute("title");
          },
          onMouseLeave: (event: MouseEvent<HTMLElement>) => event.currentTarget.removeAttribute("title"),
          onDragStart: (event: DragEvent<HTMLElement>) => { draggedColumn.current = column.id; event.dataTransfer.setData("text/plain", column.id); event.dataTransfer.effectAllowed = "move"; },
          onDragEnd: () => { draggedColumn.current = null; } };
        return <th key={column.id} scope="col" data-testid={source.name} data-control-path={source.path}
          onContextMenu={event => {
            if (!configureColumns || options?.column_context_menu !== "Yes" || !onHiddenColumnsChange) return;
            event.preventDefault(); setConfigurationOpen(true);
          }}
          onDragOver={event => { if (draggedColumn.current) event.preventDefault(); }}
          onDrop={event => { event.preventDefault(); if (draggedColumn.current) moveColumn(draggedColumn.current, column.id); draggedColumn.current = null; }}
          onKeyDown={event => {
            if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
            event.preventDefault(); event.stopPropagation();
            const ids = table.getAllLeafColumns().map(item => item.id), index = ids.indexOf(column.id);
            const target = ids[index + (event.key === "ArrowLeft" ? -1 : 1)];
            keyboardFocus.current = null;
            if (target && moveColumn(column.id, target)) keyboardFocus.current = event.target as HTMLElement;
          }}>
          {searchColumn === column.id ? <input autoFocus className="wd-column-search-input" aria-label={`${config.labels.search} ${source.title ?? source.name}`} value={searchTerm}
            onChange={event => { setSearchTerm(event.target.value); onColumnSearch?.(source, event.target.value); }}
            onKeyDown={event => {
              if (event.key !== "Escape" && event.key !== "Enter") return;
              event.preventDefault(); event.stopPropagation(); setSearchColumn(null);
              if (event.key === "Escape") onColumnSearch?.(source, "");
              container.current?.focus();
            }} /> : <>
            {onSort && source.flags?.["Sortable column"] === true
              ? <button {...captionProps} className={onColumnSearch && source.flags?.["With search"] ? "wd-searchable-caption" : undefined} type="button" onClick={() => onSort(source)}>{source.title}</button> : <span {...captionProps} tabIndex={movable ? 0 : undefined} className="wd-column-caption">{source.title}</span>}
            {onColumnSearch && source.flags?.["With search"] === true && <button type="button" className="wd-column-search" data-testid={`${source.name}__search`} aria-label={`${config.labels.search} ${source.title ?? source.name}`}
              onClick={() => { setSearchColumn(column.id); setSearchTerm(""); onColumnSearch(source, ""); }}><span aria-hidden="true" /></button>}
          </>}
          {column.getCanResize() && <span role="separator" aria-orientation="vertical" aria-label={source.title ?? source.name}
            aria-valuenow={column.getSize()} aria-valuemin={Math.min(24, source.width!)} aria-valuemax={Number.MAX_SAFE_INTEGER} aria-valuetext={`${column.getSize()} px`} tabIndex={0} data-testid={`${source.name}__resize`} className="wd-column-resize"
            onMouseDown={header.getResizeHandler()} onTouchStart={header.getResizeHandler()}
            onKeyDown={event => {
              if (!["ArrowLeft", "ArrowRight"].includes(event.key) || event.altKey || event.ctrlKey || event.metaKey) return;
              event.preventDefault(); event.stopPropagation();
              const delta = (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 1 : 8);
              table.setColumnSizing(previous => ({ ...previous, [column.id]: Math.max(Math.min(24, source.width!), column.getSize() + delta) }));
            }} />}
        </th>;
      })}</tr>)}</thead>
      <tbody>{topSpace > 0 && <tr aria-hidden="true"><td colSpan={table.getVisibleLeafColumns().length} style={{ height: topSpace, padding: 0, border: 0 }} /></tr>}
      {rendered.map((row, index) => <tr key={row.id} ref={virtualized && index === 0 ? firstRow : undefined} aria-selected={row.id === selectedId}
        aria-rowindex={virtualized ? virtualRows[index].index + (showHeaders ? 2 : 1) : undefined}
        onClick={() => { container.current?.focus(); onSelect(row.id); }} onDoubleClick={() => onActivate?.(row.id)}>
        {row.getVisibleCells().map(value => {
          const source = columnOf(value.column.id);
          return <td key={value.id} style={{ height: effectiveRowHeight, textAlign: source.h_align === "Right" ? "right" : source.h_align === "Center" ? "center" : "left" }}
            onMouseEnter={event => {
              const element = event.currentTarget;
              if (options?.truncated_tooltip === "Yes" && element.scrollWidth > element.clientWidth) element.title = element.textContent ?? "";
              else element.removeAttribute("title");
            }} onMouseLeave={event => event.currentTarget.removeAttribute("title")}>{cell(row.original, source)}</td>;
        })}
      </tr>)}
      {bottomSpace > 0 && <tr aria-hidden="true"><td colSpan={table.getVisibleLeafColumns().length} style={{ height: bottomSpace, padding: 0, border: 0 }} /></tr>}</tbody>
    </table>
  </div>;
}
