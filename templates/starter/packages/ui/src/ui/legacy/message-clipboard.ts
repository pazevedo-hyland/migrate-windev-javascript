import type { MessageRequest } from "./message-state";
import { writeClipboardText } from "../../infrastructure/clipboard";

export function messageClipboardText(request: Pick<MessageRequest, "title" | "text">): string {
  const separator = "---------------------------";
  return `${separator}\r\n${request.title}\r\n${separator}\r\n${request.text}`;
}

export function writeMessageClipboard(request: Pick<MessageRequest, "title" | "text">, clipboard?: Pick<Clipboard, "writeText">): Promise<boolean> {

  return writeClipboardText(messageClipboardText(request), clipboard);
}
