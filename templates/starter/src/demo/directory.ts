import { useState } from "react";
import { useDialogs } from "@windev-migration/ui";
import type { ScreenModel, ScreenRow } from "../runtime/contracts";

const initial: ScreenRow[] = [{ id: "9007199254740993", name: "Example association", active: true }, { id: "9007199254740994", name: "Sample library", active: false }];

/** Synthetic, in-memory example. Replace with the project's real application/repository boundary. */
export function useDemoDirectory(): ScreenModel {
  const [rows, setRows] = useState(initial);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [active, setActive] = useState(true);
  const [status, setStatus] = useState("Demo data in memory; nothing is saved to a database.");
  const dialogs = useDialogs();
  const select = (id: string) => {
    const row = rows.find(item => item.id === id)!;
    setSelectedId(id); setName(String(row.name)); setActive(row.active === true);
  };
  return {
    bindings: [
      { name: "WIN_Directory.EDT_Name", kind: "edit", props: { value: name, onChange: event => setName(event.currentTarget.value) } },
      { name: "WIN_Directory.CBOX_Active", kind: "checkbox", props: { checked: active, onChange: setActive } },
      { name: "WIN_Directory.BTN_New", kind: "button", props: { onClick: () => { setSelectedId(null); setName(""); setActive(true); } } },
      { name: "WIN_Directory.BTN_Save", kind: "button", props: { disabled: !name.trim(), onClick: () => {
        const id = selectedId ?? crypto.randomUUID();
        const row = { id, name: name.trim(), active };
        setRows(previous => selectedId ? previous.map(item => item.id === id ? row : item) : [...previous, row]);
        setSelectedId(id); setStatus("Saved in demo memory only.");
      } } },
      { name: "WIN_Directory.BTN_Delete", kind: "button", props: { disabled: !selectedId, onClick: async () => {
        const id = selectedId;
        if (await dialogs.message({ title: "Remove demo entry", text: `Remove ${name}?`, type: 2, destructive: true }) !== 6) return;
        setRows(previous => previous.filter(item => item.id !== id)); setSelectedId(null); setName(""); setStatus("Removed from demo memory.");
      } } },
    ],
    tables: [{ name: "WIN_Directory.TABLE_Entries", rows, rowId: row => String(row.id), selectedId, onSelect: select,
      cell: (row, column) => column.name === "COL_Active" ? (row.active ? "Yes" : "No") : String(row[column.name === "COL_Name" ? "name" : "id"] ?? "") }],
    status,
  };
}
