import type { Metadata } from "next";
import type { ReactElement } from "react";
import { CLAIM } from "@/content/claim";
import "./globals.css";

export const metadata: Metadata = {
  title: "domain-health",
  description: CLAIM,
};

export default function RootLayout({ children }: LayoutProps<"/">): ReactElement {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
