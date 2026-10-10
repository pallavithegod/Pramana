import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "APIx — Airfare Price Index · Air-Sankhyiki",
  description:
    "Real-time Airfare Price Index for India (SIH 2026 · MoSPI PS 26056). PRISM decomposition, GEKS-Törnqvist methodology, MoSPI-mirror API.",
  icons: {
    icon: "/icon.png",
    shortcut: "/icon.png",
    apple: "/icon.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
