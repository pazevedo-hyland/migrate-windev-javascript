import { useState } from "react";
import { controlBox, controlOf, WdRadControls, WdTable, type LegacyControl, type LegacyLayout, type WdRadBinding } from "@windev-migration/ui";
import type { ScreenAdapter, ScreenDefinition, ScreenModel } from "./contracts";

const chrome = new Set(["RADTitle", "SCSystemButtons", "BTN_SYST_MINIMIZE", "BTN_Syst_Maximize", "BTN_SYST_FERMER", "BTN_Syst_Restore", "BTN_UMC"]);
export function contentControls(layout: LegacyLayout) {
  const controls = layout.controls.filter(control => !chrome.has(control.name));
  const hasCompleteOrder = controls.every(control => control.tab_order != null && Number.isFinite(Number(control.tab_order)) && Number(control.tab_order) >= 0);
  return hasCompleteOrder ? controls.sort((a, b) => Number(a.tab_order) - Number(b.tab_order)) : controls;
}

/** Reversible input drafts let developers inspect extraction without inventing persistence. */
function useScaffold(layout: LegacyLayout): ScreenModel {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const bindings: WdRadBinding[] = [];
  for (const control of contentControls(layout)) {
    if (control.width == null || control.height == null) continue;
    const name = control.path;
    if (control.kind === "Caption") bindings.push({ name, kind: "caption" });
    else if (control.kind === "Button") bindings.push({ name, kind: "button", props: { disabled: true, title: "Bind an application action first" } });
    else if (control.kind === "Edit control") {
      const props = { value: Object.hasOwn(draft, name) ? draft[name] : "", onChange: (event: { currentTarget: { value: string } }) => {
        const value = event.currentTarget.value;
        setDraft(previous => ({ ...previous, [name]: value }));
      } };
      bindings.push(control.flags?.Multiline === true ? { name, kind: "memo", props } : { name, kind: "edit", props });
    } else if (control.kind === "Check Box") bindings.push({ name, kind: "checkbox", props: { checked: null, disabled: true, onChange: () => {} } });
    else if (control.kind === "Combo Box") bindings.push({ name, kind: "combo", props: { options: [], value: "", disabled: true, onChange: () => {} } });
    else if (control.kind === "RadioButton") bindings.push({ name, kind: "radio", props: { options: [], value: null, label: control.caption ?? control.name, disabled: true, onChange: () => {} } });
  }
  return { bindings, status: "Screen scaffold: drafts only. Connect queries, option values and actions in src/adapters.ts." };
}

function MissingControl({ control }: { control: LegacyControl }) {
  if ((control.visible ?? control.flags?.Visible) === false) return null;
  const geometry = control.width != null && control.height != null ? controlBox(control) : {
    left: Number.isFinite(control.x) ? control.x : 12, top: Number.isFinite(control.y) ? control.y : 40,
    width: control.width ?? 220, minHeight: control.height ?? 32,
  };
  return <div className="missing-control" data-testid={`unbound:${control.path}`} style={geometry}>
    {control.caption ?? control.name}: {control.kind || "unknown kind"} needs a binding
  </div>;
}

function BoundScreen({ definition, useAdapter }: { definition: ScreenDefinition; useAdapter: ScreenAdapter }) {
  const model = useAdapter(definition.layout);
  const evidence = definition.layout as LegacyLayout & { diagnostics?: string[]; unknown?: string[] };
  const diagnostics = [...evidence.diagnostics ?? [], ...evidence.unknown ?? []];
  const bound = new Set(model.bindings.map(binding => controlOf(definition.layout, binding.name).path));
  for (const table of model.tables ?? []) {
    const control = controlOf(definition.layout, table.name);
    if (control.kind !== "Table") throw new Error(`Table kind mismatch: ${control.path}`);
    if (bound.has(control.path)) throw new Error(`RAD control bound twice: ${control.path}`);
    bound.add(control.path);
  }
  return <>
    <WdRadControls layout={definition.layout} bindings={model.bindings} />
    {model.tables?.map(({ name, ...props }) => <WdTable key={name} control={controlOf(definition.layout, name)} {...props} />)}
    {contentControls(definition.layout).filter(control => !bound.has(control.path)).map(control => <MissingControl key={control.path} control={control} />)}
    {(model.status || diagnostics.length > 0) && <div className="screen-status">
      {model.status && <div role="status">{model.status}</div>}
      {diagnostics.length > 0 && <details><summary>Extraction diagnostics ({diagnostics.length})</summary><ul>{diagnostics.map((text, index) => <li key={index}>{text}</li>)}</ul></details>}
    </div>}
  </>;
}

export function Screen({ definition, adapter }: { definition: ScreenDefinition; adapter?: ScreenAdapter }) {
  return <BoundScreen definition={definition} useAdapter={adapter ?? useScaffold} />;
}
