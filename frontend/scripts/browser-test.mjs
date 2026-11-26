// `make browser-test`: one short journey in a real Chromium, as a visitor with no sign-in, on
// the local servers and the Firestore emulator. No model call and no key.
//
// It is started by scripts/screens.sh, which runs the backend and the frontend first. Phone
// width, where the two lists are stacked, so "fixes above advisory risks" can be measured.

import { chromium } from "playwright-core";

const BASE = process.env.SCREENS_BASE_URL ?? "http://localhost:3000";
const CLIENT = "Northwind Cycles"; // seeded with both fixes and advisory risks

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.setDefaultTimeout(30_000);

  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  const rows = page.locator(".client-row:visible");
  await rows.first().waitFor();
  check((await rows.count()) === 12, `home lists ${await rows.count()} clients, not 12`);
  console.log("pass  home lists 12 clients");

  await page.getByRole("link", { name: CLIENT }).locator("visible=true").click();
  await page.getByRole("heading", { level: 1, name: CLIENT }).waitFor();
  const fixes = await page.locator("#fixes-heading").boundingBox();
  const advisory = await page.locator("#advisory-heading").boundingBox();
  check(fixes && advisory, "the fixes or the advisory heading is not on the page");
  check(fixes.y + fixes.height <= advisory.y, "the fixes are not above the advisory risks");
  console.log("pass  the client page shows fixes above advisory risks");

  const mark = page.getByRole("button", { name: "Mark handled" }).first();
  const markId = await mark.getAttribute("id");
  check(markId?.startsWith("mark-"), "no risk to mark handled");
  // Risk ids hold ":" and ".", so they are matched as attribute values, not as #id selectors.
  const reopen = page.locator(`[id="reopen-${markId.slice("mark-".length)}"]`);
  const saved = page.waitForResponse((response) => response.url().endsWith("/handled"));
  await mark.click();
  check((await saved).ok(), "the handled click was not saved");
  await reopen.waitFor();
  console.log("pass  a risk is marked handled");

  await page.reload({ waitUntil: "networkidle" });
  await reopen.waitFor();
  check(
    (await page.locator(`[id="${markId}"]`).count()) === 0,
    "the handled risk is back in the list",
  );
  console.log("pass  after a reload the risk is still hidden");
} finally {
  await browser.close();
}
