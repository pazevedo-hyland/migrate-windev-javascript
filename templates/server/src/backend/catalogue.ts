/**
 * The table/column catalogue the data layer and the importer check every identifier against. It is generated with the
 * schema (`tools/pg_schema.py` writes `src/shared/schema.generated.ts`) and installed once by `src/backend/index.ts`;
 * tests install their own. The catalogue plays the role of the WINDEV analysis (.wdd) at run time.
 */
export type ColumnKind =
  "text" | "integer" | "bigint" | "real" | "decimal" | "boolean" | "date" | "datetime" | "time" | "duration" | "binary";

export interface CatalogueColumn {
  name: string;
  /** The HFSQL item name, as in the analysis (case kept). */
  legacy?: string;
  kind: ColumnKind;
  size?: number;
  key?: "unique" | "duplicates" | null;
  caption?: string | null;
}

export interface CatalogueTable {
  /** The HFSQL file name, as in the analysis (case kept). */
  legacy?: string;
  /** Primary key column: the automatic identifier, or the technical `rowid_` when the file has none. */
  primary: string;
  columns: readonly CatalogueColumn[];
  keys?: readonly { name: string; columns: readonly string[]; unique: boolean }[];
}

export type Catalogue = Readonly<Record<string, CatalogueTable>>;

let current: Catalogue = {};

export function installCatalogue(next: Catalogue) {
  current = next;
}

export function catalogue(): Catalogue {
  return current;
}
