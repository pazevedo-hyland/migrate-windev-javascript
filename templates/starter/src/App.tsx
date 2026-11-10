import { useState } from "react";
import { DialogProvider, UiProvider, WdWorkspace } from "@windev-migration/ui";
import { screens } from "./generated/screens";
import { adapters } from "./adapters";
import type { ScreenAdapter, ScreenDefinition } from "./runtime/contracts";
import { WindowManager, useOpenWindow } from "./runtime/windows";

function Launcher({ definitions }: { definitions: ScreenDefinition[] }) {
  const open = useOpenWindow();
  const [error, setError] = useState("");
  // Open(WIN_X): one instance per window; the window's adapter gets params, Close(value), OpenChild and its Closing event.
  const launch = (definition: ScreenDefinition) => {
    if (!definition.layout.window.size) {
      setError(`${definition.id}: window size is unresolved`);
      return;
    }
    setError("");
    void open(definition.id);
  };
  return (
    <header className="launcher">
      <strong>__APP_TITLE__</strong>
      <nav aria-label="Screens">
        {definitions.map((definition) => (
          <button key={definition.id} type="button" onClick={() => launch(definition)}>
            {definition.layout.window.title ?? definition.id}
          </button>
        ))}
      </nav>
      {error && <span role="alert">{error}</span>}
    </header>
  );
}

export function App({
  definitions = screens,
  registry = adapters,
}: { definitions?: ScreenDefinition[]; registry?: Record<string, ScreenAdapter> } = {}) {
  return (
    <UiProvider config={{ namespace: "__APP_NAME__", locale: "en-GB" }}>
      <DialogProvider>
        <WdWorkspace>
          <WindowManager definitions={definitions} registry={registry}>
            <Launcher definitions={definitions} />
          </WindowManager>
        </WdWorkspace>
      </DialogProvider>
    </UiProvider>
  );
}
