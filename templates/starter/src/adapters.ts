import { useDemoDirectory } from "./demo/directory";
import type { ScreenAdapter } from "./runtime/contracts";

/** Maintained application code. Use qualified control paths; generation never edits this file. */
export const adapters: Record<string, ScreenAdapter> = { WIN_Directory: useDemoDirectory };
