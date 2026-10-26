import Decimal from "decimal.js";
import { useEffect, useRef, useState } from "react";
import { resourceLayout as source } from "./synthetic-layouts";
import { useUiConfig } from "../../config";
import { dialogLayout } from "./dialog-layout";
import { controlOf } from "./layout";
import { WdModal, type WdModalHandle } from "./modal";
import { WdButton, WdEdit } from "./wd";

const ExactArithmetic = Decimal.clone({ precision: 1024, toExpNeg: -1024, toExpPos: 1024 });
const Division = Decimal.clone({ precision: 80, toExpNeg: -80, toExpPos: 80 });
type Operation = "+" | "−" | "×" | "÷";
export function calculatorOperation(left: string, operation: Operation, right: string): string | null {
  if (![left, right].every(value => /^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/.test(value) && value.length <= 256)) return null;
  try {
    // Two bounded 256-character operands, multiplication and carry fit exactly in1024
    // significant digits. Only division adopts the explicit80-digit target default.
    const Arithmetic = operation === "÷" ? Division : ExactArithmetic;
    const a = new Arithmetic(left), b = new Arithmetic(right);
    const value = operation === "+" ? a.plus(b) : operation === "−" ? a.minus(b) : operation === "×" ? a.times(b) : a.dividedBy(b);
    return value.isFinite() ? value.toFixed() : null;
  } catch { return null; }
}

export function CalculatorDialog({ initial, close }: { initial: string; close: (value: string | null) => void }) {
  const config = useUiConfig();
  const ref = useRef<WdModalHandle>(null), field = useRef<HTMLInputElement>(null);
  const [display, setDisplay] = useState(initial || "0"), [invalid, setInvalid] = useState(false);
  const [accumulator, setAccumulator] = useState<string | null>(null), [operation, setOperation] = useState<Operation | null>(null), [replace, setReplace] = useState(true);
  const layout = dialogLayout({ ...source, window: { ...source.window, name: "target-calculator" } }, config.labels.calculator);
  const edit = { ...controlOf(source, "SAI_1"), name: "calculator-value", path: "target/calculator-value", x: 18, y: 38, width: 252, height: 30, caption_width: 0, visible: true, h_align: "Right" };
  const button = controlOf(source, "BTN_1");
  useEffect(() => { field.current?.focus(); }, []);
  const finish = (value: string | null) => { ref.current?.close(); close(value); };
  const key = (value: string) => {
    if (/^[0-9.]$/.test(value)) {
      setInvalid(false);
      setDisplay(previous => {
        const next = replace ? value === "." ? "0." : value : previous === "0" && value !== "." ? value : previous + value;
        return next.length <= 256 && /^[+-]?[0-9]*\.?[0-9]*$/.test(next) ? next : previous;
      });
      setReplace(false); return;
    }
    if (value === "C") { setDisplay("0"); setAccumulator(null); setOperation(null); setReplace(true); setInvalid(false); return; }
    if (value === "⌫") { setDisplay(previous => previous.slice(0, -1) || "0"); setReplace(false); setInvalid(false); return; }
    if (value === "±") { setDisplay(previous => previous.startsWith("-") ? previous.slice(1) : `-${previous}`); setInvalid(false); return; }
    const calculated = accumulator !== null && operation && !replace ? calculatorOperation(accumulator, operation, display) : calculatorOperation(display, "+", "0");
    if (calculated === null) { setInvalid(true); field.current?.focus(); return; }
    setDisplay(calculated); setInvalid(false); setReplace(true);
    if (value === "=") { setAccumulator(null); setOperation(null); }
    else { setAccumulator(calculated); setOperation(value as Operation); }
  };
  const apply = () => {
    const value = accumulator !== null && operation && !replace ? calculatorOperation(accumulator, operation, display) : calculatorOperation(display, "+", "0");
    if (value === null) { setInvalid(true); field.current?.focus(); } else finish(value);
  };
  return <WdModal ref={ref} layout={layout} instance="target-calculator-frame" testId="target-calculator" restoreTestId="target-calculator-restore"
    contentSize={{ width: 288, height: 320 }}
    onClose={() => finish(null)} onCancel={() => finish(null)} onKeyDown={event => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.target instanceof HTMLButtonElement) return;
      const value = ({ "*": "×", "/": "÷", "-": "−", ",": ".", Backspace: "⌫", Delete: "C", Enter: "=" } as Record<string, string>)[event.key] ?? event.key;
      if (/^[0-9.+−×÷=]$/.test(value) || ["⌫", "C"].includes(value)) { event.preventDefault(); event.stopPropagation(); key(value); }
    }}>
    <WdEdit ref={field} control={edit} value={display} aria-invalid={invalid || undefined} aria-label={config.labels.value} readOnly />
    <output aria-live="polite" data-testid="calculator-operation" style={{ position: "absolute", left: 20, top: 72 }}>{accumulator !== null ? `${accumulator} ${operation ?? ""}` : ""}</output>
    {["C", "⌫", "±", "÷", "7", "8", "9", "×", "4", "5", "6", "−", "1", "2", "3", "+", "0", ".", "="].map((value, index) => <WdButton key={value}
      control={{ ...button, name: `calculator-key-${value}`, path: `target/calculator-key-${value}`, caption: value, visible: true, x: 18 + index % 4 * 64, y: 96 + Math.floor(index / 4) * 34, width: 60, height: 30 }}
      onClick={() => key(value)} />)}
    <WdButton control={{ ...button, name: "calculator-apply", path: "target/calculator-apply", caption: config.labels.apply, visible: true, x: 18, y: 280, width: 120, height: 30 }} onClick={apply} />
    <WdButton control={{ ...button, name: "calculator-cancel", path: "target/calculator-cancel", caption: config.labels.cancel, visible: true, x: 150, y: 280, width: 120, height: 30 }} onClick={() => finish(null)} />
  </WdModal>;
}
