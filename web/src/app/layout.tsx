import type { Metadata, Viewport } from "next";
import { DM_Sans, Fraunces } from "next/font/google";

import { AuthProvider } from "@/components/AuthProvider";
import { CurrencyProvider } from "@/components/CurrencyProvider";
import { LocaleProvider } from "@/components/LocaleProvider";
import { OpsHealthGate } from "@/components/OpsHealthGate";
import { PwaChrome } from "@/components/PwaChrome";
import { SiteHeader } from "@/components/SiteHeader";
import { WatchAlertBanners } from "@/components/WatchAlertBanners";

import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://www.kestreltcg.app"),
  title: {
    default: "Kestrel — Spot. Signal. Act.",
    template: "%s · Kestrel",
  },
  description:
    "Kestrel Soft Ink — Pokémon TCG market prices, AI fair-band signals, portfolio, Trade Analyzer, and dealer tools.",
  applicationName: "Kestrel",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Kestrel",
  },
  openGraph: {
    type: "website",
    siteName: "Kestrel",
    locale: "en_US",
  },
  twitter: {
    card: "summary",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0908",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} ${fraunces.variable} antialiased`}>
        <LocaleProvider>
          <CurrencyProvider>
            <AuthProvider>
              <div className="app-shell">
                <SiteHeader />
                <WatchAlertBanners />
                <PwaChrome />
                <main>{children}</main>
                <OpsHealthGate />
              </div>
            </AuthProvider>
          </CurrencyProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
