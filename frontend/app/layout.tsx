import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Genesis — Specification to Verified Software",
  description:
    "Autonomous software engineering intelligence by Vrajhna Technologies. Spec in, verified software out.",
};

export const viewport: Viewport = { themeColor: "#0a0c10" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
