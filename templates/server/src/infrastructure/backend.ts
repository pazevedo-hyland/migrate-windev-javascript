import type { ErrorKind, RpcResult, Session } from "../backend/rpc";

/**
 * Client side of the procedure registry, chosen once at start-up with `configureBackend`:
 * - server: POST {serverUrl}/rpc — the shared server owns the database (installed stations, `?server=` in tests);
 * - preview: the real procedures on an in-browser PGlite with demo data (show a visible "preview" banner in this mode).
 */
export type Transport = (name: string, input: unknown, session: Session) => Promise<RpcResult>;

let transport: Transport | null = null;
let mode: "server" | "preview" | null = null;
const session: Session = {};

export class BackendError extends Error {
  constructor(
    message: string,
    readonly kind: ErrorKind,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

export function configureBackend(next: Transport, nextMode: "server" | "preview") {
  transport = next;
  mode = nextMode;
}
export function backendMode() {
  return mode;
}
export function getSession(): Readonly<Session> {
  return session;
}
export function setSession(patch: Partial<Session>) {
  Object.assign(session, patch);
}

/** `unavailable` = the text shown when the server does not answer (the legacy connection-failure message, if any). */
export function httpTransport(serverUrl: string, unavailable = (status: number) => `Server unavailable (${status})`): Transport {
  const url = serverUrl.replace(/\/$/, "") + "/rpc";
  return async (name, input, current) => {
    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, input, session: current }),
      });
    } catch {
      return { ok: false, error: unavailable(0), kind: "fatal" };
    }
    if (!response.ok) return { ok: false, error: unavailable(response.status), kind: "fatal" };
    return response.json() as Promise<RpcResult>;
  };
}

/** The in-browser backend (lazy: PGlite is loaded only in preview mode). */
export async function previewTransport(seed?: readonly string[]): Promise<Transport> {
  const { createLocalBackend } = await import("../backend/local");
  const backend = await createLocalBackend(seed ? { seed } : {});
  return (name, input, current) => backend.call(name, input, current);
}

/** Calls a procedure. Business refusals throw BackendError with the legacy text and its kind (info/error/fatal). */
export async function call<T = unknown>(name: string, input: unknown = {}): Promise<T> {
  if (!transport) throw new Error("Backend not configured");
  const result = await transport(name, input, { ...session });
  if (!result.ok) throw new BackendError(result.error, result.kind);
  return result.value as T;
}
