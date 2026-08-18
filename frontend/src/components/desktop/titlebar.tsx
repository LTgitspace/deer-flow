"use client";

import { useEffect, useState } from "react";

import { isDesktopRuntime } from "@/core/api/desktop-bridge";

/**
 * Frameless desktop titlebar.
 *
 * Rendered only when running inside the Tauri webview (desktop mode). Uses
 * `data-tauri-drag-region` for native hardware window dragging, and the
 * Tauri window API for minimize / maximize / close. In the browser the
 * component renders nothing, so the normal page header stays intact.
 */
export function DesktopTitlebar() {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    setIsDesktop(isDesktopRuntime());
  }, []);

  if (!isDesktop) {
    return null;
  }

  const minimize = () => {
    void import("@tauri-apps/api/window").then(({ getCurrentWindow }) =>
      getCurrentWindow().minimize(),
    );
  };

  const toggleMaximize = () => {
    void import("@tauri-apps/api/window").then(async ({ getCurrentWindow }) => {
      const win = getCurrentWindow();
      if (await win.isMaximized()) {
        await win.unmaximize();
      } else {
        await win.maximize();
      }
    });
  };

  const close = () => {
    void import("@tauri-apps/api/window").then(({ getCurrentWindow }) =>
      getCurrentWindow().close(),
    );
  };

  return (
    <div
      data-tauri-drag-region
      className="flex h-9 shrink-0 select-none items-center justify-between border-b border-border bg-background/80 px-3 backdrop-blur"
    >
      <span
        data-tauri-drag-region
        className="text-xs font-medium text-muted-foreground"
      >
        UniDeer
      </span>
      <div className="flex items-center gap-1" data-tauri-drag-region>
        <button
          type="button"
          aria-label="Minimize"
          onClick={minimize}
          className="flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M0 5h10" stroke="currentColor" strokeWidth="1" />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Maximize"
          onClick={toggleMaximize}
          className="flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <rect
              x="0.5"
              y="0.5"
              width="9"
              height="9"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
            />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Close"
          onClick={close}
          className="flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-destructive hover:text-destructive-foreground"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path
              d="M0 0l10 10M10 0L0 10"
              stroke="currentColor"
              strokeWidth="1"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
