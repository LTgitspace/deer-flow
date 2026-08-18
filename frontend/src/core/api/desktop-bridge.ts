/**
 * Desktop bridge: Tauri detection + dynamic port resolution.
 *
 * In desktop mode the webview loads the Next.js standalone server, which
 * proxies `/api/*` to the FastAPI gateway via the existing `next.config.js`
 * rewrites (keyed off `DEER_FLOW_INTERNAL_GATEWAY_BASE_URL`). The frontend's
 * API client already resolves same-origin `/api/*` URLs, so no API base URL
 * change is needed here — the bridge only detects the Tauri runtime and
 * resolves the ephemeral backend ports for diagnostics and the titlebar.
 */

export interface DesktopPorts {
  gatewayPort: number | null;
  frontendPort: number | null;
}

export interface DesktopInfo {
  isDesktop: boolean;
  ports: DesktopPorts;
}

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

/** True when running inside the Tauri webview (Tauri v2 injects this). */
export function isDesktopRuntime(): boolean {
  return typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined;
}

/**
 * Resolve the ephemeral ports from the Tauri shell via the `resolve_ports`
 * IPC command. Falls back to the env-provided values for dev. Polls up to
 * `timeoutMs` since the sidecar may still be starting when the webview loads.
 */
export async function getDesktopPorts(timeoutMs = 15000): Promise<DesktopPorts> {
  if (!isDesktopRuntime()) {
    return { gatewayPort: null, frontendPort: null };
  }

  const deadline = Date.now() + timeoutMs;
  // Local import so the browser build never resolves the Tauri package.
  const { invoke } = await import("@tauri-apps/api/core");

  while (Date.now() < deadline) {
    try {
      const ports = await invoke<DesktopPorts>("resolve_ports");
      if (ports.gatewayPort != null || ports.frontendPort != null) {
        return ports;
      }
    } catch {
      // Tauri IPC not ready yet; keep polling.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  return { gatewayPort: null, frontendPort: null };
}

/** The base origin for API calls in desktop mode (same-origin rewrites). */
export function getDesktopApiOrigin(): string {
  return typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1";
}
