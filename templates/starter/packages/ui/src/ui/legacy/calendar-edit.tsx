import { useImperativeHandle, useRef, useState, type Ref } from "react";
import { flushSync } from "react-dom";
import type { LegacyControl } from "./layout";
import { WdEdit } from "./wd";
import "./date.css";
import { useUiConfig } from "../../config";

export interface WdCalendarEditHandle { focus(): void; dismissCalendar(): boolean; validateCalendar(): boolean; isCalendarValid(): boolean }

const calendarState = (node: HTMLInputElement) => JSON.stringify([
  node.value, node.validity.badInput, node.validity.rangeUnderflow, node.validity.rangeOverflow,
]);

export function WdCalendarEdit({ control, value, onTextChange, calendarValue, isCalendarValue, onCalendarEdit, invalid = false, disabled = false, ref }: {
  control: LegacyControl; value: string; onTextChange: (text: string) => void;
  calendarValue: () => string; isCalendarValue: (iso: string) => boolean;
  onCalendarEdit: (iso: string, valid: boolean) => void;
  invalid?: boolean; disabled?: boolean; ref?: Ref<WdCalendarEditHandle>;
}) {
  const config = useUiConfig();
  const text = useRef<HTMLInputElement>(null), calendar = useRef<HTMLInputElement>(null);
  const [calendarMode, setCalendarMode] = useState(false), [calendarInvalid, setCalendarInvalid] = useState(false);
  const active = useRef(false), nativeInvalid = useRef(false);
  const keyboardBefore = useRef<string | null>(null);
  const retainNativeInvalid = () => {
    const node = calendar.current;
    if (active.current && node && (node.validity.badInput || node.validity.rangeUnderflow || node.validity.rangeOverflow) && !nativeInvalid.current) {
      nativeInvalid.current = true;
      // Segmented editing can change validity without emitting input/change while the value stays empty.
      onCalendarEdit(node.value, false);
    }
    return nativeInvalid.current;
  };
  const dismissCalendar = () => {
    if (!active.current) return false;
    const invalidNative = retainNativeInvalid();
    active.current = false;
    flushSync(() => { setCalendarMode(false); setCalendarInvalid(invalidNative); });
    text.current?.focus();
    return true;
  };
  useImperativeHandle(ref, () => ({
    focus() { if (!dismissCalendar()) text.current?.focus(); }, dismissCalendar,
    isCalendarValid() {
      const node = calendar.current;
      return !nativeInvalid.current && !(active.current && node
        && (node.validity.badInput || node.validity.rangeUnderflow || node.validity.rangeOverflow || !isCalendarValue(node.value)));
    },
    validateCalendar() {
      if (!retainNativeInvalid()) return true;
      active.current = true;
      flushSync(() => { setCalendarMode(true); setCalendarInvalid(true); });
      calendar.current?.focus();
      return false;
    },
  }));
  const openCalendar = () => {
    const projected = calendarValue();
    active.current = true;
    keyboardBefore.current = null;
    // Remain in a usable visible adapter mode even when this engine has no popup API.
    flushSync(() => setCalendarMode(true));
    const node = calendar.current;
    if (!node) return;
    // Initialize this mutable projection only on explicit entry, never on a React rerender.
    if (!nativeInvalid.current) node.value = projected;
    node.focus();
    try { node.showPicker?.(); } catch { /* The mounted native input remains available for manual entry. */ }
  };
  const changeCalendar = (node: HTMLInputElement) => {
    nativeInvalid.current = node.validity.badInput || node.validity.rangeUnderflow || node.validity.rangeOverflow || !isCalendarValue(node.value);
    setCalendarInvalid(nativeInvalid.current);
    // Partial native segments expose no text value. Latch the actual edit and retain their native invalid state.

    onCalendarEdit(node.value, !nativeInvalid.current);
  };
  const captionWidth = control.caption_width ?? 0;
  return <WdEdit control={control} ref={text} value={value} disabled={disabled} aria-invalid={invalid || calendarInvalid || undefined}
    aria-hidden={calendarMode || undefined} tabIndex={calendarMode ? -1 : undefined}
    onChange={event => { nativeInvalid.current = false; setCalendarInvalid(false); onTextChange(event.currentTarget.value); }}
    onKeyDown={event => {
      if (control.calendar_button === "Yes" && event.altKey && event.key === "ArrowDown" && !event.ctrlKey && !event.metaKey) {
        event.preventDefault(); event.stopPropagation(); openCalendar();
      } else if (event.key === "Enter") { event.preventDefault(); event.stopPropagation(); }
    }} adornment={control.calendar_button === "Yes" ? { width: 20, content: <>
      <button type="button" className="wd-date-calendar-button" data-testid={`${control.name}__calendar`}
        aria-label={config.labels.calendar} tabIndex={-1} disabled={disabled} onPointerDown={event => event.preventDefault()}
        onClick={openCalendar}><span className="wd-date-calendar-icon" aria-hidden="true" /></button>
      <input ref={calendar} type="date" min="0001-01-01" max="9999-12-31" disabled={disabled}
        className="wd-date-calendar-input" data-testid={`${control.name}__calendar-input`} aria-label={config.labels.calendar}
        hidden={!calendarMode} tabIndex={calendarMode ? 0 : -1} aria-invalid={calendarInvalid || undefined}
        style={{ left: captionWidth, width: `calc(100% - ${captionWidth}px)` }}
        onInput={event => changeCalendar(event.currentTarget)} onChange={event => changeCalendar(event.currentTarget)}
        onBlur={() => { if (retainNativeInvalid()) setCalendarInvalid(true); }} onKeyDown={event => {
          keyboardBefore.current = calendarState(event.currentTarget);
          if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); dismissCalendar(); }
          else if (event.key === "Enter") event.stopPropagation();
        }} onKeyUp={event => {
          // Some engines emit no input/change for partial segments, including clearing them back to empty.
          // Observe an actual widget-state change; opening, focus and navigation alone never mark an edit.
          if (keyboardBefore.current !== null && keyboardBefore.current !== calendarState(event.currentTarget)) changeCalendar(event.currentTarget);
          keyboardBefore.current = null;
        }} />
    </> } : undefined} />;
}
