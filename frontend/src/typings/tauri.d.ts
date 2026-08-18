/**
 * Ambient types for the optional `@tauri-apps/api` package.
 *
 * The desktop shell (Tauri) is an optional build target: `@tauri-apps/api`
 * is not installed in the normal web build, so `tsc --noEmit` would fail on
 * the dynamic imports in the desktop bridge/titlebar. These declarations
 * satisfy the typecheck without adding the dependency; the dynamic imports
 * only resolve at runtime inside the Tauri webview, where the package is
 * bundled.
 */
declare module "@tauri-apps/api/window" {
  export interface Window {
    minimize(): Promise<void>;
    maximize(): Promise<void>;
    unmaximize(): Promise<void>;
    isMaximized(): Promise<boolean>;
    close(): Promise<void>;
  }

  export function getCurrentWindow(): Window;
}

declare module "@tauri-apps/api/core" {
  export function invoke<T = unknown>(cmd: string, args?: Record<string, unknown>): Promise<T>;
}
