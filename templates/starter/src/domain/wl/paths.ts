/** WLanguage file-path functions on Windows paths ("\" separator; "/" also accepted when reading). Pure: no file access. */
const base = (path: string) => path.split(/[\\/]/).pop() ?? "";

/** CompleteDir(path): adds the trailing "\" when missing ("" stays ""). */
export const completeDir = (path: string) => (path === "" || path.endsWith("\\") ? path : `${path}\\`);
/** fExtractPath(path, fFileName): the file name without folder or extension. */
export function fileName(path: string): string {
  const name = base(path),
    dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}
/** fExtractPath(path, fExtension): the extension with its dot (".pdf"); "" when none. */
export function fileExtension(path: string): string {
  const name = base(path),
    dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot) : "";
}
/** fExtractPath(path, fDirectory) without the trailing "\". */
export const parentDir = (path: string) => path.replace(/[\\/][^\\/]*$/, "");
