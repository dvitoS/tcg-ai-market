import type { Metadata } from "next";
import { DM_Sans, Fraunces } from "next/font/google";

import { AuthProvider } from "@/components/AuthProvider";
import { SiteHeader } from "@/components/SiteHeader";

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
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} ${fraunces.variable} antialiased`}>
        <AuthProvider>
          <div className="app-shell">
            <SiteHeader />
            <main>{children}</main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
