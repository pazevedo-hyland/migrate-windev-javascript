/** Optional browser clipboard boundary. Failure never dismisses an active dialog. */
export async function writeClipboardText(text: string, clipboard?: Pick<Clipboard, "writeText">): Promise<boolean> {
  try {
    const target = clipboard ?? (typeof navigator === "undefined" ? undefined : navigator.clipboard);
    if (!target) return false;
    await target.writeText(text);
    return true;
  } catch { return false; }
}
