export interface TableLayout { widths: Record<string, number>; order: string[]; hidden?: string[] }

export interface TableLayoutStore {
  load(key: string): TableLayout | null;
  save(key: string, layout: TableLayout): boolean;
}
