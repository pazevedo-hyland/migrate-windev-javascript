// Builds the procedure server and the setup CLI with Vite SSR (the SQL migrations are bundled by import.meta.glob):
//
//   node server/build.mjs                    -> dist-server/main.js, dist-server/setup.js (dependencies from node_modules)
//   node server/build.mjs --self-contained --out <dir>
//                                            -> every dependency bundled except PGlite (it loads its WASM and data files
//                                               from its own package folder: copy node_modules/@electric-sql/pglite
//                                               next to the output as <dir>/node_modules/@electric-sql/pglite)
//
// The test fixtures (ui-check/server) start dist-server/main.js: the same bundle an installer embeds.
import { build } from "vite";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = process.argv.slice(2);
const selfContained = args.includes("--self-contained");
const outIndex = args.indexOf("--out");
const outDir = outIndex >= 0 ? args[outIndex + 1] : join(root, "dist-server");
const external = ["@electric-sql/pglite", "pg-native", "pg-cloudflare", /^node:/];

await build({
  configFile: false,
  root,
  logLevel: "warn",
  mode: "production",
  ssr: selfContained ? { noExternal: true, external: ["@electric-sql/pglite"] } : {},
  build: {
    ssr: true,
    target: "node24",
    outDir,
    emptyOutDir: true,
    minify: false,
    copyPublicDir: false,
    rollupOptions: {
      input: { main: join(root, "server", "main.ts"), setup: join(root, "server", "setup.ts") },
      external: selfContained ? external : undefined,
      output: { format: "esm", entryFileNames: "[name].js", chunkFileNames: "[name]-[hash].js" },
    },
  },
});
console.log(`server bundle -> ${outDir}`);
