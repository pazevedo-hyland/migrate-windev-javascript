import type { KeyboardEvent } from "react";

export function dialogTabStops(root: HTMLElement) {
  const dialog = root.closest("dialog");
  const eligible = Array.from(root.querySelectorAll<HTMLElement>("button,input,textarea,select,a[href],[tabindex],summary")).filter(element =>
    element.tabIndex >= 0 && !element.matches(":disabled,input[type=hidden]") && !element.closest("[inert]")
    && element.closest("dialog") === dialog && element.getClientRects().length > 0 && getComputedStyle(element).visibility === "visible");
  return eligible.filter(element => {
    if (!(element instanceof HTMLInputElement) || element.type !== "radio" || !element.name) return true;
    const group = eligible.filter(other => other instanceof HTMLInputElement && other.type === "radio" && other.name === element.name && other.form === element.form) as HTMLInputElement[];
    return element === (group.find(other => other.checked) ?? group[0]);
  }).map((element, index) => ({ element, index })).sort((left, right) => {
    const a = left.element.tabIndex, b = right.element.tabIndex;
    return (a > 0 ? a : Infinity) - (b > 0 ? b : Infinity) || left.index - right.index;
  }).map(item => item.element);
}

export function trapDialogTab(event: KeyboardEvent<HTMLDialogElement>) {
  if (event.defaultPrevented || event.key !== "Tab" || event.ctrlKey || event.altKey || event.metaKey) return;
  const dialog = event.currentTarget;
  const controls = dialogTabStops(dialog);
  const first = controls[0], last = controls[controls.length - 1];
  if (!first) { event.preventDefault(); dialog.focus(); return; }
  if (!controls.includes(document.activeElement as HTMLElement) || document.activeElement === (event.shiftKey ? first : last)) {
    event.preventDefault(); (event.shiftKey ? last : first).focus();
  }
}
