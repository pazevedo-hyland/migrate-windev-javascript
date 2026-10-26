import { useId, useLayoutEffect, useRef } from "react";
import { useAnchoredControl } from "./anchors";
import { controlBox, type LegacyControl } from "./layout";

export interface WdComboOption { value: string; label: string }

export function WdCombo({ control: source, options, value, onChange, disabled, allowNoSelection = false, onOpenIntent }: {
  control: LegacyControl; options: readonly WdComboOption[]; value: string;
  onChange: (value: string) => void; disabled?: boolean; allowNoSelection?: boolean; onOpenIntent?: () => void;
}) {
  const control = useAnchoredControl(source), id = useId();
  const captionWidth = control.caption_width ?? 0;
  const select = useRef<HTMLSelectElement>(null);
  useLayoutEffect(() => {
    if (allowNoSelection && !options.some(option => option.value === value) && select.current) select.current.selectedIndex = -1;
  }, [allowNoSelection, options, value]);
  return <div className="wd-field wd-combo-field" hidden={(control.visible ?? control.flags?.Visible) === false}
    data-control-path={control.path} style={controlBox(control)}>
    {captionWidth > 0 && <label htmlFor={id} style={{ width: captionWidth - 2 }}>{control.caption}</label>}
    <select ref={select} id={id} data-testid={control.name} className="wd-edit wd-combo" value={value} disabled={disabled}
      aria-label={captionWidth ? undefined : control.caption ?? control.name}
      tabIndex={control.flags?.["TAB Key"] === false || String(control.tab_order) === "-1" ? -1 : undefined}
      onChange={event => onChange(event.currentTarget.value)}
      onPointerDown={event => { if (event.button === 0 && !disabled) onOpenIntent?.(); }}
      onKeyDown={event => {

        if (!disabled && !event.ctrlKey && !event.metaKey && (event.key === " " || event.key === "F4" || (event.altKey && event.key === "ArrowDown"))) onOpenIntent?.();

        // This does not infer whether an OS popup is currently open.
        if (event.key === "Escape") event.preventDefault();
        if (["Enter", " ", "Escape", "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight"].includes(event.key)) event.stopPropagation();
      }} style={{ left: captionWidth + 4, width: Math.max(0, (control.width ?? 0) - captionWidth - 8) }}>
      {options.map((option, index) => <option key={index} value={option.value}>{option.label}</option>)}
    </select>
  </div>;
}
