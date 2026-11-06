import type { ReactElement } from "react";

/** Soft Ink copper/ink palette for OG ImageResponse (inline styles only). */
export const OG_SIZE = { width: 1200, height: 630 } as const;

export function OgShell({
  children,
  footer = "kestreltcg.app",
}: {
  children: ReactElement | ReactElement[];
  footer?: string;
}): ReactElement {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "56px 64px",
        background:
          "linear-gradient(135deg, #0a0908 0%, #110f0d 48%, #1a1410 100%)",
        color: "#f3eee6",
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div
          style={{
            width: 14,
            height: 14,
            borderRadius: 999,
            background: "#c07a3a",
          }}
        />
        <div
          style={{
            fontSize: 28,
            letterSpacing: "-0.03em",
            fontWeight: 650,
            color: "#f7f1e8",
          }}
        >
          Kestrel
        </div>
        <div
          style={{
            marginLeft: 8,
            fontSize: 20,
            color: "#9a9288",
            fontFamily: "ui-sans-serif, system-ui, sans-serif",
          }}
        >
          Soft Ink
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 18, flex: 1, justifyContent: "center" }}>
        {children}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          fontSize: 22,
          color: "#9a9288",
        }}
      >
        <div>Spot. Signal. Act.</div>
        <div style={{ color: "#e0b483" }}>{footer}</div>
      </div>
    </div>
  );
}
