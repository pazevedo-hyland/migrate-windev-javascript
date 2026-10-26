import { useEffect, useRef, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { DialogProvider, UiProvider, useDialogs } from "@windev-migration/ui";

// Test-only HTTP consumer. Its records live in the test server's scratch SQLite database.
type Entity = "members" | "rooms";
type Field = { key: string; label: string; kind: "text" | "email" | "checkbox" | "textarea"; inputMode?: "numeric" };
type FixtureRow = { id: string } & Record<string, string | boolean>;
type Draft = Record<string, string | boolean>;
interface EditorState { id: string | null; draft: Draft }
const definitions: Record<Entity, { title: string; singular: string; fields: Field[]; empty: Draft }> = {
  members: { title: "Members", singular: "member", fields: [
    { key: "name", label: "Name", kind: "text" },
    { key: "email", label: "Email", kind: "email" },
    { key: "active", label: "Active", kind: "checkbox" },
  ], empty: { name: "", email: "", active: false } },
  rooms: { title: "Rooms", singular: "room", fields: [
    { key: "code", label: "Code", kind: "text" },
    { key: "capacity", label: "Capacity", kind: "text", inputMode: "numeric" },
    { key: "notes", label: "Notes", kind: "textarea" },
  ], empty: { code: "", capacity: "", notes: "" } },
};

async function request(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, init);
  const text = await response.text();
  let data: unknown;
  try { data = text ? JSON.parse(text) : null; }
  catch { throw new Error(`Invalid API response (${response.status})`); }
  if (!response.ok) {
    const message = data && typeof data === "object" && "error" in data && typeof data.error === "string" ? data.error : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}
function readRow(value: unknown, fields: Field[]): FixtureRow {
  if (!value || typeof value !== "object" || !("id" in value) || typeof value.id !== "string") throw new Error("API record identity must be a string");
  const result: FixtureRow = { id: value.id };
  for (const field of fields) {
    const data = (value as Record<string, unknown>)[field.key];
    if (typeof data !== (field.kind === "checkbox" ? "boolean" : "string")) throw new Error(`Invalid API field: ${field.key}`);
    result[field.key] = data as string | boolean;
  }
  return result;
}
const errorText = (error: unknown) => error instanceof Error ? error.message : "Request failed";

function RecordEditor({ entity, editor, pending, error, onChange, onSave, onCancel }: {
  entity: Entity; editor: EditorState; pending: boolean; error: string;
  onChange: (key: string, value: string | boolean) => void; onSave: () => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null), definition = definitions[entity];
  useEffect(() => { const element = dialog.current!; element.showModal(); return () => element.close(); }, []);
  const submit = (event: FormEvent) => { event.preventDefault(); if (!pending) onSave(); };
  return <dialog ref={dialog} data-testid="record-editor" aria-label={`${editor.id === null ? "New" : "Edit"} ${definition.singular}`}
    className="fixture-editor" onCancel={event => { event.preventDefault(); if (!pending) onCancel(); }}>
    <form noValidate onSubmit={submit} aria-busy={pending}>
      <h2>{editor.id === null ? "New" : "Edit"} {definition.singular}</h2>
      <p className="fixture-id">ID: <output data-testid="record-id">{editor.id ?? "new"}</output></p>
      {definition.fields.map((field, index) => <label key={field.key} htmlFor={`field-${field.key}`} className={field.kind === "checkbox" ? "fixture-checkbox" : "fixture-field"}>
        <span>{field.label}</span>
        {field.kind === "checkbox" ? <input id={`field-${field.key}`} data-testid={`field-${field.key}`} type="checkbox"
          checked={editor.draft[field.key] === true} disabled={pending} onChange={event => onChange(field.key, event.currentTarget.checked)} />
          : field.kind === "textarea" ? <textarea id={`field-${field.key}`} data-testid={`field-${field.key}`} value={String(editor.draft[field.key] ?? "")}
            disabled={pending} onChange={event => onChange(field.key, event.currentTarget.value)} />
            : <input id={`field-${field.key}`} data-testid={`field-${field.key}`} type={field.kind} inputMode={field.inputMode}
              autoFocus={index === 0} value={String(editor.draft[field.key] ?? "")} disabled={pending}
              onChange={event => onChange(field.key, event.currentTarget.value)} />}
      </label>)}
      {error && <p role="alert" data-testid="form-error">{error}</p>}
      <div className="fixture-actions">
        <button type="submit" data-testid="save-record" disabled={pending}>Save</button>
        <button type="button" data-testid="cancel-record" disabled={pending} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  </dialog>;
}

function Fixture({ entity }: { entity: Entity }) {
  const definition = definitions[entity], endpoint = `/__workflow_fixture/api/${entity}`, dialogs = useDialogs();
  const [rows, setRows] = useState<FixtureRow[]>([]), [selectedId, select] = useState<string | null>(null);
  const [search, setSearch] = useState(""), [editor, setEditor] = useState<EditorState | null>(null);
  const [loading, setLoading] = useState(true), [pending, setPending] = useState(false);
  const [listError, setListError] = useState(""), [formError, setFormError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void request(endpoint, { signal: controller.signal }).then(value => {
      if (!Array.isArray(value)) throw new Error("API list response must be an array");
      const records = value.map(row => readRow(row, definition.fields));
      if (new Set(records.map(row => row.id)).size !== records.length) throw new Error("API returned duplicate record identities");
      setRows(records); setLoading(false);
    }).catch(error => { if (!controller.signal.aborted) { setListError(errorText(error)); setLoading(false); } });
    return () => controller.abort();
  }, [endpoint, definition]);
  const selected = rows.find(row => row.id === selectedId);
  const begin = (row?: FixtureRow) => {
    setFormError(""); setListError("");
    setEditor({ id: row?.id ?? null, draft: Object.fromEntries(definition.fields.map(field => [field.key, row?.[field.key] ?? definition.empty[field.key]])) });
  };
  const save = async () => {
    if (!editor || pending) return;
    setPending(true); setFormError("");
    try {
      const saved = readRow(await request(editor.id === null ? endpoint : `${endpoint}/${encodeURIComponent(editor.id)}`, {
        method: editor.id === null ? "POST" : "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(editor.draft),
      }), definition.fields);
      if (editor.id !== null && saved.id !== editor.id) throw new Error("API changed the edited record identity");
      // Apply only the full row returned after a successful real server operation.
      setRows(previous => editor.id === null ? [...previous, saved] : previous.map(row => row.id === saved.id ? saved : row));
      select(saved.id); setEditor(null);
    } catch (error) { setFormError(errorText(error)); }
    finally { setPending(false); }
  };
  const remove = async () => {
    if (!selected || pending) return;
    setPending(true); setListError("");
    try {
      const answer = await dialogs.message({ title: "Delete record", text: `Delete ${definition.singular} ${String(selected[definition.fields[0].key])}?`, type: 2, destructive: true });
      if (answer !== 6) return;
      await request(`${endpoint}/${encodeURIComponent(selected.id)}`, { method: "DELETE" });
      setRows(previous => previous.filter(row => row.id !== selected.id)); select(null);
    } catch (error) { setListError(errorText(error)); }
    finally { setPending(false); }
  };
  const visible = rows.filter(row => [row.id, ...definition.fields.map(field => String(row[field.key]))].join(" ").toLowerCase().includes(search.toLowerCase()));
  return <main className="workflow-fixture" data-testid="workflow-fixture" data-entity={entity}>
    <style>{styles}</style>
    <header><h1>{definition.title}</h1><p>Test-only HTTP workflow fixture · scratch SQLite persistence</p></header>
    <nav aria-label="Fixture entities"><a href="?entity=members">Members</a><a href="?entity=rooms">Rooms</a></nav>
    <div className="fixture-toolbar">
      <button type="button" data-testid="new-record" disabled={loading || pending} onClick={() => begin()}>New</button>
      <button type="button" data-testid="edit-record" disabled={!selected || pending} onClick={() => begin(selected)}>Edit</button>
      <button type="button" data-testid="delete-record" disabled={!selected || pending} onClick={() => { void remove(); }}>Delete</button>
      <label htmlFor="fixture-search">Search <input id="fixture-search" data-testid="search" type="search" value={search} onChange={event => setSearch(event.currentTarget.value)} /></label>
    </div>
    {loading && <p role="status">Loading records…</p>}
    {listError && <p role="alert" data-testid="list-error">{listError}</p>}
    <table data-testid="record-table" aria-label={definition.title}>
      <thead><tr><th scope="col">ID</th>{definition.fields.map(field => <th key={field.key} scope="col">{field.label}</th>)}</tr></thead>
      <tbody>{visible.map(row => <tr key={row.id} data-record-key={row.id} aria-selected={row.id === selectedId} tabIndex={0}
        onClick={() => select(row.id)} onDoubleClick={() => begin(row)} onKeyDown={event => {
          if (event.key === " " || event.key === "Enter") { event.preventDefault(); select(row.id); }
        }}>
        <td>{row.id}</td>{definition.fields.map(field => <td key={field.key}>{typeof row[field.key] === "boolean" ? row[field.key] ? "Yes" : "No" : row[field.key]}</td>)}
      </tr>)}</tbody>
    </table>
    <p data-testid="record-count">{visible.length} of {rows.length} records</p>
    {editor && <RecordEditor entity={entity} editor={editor} pending={pending} error={formError} onSave={() => { void save(); }}
      onChange={(key, value) => setEditor(previous => previous ? { ...previous, draft: { ...previous.draft, [key]: value } } : null)}
      onCancel={() => { setEditor(null); setFormError(""); }} />}
  </main>;
}

const styles = `
body { margin: 0; color: #1d2e43; background: #f1f4f8; font: 14px system-ui,sans-serif; }
.workflow-fixture { max-width: 1050px; margin: 32px auto; padding: 24px; background: white; border: 1px solid #c9d3df; border-radius: 7px; }
.workflow-fixture h1 { margin: 0; font-size: 25px; }.workflow-fixture header p { color: #5a6a7e; }
.workflow-fixture nav { display: flex; gap: 16px; margin: 20px 0; }.workflow-fixture nav a { color: #245b9c; }
.fixture-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 18px; }.fixture-toolbar label { margin-left: auto; }
.workflow-fixture button,.workflow-fixture input,.workflow-fixture textarea { font: inherit; }.workflow-fixture button { padding: 6px 14px; border: 1px solid #9caec3; border-radius: 3px; color: inherit; background: #f4f7fb; }.workflow-fixture button:disabled { opacity: .5; }
.workflow-fixture input:not([type=checkbox]),.workflow-fixture textarea { box-sizing: border-box; padding: 6px; border: 1px solid #9caec3; border-radius: 3px; }
.workflow-fixture table { width: 100%; border-collapse: collapse; text-align: left; }.workflow-fixture th,.workflow-fixture td { border: 1px solid #d4dde7; padding: 9px; }.workflow-fixture th { background: #edf2f8; }.workflow-fixture tbody tr { cursor: default; }.workflow-fixture tbody tr[aria-selected=true] { background: #dceafb; }
.workflow-fixture [role=alert] { color: #a62434; padding: 10px; border: 1px solid #dbaab2; border-radius: 3px; background: #fff4f6; }
.fixture-editor { width: 420px; padding: 22px; border: 1px solid #9caec3; border-radius: 6px; box-shadow: 0 12px 40px #1d2e4326; color: inherit; }.fixture-editor::backdrop { background: #1d2e4330; }.fixture-editor h2 { margin: 0 0 8px; font-size: 20px; }.fixture-id { color: #5a6a7e; overflow-wrap: anywhere; }
.fixture-field { display: grid; grid-template-columns: 90px 1fr; align-items: start; gap: 8px; margin: 14px 0; }.fixture-field span { padding-top: 6px; }.fixture-field textarea { min-height: 80px; resize: vertical; }.fixture-checkbox { display: flex; align-items: center; gap: 12px; margin: 14px 0; }.fixture-actions { display: flex; justify-content: end; gap: 8px; margin-top: 20px; }
`;
const entity: Entity = new URLSearchParams(window.location.search).get("entity") === "rooms" ? "rooms" : "members";
createRoot(document.getElementById("root")!).render(<UiProvider config={{ namespace: `workflow-fixture:${entity}`, locale: "en-GB" }}>
  <DialogProvider><Fixture entity={entity} /></DialogProvider>
</UiProvider>);
