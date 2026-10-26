import { useLayoutEffect, useRef, useState, type ChangeEvent, type FocusEvent, type KeyboardEvent } from "react";

export function inputSuggestions(values: readonly (string | null | undefined)[], draft: string, maxLength?: number): string[] {
  if (!draft) return [];
  const prefix = draft.toLowerCase();
  return [...new Set(values)].filter((value): value is string => typeof value === "string" && value.length > 0
    && (!(maxLength && maxLength > 0) || value.length <= maxLength) && value.toLowerCase().startsWith(prefix));
}

type SuggestionKey = { type: "move" | "accept"; index: number } | { type: "dismiss" };
export function suggestionKey(key: string, count: number, active: number): SuggestionKey | null {
  if (!count) return null;
  if (key === "Escape") return { type: "dismiss" };
  if (key === "ArrowDown") return { type: "move", index: active < 0 ? 0 : Math.min(active + 1, count - 1) };
  if (key === "ArrowUp") return { type: "move", index: active < 0 ? count - 1 : Math.max(active - 1, 0) };
  if (key === "Enter" && active >= 0 && active < count) return { type: "accept", index: active };
  return null;
}

interface InputHandlers {
  onFocus?: (event: FocusEvent<HTMLInputElement>) => void;
  onBlur?: (event: FocusEvent<HTMLInputElement>) => void;
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
}

export function useInputSuggestions({ enabled, values = [], maxLength, onSuggestion, handlers, id, testId, label }: {
  enabled: boolean; values?: readonly string[]; maxLength?: number; onSuggestion?: (value: string) => void;
  handlers: InputHandlers; id: string; testId: string; label: string;
}) {
  const [state, setState] = useState<{ input: HTMLInputElement | null; draft: string; open: boolean; active: string | null }>({ input: null, draft: "", open: false, active: null });
  const options = enabled && state.open ? inputSuggestions(values, state.draft, maxLength) : [];
  const active = state.active === null ? -1 : options.indexOf(state.active);
  const listId = `${id}-suggestions`;
  const remember = (input: HTMLInputElement) => {
    if (enabled) setState({ input, draft: input.value, open: true, active: null });
  };
  const accept = (value: string) => {
    if (!enabled || !state.input || state.input.disabled || state.input.readOnly) return;
    onSuggestion?.(value);
    state.input.focus({ preventScroll: true });
    state.input.setSelectionRange(value.length, value.length);
    setState(previous => ({ ...previous, draft: value, open: false, active: null }));
  };
  return {
    onFocus: (event: FocusEvent<HTMLInputElement>) => { handlers.onFocus?.(event); remember(event.currentTarget); },
    onChange: (event: ChangeEvent<HTMLInputElement>) => { handlers.onChange?.(event); remember(event.currentTarget); },
    onBlur: (event: FocusEvent<HTMLInputElement>) => {
      setState(previous => previous.open ? { ...previous, open: false, active: null } : previous);
      handlers.onBlur?.(event);
    },
    onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => {
      const action = !event.defaultPrevented && !event.altKey && !event.ctrlKey && !event.metaKey && !event.nativeEvent.isComposing
        ? suggestionKey(event.key, options.length, active) : null;
      if (!action) { handlers.onKeyDown?.(event); return; }
      event.preventDefault(); event.stopPropagation();
      if (action.type === "accept") accept(options[action.index]);
      else setState(previous => ({ ...previous, open: action.type !== "dismiss", active: action.type === "move" ? options[action.index] : null }));
    },
    attributes: enabled ? {
      role: "combobox", "aria-autocomplete": "list" as const, "aria-expanded": options.length > 0,
      "aria-controls": options.length ? listId : undefined,
      "aria-activedescendant": active >= 0 ? `${listId}-${active}` : undefined,
    } : {},
    popup: options.length > 0 && state.input ? <InputSuggestionList input={state.input} options={options} active={active}
      id={listId} testId={testId} label={label} onAccept={accept} /> : null,
  };
}

function InputSuggestionList({ input, options, active, id, testId, label, onAccept }: {
  input: HTMLInputElement; options: readonly string[]; active: number; id: string; testId: string; label: string; onAccept: (value: string) => void;
}) {
  const list = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const node = list.current!;
    const position = () => {
      if (!input.isConnected || !input.checkVisibility()) { if (node.matches(":popover-open")) node.hidePopover(); return; }
      const box = input.getBoundingClientRect(), padding = 8;
      const below = window.innerHeight - box.bottom - padding, above = box.top - padding;
      const height = Math.min(160, options.length * 20 + 2), upwards = below < height && above > below;
      const available = Math.max(0, upwards ? above : below);
      const width = Math.min(box.width, window.innerWidth - padding * 2);
      Object.assign(node.style, { left: `${Math.max(padding, Math.min(box.left, window.innerWidth - width - padding))}px`,
        top: `${upwards ? box.top - Math.min(height, available) : box.bottom}px`, width: `${width}px`, maxHeight: `${Math.min(160, available)}px` });
      if (!node.matches(":popover-open")) node.showPopover();
    };
    position();
    node.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => { window.removeEventListener("resize", position); window.removeEventListener("scroll", position, true); };
  });
  return <div ref={list} id={id} data-testid={testId} role="listbox" aria-label={label} popover="manual" className="wd-input-suggestions">
    {options.map((value, index) => <div key={value} id={`${id}-${index}`} role="option" tabIndex={-1} aria-selected={index === active}
      onPointerDown={event => { event.preventDefault(); event.stopPropagation(); }} onClick={event => { event.stopPropagation(); onAccept(value); }}>{value}</div>)}
  </div>;
}
