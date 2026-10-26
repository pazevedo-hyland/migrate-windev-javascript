import { useLayoutEffect, useRef, type Ref } from "react";
import { dateCalendarText } from "../../value/date-entry";
import { dateTimeCalendarChange, dateTimeCalendarValue, dateTimeEntryChange, type DateTimeEntryDraft } from "../../value/date-time";
import { WdCalendarEdit, type WdCalendarEditHandle } from "./calendar-edit";
import type { LegacyControl } from "./layout";

export type WdDateTimeEditHandle = WdCalendarEditHandle;

export function WdDateTimeEdit({ control, draft, onChange, invalid = false, disabled = false, ref }: {
  control: LegacyControl; draft: DateTimeEntryDraft; onChange: (draft: DateTimeEntryDraft) => void;
  invalid?: boolean; disabled?: boolean; ref?: Ref<WdDateTimeEditHandle>;
}) {
  if (control.input_type !== "Date" || control.return_format !== "YYYYMMDDHHmmSS" || control.input_mask !== "DD/MM/YYYY HH:mm"
    || !["Yes", "No"].includes(control.calendar_button ?? "") || control.blocking_validation !== "Yes") {
    throw new Error(`Date-time metadata unresolved: ${control.path}`);
  }
  // A literal CalculatorYes does not establish a second behavior or precision conversion.
  const latest = useRef(draft);
  useLayoutEffect(() => { latest.current = draft; }, [draft]);
  return <WdCalendarEdit control={control} value={draft.text} invalid={invalid} disabled={disabled} ref={ref}
    calendarValue={() => dateTimeCalendarValue(latest.current)} isCalendarValue={iso => dateCalendarText(iso) !== null}
    onTextChange={text => onChange(dateTimeEntryChange(latest.current, text))}
    onCalendarEdit={(iso, valid) => onChange(valid ? dateTimeCalendarChange(latest.current, iso) : dateTimeEntryChange(latest.current, latest.current.text))} />;
}
