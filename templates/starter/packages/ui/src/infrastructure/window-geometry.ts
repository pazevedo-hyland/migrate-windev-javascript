import type { WindowGeometry, WindowGeometryStore } from "../application/window-geometry";

type GeometryStorage = Pick<Storage, "getItem" | "setItem">;

function valid(value: unknown): value is WindowGeometry {
  if (!value || typeof value !== "object") return false;
  const data = value as Record<string, unknown>;
  return ["x", "y", "width", "height"].every(key => typeof data[key] === "number" && Number.isFinite(data[key])) &&
    Number(data.x) >= 0 && Number(data.y) >= 0 && Number(data.width) > 0 && Number(data.height) > 0 && typeof data.maximized === "boolean";
}

function bounds(value: WindowGeometry): WindowGeometry {
  return { x: value.x, y: value.y, width: value.width, height: value.height, maximized: value.maximized };
}

export function createWindowGeometryStore(storage?: GeometryStorage, namespace = "windev-migration"): WindowGeometryStore {
  if (!namespace.trim() || /[\u0000-\u001f]/.test(namespace)) throw new Error("UI storage namespace is required");
  const prefix = `${namespace}:window-geometry:v1:`;
  return {
    load(name) {
      try {
        const value: unknown = JSON.parse((storage ?? window.localStorage).getItem(prefix + encodeURIComponent(name)) ?? "null");
        if (!valid(value) || (value as WindowGeometry & { version?: unknown }).version !== 1) return null;
        return bounds(value);
      } catch { return null; }
    },
    save(name, geometry) {
      if (!valid(geometry)) return false;
      try {
        (storage ?? window.localStorage).setItem(prefix + encodeURIComponent(name), JSON.stringify({ version: 1, ...bounds(geometry) }));
        return true;
      } catch { return false; }
    },
  };
}
