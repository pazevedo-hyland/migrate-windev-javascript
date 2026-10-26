import { createRoot } from "react-dom/client";
import { App } from "../src/App";
import type { ScreenDefinition } from "../src/runtime/contracts";
import "../src/style.css";

const definitions: ScreenDefinition[] = [{ id: "constructor", source: "synthetic fixture", layout: {
  window: { name: "constructor", title: "Unknown source assets", size: { width: 640, height: 460 }, background_image: "unconfigured-frame.png" },
  controls: [
    { name: "RADTitle", path: "RADTitle", kind: "Caption", x: 0, y: 0 },
    { name: "Draft", path: "__proto__", kind: "Edit control", x: 16, y: 60, width: 400, height: 28, caption: "Draft", input_type: "Text" },
    { name: "Action", path: "Action", kind: "Button", x: 16, y: 105, width: 160, height: 32, caption: "Unbound action", background_image: "unconfigured-button.png" },
    { name: "Unsupported", path: "Unsupported", kind: "Unknown widget", x: 16, y: 160, width: 280, height: 38, caption: "<img src=x onerror=alert(1)>" },
    { name: "MissingSize", path: "MissingSize", kind: "Unknown widget", x: 16, y: 210, caption: "Missing size" },
  ],
} }];
createRoot(document.getElementById("root")!).render(<App definitions={definitions} registry={{}} />);
