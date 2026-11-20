import type { Metadata } from "next";
import localFont from "next/font/local";
import { type ReactElement, Suspense } from "react";
import { Announcer } from "@/components/announcer";
import { AdminBar, SiteHeader } from "@/components/chrome";
import "./globals.css";

// Both families come from files in the repository: the build needs no network.
const instrumentSans = localFont({
  src: "../fonts/InstrumentSans-Variable.woff2",
  variable: "--font-instrument-sans",
  display: "swap",
  weight: "400 700",
  declarations: [{ prop: "font-stretch", value: "75% 100%" }],
});

// The model's words only. Not preloaded: most pages open without a risk on them.
const newsreader = localFont({
  src: "../fonts/Newsreader-Variable.woff2",
  variable: "--font-newsreader",
  display: "swap",
  weight: "200 800",
  preload: false,
});

export const metadata: Metadata = {
  title: { default: "domain-health", template: "%s - domain-health" },
  // Not the claim sentence: a search result or a link preview would show it without its limit.
  description:
    "A demo of a daily email-domain health check on invented clients. Its eval result and its limit are on the page.",
};

// Runs before the first paint, so a saved theme never flashes.
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export default function RootLayout({ children }: LayoutProps<"/">): ReactElement {
  return (
    <html
      lang="en"
      className={`${instrumentSans.variable} ${newsreader.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <a href="#content" className="skip-link">
          Skip to content
        </a>
        <SiteHeader />
        <Suspense fallback={null}>
          <AdminBar />
        </Suspense>
        {children}
        <Announcer />
      </body>
    </html>
  );
}
