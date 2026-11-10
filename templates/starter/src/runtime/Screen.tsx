import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import {
  controlBox,
  controlOf,
  WdRadControls,
  WdTable,
  type LegacyControl,
  type LegacyLayout,
  type WdRadBinding,
} from "@windev-migration/ui";
import type { ScreenAdapter, ScreenDefinition, ScreenModel, WindowContext } from "./contracts";

const chrome = new Set([
  "RADTitle",
  "SCSystemButtons",
  "BTN_SYST_MINIMIZE",
  "BTN_Syst_Maximize",
  "BTN_SYST_FERMER",
  "BTN_Syst_Restore",
  "BTN_UMC",
]);
export function contentControls(layout: LegacyLayout) {
  const controls = layout.controls.filter((control) => !chrome.has(control.name));
  const hasCompleteOrder = controls.every(
    (control) => control.tab_order != null && Number.isFinite(Number(control.tab_order)) && Number(control.tab_order) >= 0,
  );
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
    else if (control.kind === "Button")
      bindings.push({ name, kind: "button", props: { disabled: true, title: "Bind an application action first" } });
    else if (control.kind === "Edit control") {
      const props = {
        value: Object.hasOwn(draft, name) ? draft[name] : "",
        onChange: (event: { currentTarget: { value: string } }) => {
          const value = event.currentTarget.value;
          setDraft((previous) => ({ ...previous, [name]: value }));
        },
      };
      bindings.push(control.flags?.Multiline === true ? { name, kind: "memo", props } : { name, kind: "edit", props });
    } else if (control.kind === "Check Box")
      bindings.push({ name, kind: "checkbox", props: { checked: null, disabled: true, onChange: () => {} } });
    else if (control.kind === "Combo Box")
      bindings.push({ name, kind: "combo", props: { options: [], value: "", disabled: true, onChange: () => {} } });
    else if (control.kind === "RadioButton")
      bindings.push({
        name,
        kind: "radio",
        props: { options: [], value: null, label: control.caption ?? control.name, disabled: true, onChange: () => {} },
      });
  }
  return { bindings, status: "Screen scaffold: drafts only. Connect queries, option values and actions in src/adapters.ts." };
}

/** Containers without behaviour of their own (their children are bound): never "needs a binding". */
export const CONTAINER_KINDS: ReadonlySet<string> = new Set(["Supercontrol", "Group"]);

function MissingControl({ control }: { control: LegacyControl }) {
  if ((control.visible ?? control.flags?.Visible) === false) return null;
  if (CONTAINER_KINDS.has(control.kind)) return null;
  const geometry =
    control.width != null && control.height != null
      ? controlBox(control)
      : {
          left: Number.isFinite(control.x) ? control.x : 12,
          top: Number.isFinite(control.y) ? control.y : 40,
          width: control.width ?? 220,
          minHeight: control.height ?? 32,
        };
  return (
    <div className="missing-control" data-testid={`unbound:${control.path}`} style={geometry}>
      {control.caption ?? control.name}: {control.kind || "unknown kind"} needs a binding
    </div>
  );
}

function withFlags(layout: LegacyLayout, flags?: ScreenModel["flags"]): LegacyLayout {
  if (!flags) return layout;
  return {
    ...layout,
    controls: layout.controls.map((control) => {
      const extra = flags[control.path] ?? flags[control.name];
      // A runtime `..Visible` (flags.Visible) overrides the designer's initial visibility (layout `visible`).
      return extra
        ? { ...control, ...(extra.Visible === undefined ? {} : { visible: extra.Visible }), flags: { ...control.flags, ...extra } }
        : control;
    }),
  };
}

/** Controls below the window's menu bar (`ScreenModel.menuBarHeight`): every content control's y moves down. */
export function belowMenuBar(layout: LegacyLayout, height?: number): LegacyLayout {
  if (!height) return layout;
  return {
    ...layout,
    controls: layout.controls.map((control) =>
      chrome.has(control.name) || !Number.isFinite(control.y) ? control : { ...control, y: control.y + height },
    ),
  };
}

/** What the window host reads from the adapter's model: the Closing event and the runtime title. */
export interface ScreenHooks {
  closing?: ScreenModel["onClosing"];
  setTitle?: (title: string | undefined) => void;
}

const SHOW_DIAGNOSTICS = typeof location !== "undefined" && new URLSearchParams(location.search).get("diag") === "1";

function BoundScreen({
  definition,
  useAdapter,
  window,
  hooks,
}: {
  definition: ScreenDefinition;
  useAdapter: ScreenAdapter;
  window: WindowContext;
  hooks?: ScreenHooks;
}) {
  const model = useAdapter(definition.layout, window);
  // The latest render's handler, so it sees the adapter's current state (e.g. "modified").
  useLayoutEffect(() => {
    if (hooks) hooks.closing = model.onClosing;
  });
  const setTitle = hooks?.setTitle;
  useEffect(() => {
    setTitle?.(model.title);
  }, [setTitle, model.title]);
  const flagKey = JSON.stringify(model.flags ?? null);
  const shifted = useMemo(() => belowMenuBar(definition.layout, model.menuBarHeight), [definition.layout, model.menuBarHeight]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const layout = useMemo(() => withFlags(shifted, model.flags), [shifted, flagKey]);
  const evidence = definition.layout as LegacyLayout & { diagnostics?: string[]; unknown?: string[] };
  // Extraction notes for developers only (`?diag=1`): they are not part of the legacy window.
  const diagnostics = SHOW_DIAGNOSTICS ? [...(evidence.diagnostics ?? []), ...(evidence.unknown ?? [])] : [];
  const bound = new Set(model.bindings.map((binding) => controlOf(definition.layout, binding.name).path));
  for (const table of model.tables ?? []) {
    const control = controlOf(definition.layout, table.name);
    if (control.kind !== "Table") throw new Error(`Table kind mismatch: ${control.path}`);
    if (bound.has(control.path)) throw new Error(`RAD control bound twice: ${control.path}`);
    bound.add(control.path);
  }
  // Static texts and captions without behaviour need no adapter code: draw them as captions.
  const statics: WdRadBinding[] = contentControls(layout)
    .filter(
      (control) => control.kind === "Caption" && !bound.has(control.path) && !model.handled?.has(control.path) && control.width != null,
    )
    .map((control) => ({ name: control.path, kind: "caption" }));
  for (const item of statics) bound.add(item.name);
  return (
    <>
      <WdRadControls layout={layout} bindings={[...model.bindings, ...statics]} />
      {model.tables?.map(({ name, ...props }) => (
        <WdTable key={name} control={controlOf(shifted, name)} {...props} />
      ))}
      {model.extra}
      {contentControls(shifted)
        .filter((control) => !bound.has(control.path) && !model.handled?.has(control.path))
        .map((control) => (
          <MissingControl key={control.path} control={control} />
        ))}
      {(model.status || diagnostics.length > 0) && (
        <div className="screen-status">
          {model.status && <div role="status">{model.status}</div>}
          {diagnostics.length > 0 && (
            <details>
              <summary>Extraction diagnostics ({diagnostics.length})</summary>
              <ul>
                {diagnostics.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </>
  );
}

const detached: WindowContext = {
  name: "",
  params: [],
  close: () => {},
  open: async () => undefined,
  minimize: () => {},
  maximize: () => {},
};

export function Screen({
  definition,
  adapter,
  window = detached,
  hooks,
}: {
  definition: ScreenDefinition;
  adapter?: ScreenAdapter;
  window?: WindowContext;
  hooks?: ScreenHooks;
}) {
  return <BoundScreen definition={definition} useAdapter={adapter ?? useScaffold} window={window} hooks={hooks} />;
}
