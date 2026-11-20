import type { Metadata } from "next";
import Link from "next/link";
import type { ReactElement } from "react";
import { PageFrame } from "@/components/chrome";

export const metadata: Metadata = { title: "Nothing here" };

export default function NotFound(): ReactElement {
  return (
    <PageFrame>
      <h1 className="t-title">Nothing here</h1>
      <p className="mt-2">
        <Link href="/" className="link tap">
          Back to clients
        </Link>
      </p>
    </PageFrame>
  );
}
