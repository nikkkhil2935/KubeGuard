import type { Metadata } from "next";
import { IBM_Plex_Mono, Manrope, Sora } from "next/font/google";

import "./globals.css";

const fontBody = Manrope({ subsets: ["latin"], variable: "--font-body" });
const fontDisplay = Sora({ subsets: ["latin"], variable: "--font-display" });
const fontMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "KubeGuard Next Command Center",
  description: "Advanced Next.js frontend for KubeGuard operations and self-healing telemetry.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${fontBody.variable} ${fontDisplay.variable} ${fontMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
