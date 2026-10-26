export interface WindowGeometry { x: number; y: number; width: number; height: number; maximized: boolean }

export interface WindowGeometryStore {
  load(name: string): WindowGeometry | null;
  save(name: string, geometry: WindowGeometry): boolean;
}
