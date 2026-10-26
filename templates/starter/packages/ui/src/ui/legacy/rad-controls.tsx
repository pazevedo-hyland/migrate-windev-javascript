import type { ComponentProps, CSSProperties } from "react";
import { useAnchoredControl } from "./anchors";
import { controlBox, controlOf, type LegacyControl, type LegacyLayout } from "./layout";
import { WdButton, WdCheckbox, WdEdit, WdMemo, WdRadio } from "./wd";
import { WdCombo } from "./combo";
import { WdDateEdit } from "./date";
import { WdDateTimeEdit } from "./date-time";

export type WdRadBinding = { name: string } & (
  | { kind: "edit"; props: Omit<ComponentProps<typeof WdEdit>, "control"> }
  | { kind: "memo"; props: Omit<ComponentProps<typeof WdMemo>, "control"> }
  | { kind: "checkbox"; props: Omit<ComponentProps<typeof WdCheckbox>, "control"> }
  | { kind: "radio"; props: Omit<ComponentProps<typeof WdRadio>, "control"> }
  | { kind: "combo"; props: Omit<ComponentProps<typeof WdCombo>, "control"> }
  | { kind: "dateTime"; props: Omit<ComponentProps<typeof WdDateTimeEdit>, "control"> }
  | { kind: "date"; props: Omit<ComponentProps<typeof WdDateEdit>, "control"> }
  | { kind: "button"; props: Omit<ComponentProps<typeof WdButton>, "control"> }
  | { kind: "caption"; props?: { text?: string } }
  | { kind: "shape"; props: { backgroundColor: CSSProperties["backgroundColor"] } }
);
const sourceKinds = { edit: "Edit control", memo: "Edit control", date: "Edit control", dateTime: "Edit control", checkbox: "Check Box", radio: "RadioButton", combo: "Combo Box", button: "Button", caption: "Caption", shape: "Shape" } as const;

export function resolveRadBindings(layout: LegacyLayout, bindings: readonly WdRadBinding[]) {
  const seen = new Set<string>();
  return bindings.map(binding => {
    const control = controlOf(layout, binding.name);
    if (seen.has(control.path)) throw new Error(`RAD control bound twice: ${control.path}`);
    seen.add(control.path);
    if (control.kind !== sourceKinds[binding.kind]) throw new Error(`RAD kind mismatch: ${control.path} (${control.kind}, ${binding.kind})`);
    return { binding, control };
  });
}

function RadStatic({ source, kind, backgroundColor, text }: { source: LegacyControl; kind: "caption" | "shape"; backgroundColor?: CSSProperties["backgroundColor"]; text?: string }) {
  const control = useAnchoredControl(source);
  const alignment: CSSProperties = kind === "caption" ? {
    display: (control.visible ?? control.flags?.Visible) === false ? "none" : "grid",
    textAlign: ({ Left: "left", Right: "right", Center: "center", Justified: "justify" } as const)[control.h_align ?? "Left"],
    alignItems: ({ Top: "start", Center: "center", Bottom: "end" } as const)[control.v_align ?? "Top"],
  } : {};
  return <div className={`wd-rad-${kind}`} data-testid={control.name} data-control-path={control.path}
    hidden={(control.visible ?? control.flags?.Visible) === false} style={{ ...controlBox(control), backgroundColor, ...alignment }}>{kind === "caption" ? text ?? control.caption : null}</div>;
}

export function WdRadControls({ layout, bindings }: { layout: LegacyLayout; bindings: readonly WdRadBinding[] }) {
  return resolveRadBindings(layout, bindings).map(({ binding, control }) => {
    switch (binding.kind) {
      case "edit": return <WdEdit key={control.path} control={control} {...binding.props} />;
      case "memo": return <WdMemo key={control.path} control={control} {...binding.props} />;
      case "checkbox": return <WdCheckbox key={control.path} control={control} {...binding.props} />;
      case "radio": return <WdRadio key={control.path} control={control} {...binding.props} />;
      case "combo": return <WdCombo key={control.path} control={control} {...binding.props} />;
      case "dateTime": return <WdDateTimeEdit key={control.path} control={control} {...binding.props} />;
      case "date": return <WdDateEdit key={control.path} control={control} {...binding.props} />;
      case "button": return <WdButton key={control.path} control={control} {...binding.props} />;
      case "caption": return <RadStatic key={control.path} source={control} kind="caption" text={binding.props?.text} />;
      case "shape": return <RadStatic key={control.path} source={control} kind="shape" {...binding.props} />;
    }
  });
}
