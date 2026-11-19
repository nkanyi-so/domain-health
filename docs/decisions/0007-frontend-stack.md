# 0007: frontend on Next.js 16, TypeScript strict, Tailwind 4, pnpm

**Status:** accepted, 2026-11-19 (intake)

**Context.** The page needs server-side routes (to hold the proxy secret and the session), a fallback bundled at build time, light and dark themes, and a host that stays up.

**Decision.** Next.js 16 with the App Router on Vercel, as in the other two demos. Server routes proxy every call to the backend, so the browser never sees the backend URL's secret or talks to Google Cloud. TypeScript in strict mode; the API types are written once from the backend's OpenAPI schema and a test fails if they drift. Tailwind 4 with design tokens as CSS variables. pnpm. Node 24 locally and in CI (Vercel's default; Node 20 is deprecated there).

**Consequence.** Vercel Hobby cannot bill and has no documented inactivity pause; its terms allow removing long-idle accounts, the same risk the other two demos carry. A private repository needs the owner to give Vercel's GitHub app access to it, which is an owner action. Design decisions live in `docs/DESIGN.md`, written in Phase 4.
