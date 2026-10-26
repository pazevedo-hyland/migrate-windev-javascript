import type { KeyboardEvent } from "react";

export function mnemonicCaption(caption: string) {
  const characters = Array.from(caption);
  let text = "", letter = "", index = -1;
  for (let i = 0; i < characters.length; i++) {
    const character = characters[i];
    if (character === "&" && i + 1 < characters.length) {
      const next = characters[++i];
      if (next !== "&" && index < 0) { letter = next; index = text.length; }
      text += next;
    } else text += character;
  }
  return { text, letter, before: index < 0 ? text : text.slice(0, index), after: index < 0 ? "" : text.slice(index + letter.length) };
}

export function activateMnemonic(event: KeyboardEvent<HTMLElement>, locale = "en") {
  if (event.defaultPrevented || !event.altKey || event.ctrlKey || event.metaKey || event.repeat || event.nativeEvent.isComposing) return;
  const root = event.currentTarget;
  if (!(event.target instanceof Element) || event.target.closest("[data-wd-keyboard-scope]") !== root) return;
  const matches = Array.from(root.querySelectorAll<HTMLButtonElement>("button[data-wd-mnemonic]")).filter(button =>
    button.closest("[data-wd-keyboard-scope]") === root && button.dataset.wdMnemonic === event.key.toLocaleLowerCase(locale) &&
    !button.matches(":disabled") && !button.closest("[inert]") && button.getClientRects().length > 0 && getComputedStyle(button).visibility === "visible");

  if (matches.length !== 1) return;
  event.preventDefault(); matches[0].click();
}
