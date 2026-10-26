import { useState } from "react";
import { DialogProvider, UiProvider, WdWorkspace, useUiConfig, useWorkspace } from "@windev-migration/ui";
import { screens } from "./generated/screens";
import { adapters } from "./adapters";
import { Screen } from "./runtime/Screen";
import type { ScreenAdapter, ScreenDefinition } from "./runtime/contracts";
import { preparePreviewLayout } from "./runtime/preview";

function Launcher({ definitions, registry }: { definitions: ScreenDefinition[]; registry: Record<string, ScreenAdapter> }) {
  const { open } = useWorkspace();
  const { assets } = useUiConfig();
  const [error, setError] = useState("");
  const launch = (definition: ScreenDefinition) => {
    if (!definition.layout.window.size) { setError(`${definition.id}: window size is unresolved`); return; }
    setError("");
    const preview = { ...definition, layout: preparePreviewLayout(definition.layout, assets) };
    const adapter = Object.hasOwn(registry, definition.id) ? registry[definition.id] : undefined;
    open({ key: definition.id, layout: preview.layout, content: <Screen definition={preview} adapter={adapter} /> });
  };
  return <header className="launcher">
    <strong>__APP_TITLE__</strong>
    <nav aria-label="Screens">{definitions.map(definition => <button key={definition.id} type="button" onClick={() => launch(definition)}>{definition.layout.window.title ?? definition.id}</button>)}</nav>
    {error && <span role="alert">{error}</span>}
  </header>;
}

export function App({ definitions = screens, registry = adapters }: { definitions?: ScreenDefinition[]; registry?: Record<string, ScreenAdapter> } = {}) {
  return <UiProvider config={{ namespace: "__APP_NAME__", locale: "en-GB" }}>
    <DialogProvider><WdWorkspace><Launcher definitions={definitions} registry={registry} /></WdWorkspace></DialogProvider>
  </UiProvider>;
}
