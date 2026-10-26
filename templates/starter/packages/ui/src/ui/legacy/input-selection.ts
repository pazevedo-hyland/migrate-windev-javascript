import { useRef, type FocusEventHandler, type MouseEventHandler } from "react";

interface SelectionHandlers<T> { onFocus?: FocusEventHandler<T>; onMouseDown?: MouseEventHandler<T>; onMouseUp?: MouseEventHandler<T> }

export function useInputSelection<T extends HTMLInputElement | HTMLTextAreaElement>(automaticErase: boolean | undefined, handlers: SelectionHandlers<T> = {}): Required<SelectionHandlers<T>> {
  const enteringByMouse = useRef(false);
  return {
    onFocus: (event) => {
      if (automaticErase === true) event.currentTarget.select();
      handlers.onFocus?.(event);
    },
    onMouseDown: (event) => {
      enteringByMouse.current = automaticErase === true && document.activeElement !== event.currentTarget;
      handlers.onMouseDown?.(event);
    },
    onMouseUp: (event) => {
      if (enteringByMouse.current) event.preventDefault();
      enteringByMouse.current = false;
      handlers.onMouseUp?.(event);
    },
  };
}
