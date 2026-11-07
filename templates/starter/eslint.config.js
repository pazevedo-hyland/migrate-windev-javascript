// ESLint (flat config): JavaScript + TypeScript recommended rules and the React hooks rules. Type checking stays with
// `tsc` (npm run typecheck); this catches mistakes tsc does not (unused code, hook dependencies, suspicious patterns).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/**", "dist-server/**", "release/**", "src/generated/**", "src/bindings/**", "src-tauri/**", "legacy/**", "analysis-local/**",
    "docs/**", "test-results/**", "playwright-report/**", "node_modules/**", ".claude/**", "**/*.min.js", "public/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Ported WLanguage often keeps parameters the legacy signature has: an underscore marks them unused on purpose.
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" }],
      // Deliberate: sanitising file names and keys strips control characters.
      "no-control-regex": "off",
    },
  },
  {
    // Tests: loose fixtures are fine; Playwright helpers named use… are not React hooks.
    files: ["**/*.test.{ts,tsx}", "ui-check/**/*.ts", "packages/*/test/**/*.ts"],
    rules: { "@typescript-eslint/no-explicit-any": "off", "react-hooks/rules-of-hooks": "off" },
  },
  { files: ["**/*.{js,mjs,cjs}"], languageOptions: { globals: { ...globals.node } } },
);
