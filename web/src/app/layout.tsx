import type { Metadata, Viewport } from "next";
import { DM_Sans, Fraunces } from "next/font/google";

import { AuthProvider } from "@/components/AuthProvider";
import { DataHealthPanel } from "@/components/DataHealthPanel";
import { LocaleProvider } from "@/components/LocaleProvider";
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
  title: "Kestrel — Spot. Signal. Act.",
  description:
    "Kestrel Soft Ink — Pokémon TCG market prices, AI signals, portfolio, and dealer tools.",
  applicationName: "Kestrel",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Kestrel",
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
  themeColor: "#0c0c0c",
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
          <AuthProvider>
            <div className="app-shell">
              <SiteHeader />
              <WatchAlertBanners />
              <PwaChrome />
              <main>{children}</main>
              <DataHealthPanel />
            </div>
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
