// `make screens`: a screenshot of each of the 17 states of the interface, in both themes, at
// 1440 and 390 wide (68 files in screenshots/, which is not committed), and three checks on
// every one of them: text contrast, no sideways scroll, a focus style on every control.
//
// It is started by scripts/screens.sh, which runs the backend and the frontend first. It drives
// a Chromium build that is already in Playwright's cache and never downloads one.

import { mkdir, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const BASE = process.env.SCREENS_BASE_URL ?? "http://localhost:3000";
// The passphrase `make dev` accepts (src/lib/server/env.ts). It works nowhere else.
const PASSPHRASE = process.env.ADMIN_PASSPHRASE ?? "dev-only-passphrase";
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../screenshots");

const ADVISORY = ["Advisory risks", "Advisory, unproven.", "See the eval result"];

/**
 * The 17 states. `path` is the state's address; `must` is wording the state has to
 * show, so a state that silently draws something else fails the run instead of being shot.
 */
const STATES = [
  {
    n: 1,
    slug: "loading",
    title: "Clients",
    path: "/?demo=loading",
    must: ["Loading today's snapshots"],
  },
  {
    n: 2,
    slug: "healthy",
    title: "Harbourlight Books",
    path: "/clients/harbourlight-books?demo=healthy",
    must: ["Healthy today", "Nothing to fix today. Every rule passed.", ...ADVISORY],
  },
  {
    n: 3,
    slug: "fixes-only",
    title: "Fernhollow Garden Supply",
    path: "/clients/fernhollow-garden?demo=fixes-only",
    must: ["Fernhollow Garden Supply", "No advisory risks today.", ...ADVISORY],
  },
  {
    n: 4,
    slug: "risks-only",
    title: "Oakhaven Outfitters",
    path: "/clients/oakhaven-outfitters?demo=risks-only",
    must: ["Nothing to fix today. Every rule passed.", "Mark handled", ...ADVISORY],
  },
  {
    n: 5,
    slug: "both",
    title: "Northwind Cycles",
    path: "/clients/northwind-cycles?demo=both",
    must: ["From DNS", "Mark handled", ...ADVISORY],
  },
  {
    n: 6,
    slug: "handled-one",
    title: "Oakhaven Outfitters",
    path: "/clients/oakhaven-outfitters?demo=handled-one",
    must: ["1 handled. The next risk moved into the list.", "Reopen", ...ADVISORY],
  },
  {
    n: 7,
    slug: "all-handled",
    title: "Oakhaven Outfitters",
    path: "/clients/oakhaven-outfitters?demo=all-handled",
    must: ["Every advisory risk is handled.", "Reopen", ...ADVISORY],
  },
  {
    n: 8,
    slug: "risks-unavailable",
    title: "Northwind Cycles",
    path: "/clients/northwind-cycles?demo=risks-unavailable",
    must: ["Risks unavailable today", "Dropped: it did not pass its checks", ...ADVISORY],
  },
  {
    n: 9,
    slug: "no-snapshot",
    title: "Driftwood Coffee Roasters",
    path: "/clients/driftwood-coffee?demo=no-snapshot",
    must: ["No snapshot for today yet", "Showing the latest one, from 19 Nov 2026."],
  },
  {
    n: 10,
    slug: "check-running",
    title: "Check a domain",
    path: "/check?domain=example.com&demo=running",
    must: ["Checking", "Looking up DNS records for example.com."],
  },
  {
    n: 11,
    slug: "check-result",
    title: "Check a domain",
    path: "/check?domain=example.com&demo=result",
    must: ["Live DNS", "None for a typed domain.", "Advisory risks"],
  },
  {
    n: 12,
    slug: "check-refused",
    title: "Check a domain",
    path: "/check?domain=192.0.2.1&demo=refused",
    must: ["That is not a domain this can check", "No lookup was made."],
  },
  {
    n: 13,
    slug: "rate-limited",
    title: "Check a domain",
    path: "/check?domain=example.com&demo=rate-limited",
    must: ["Five checks in ten minutes is the limit"],
  },
  {
    n: 14,
    slug: "cap-reached",
    title: "Check a domain",
    path: "/check?domain=example.com&demo=cap-reached",
    must: ["Today's 200 checks are used up"],
  },
  {
    n: 15,
    slug: "fallback",
    title: "Clients",
    path: "/?demo=fallback",
    must: ["Showing saved data", "Switched off while the live service cannot be reached."],
  },
  {
    n: 16,
    slug: "admin-signed-in",
    title: "Oakhaven Outfitters",
    path: "/clients/oakhaven-outfitters",
    admin: true,
    must: [
      "Signed in as admin.",
      "Sign out",
      "These ticks are on the shared list. Visitors do not see it: each has a list of their own.",
      ...ADVISORY,
    ],
  },
  {
    n: 17,
    slug: "sign-in-refused",
    title: "Admin sign-in",
    path: "/admin?demo=refused",
    must: ["That passphrase is not right", "Nothing was changed. Try again."],
  },
];

/**
 * The three screens that are not one of the 17 states. No screenshot is kept for them (the count
 * stays 68), but the same three checks are made on them, in both themes and at both widths.
 */
const ALSO_CHECKED = [
  {
    slug: "evals",
    title: "Evals",
    path: "/evals",
    must: ["How the model's list scored", "The four bars", "By set, beside rules alone"],
  },
  {
    slug: "about",
    title: "About this demo",
    path: "/about",
    must: ["What this is", "Its limit", "See the eval result", "What is seeded"],
  },
  {
    slug: "report",
    title: "Northwind Cycles report",
    path: "/clients/northwind-cycles/report",
    must: [
      "Domain health report: Northwind Cycles",
      "Download as Markdown",
      "Authentication",
      "Reputation",
      "Sending",
      "Actions",
      "From DNS",
      ...ADVISORY,
    ],
  },
];

const THEMES = ["light", "dark"];
const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];
// The page ground in each theme (the `page` token): how the script knows the theme took.
const PAGE_GROUND = { light: "rgb(241, 244, 242)", dark: "rgb(19, 28, 26)" };

// Nothing moves in a shot. The development server's own badge is not part of the page.
const STILL = `
  *, *::before, *::after { animation: none !important; transition: none !important; }
  nextjs-portal { display: none !important; }
`;

/** Runs in the page. Every visible piece of text against the ground it sits on. */
function contrastInPage() {
  const parse = (value) => {
    const m = /rgba?\(([^)]+)\)/.exec(value);
    if (!m) return null;
    const p = m[1]
      .split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (top, under) => ({
    r: top.r * top.a + under.r * (1 - top.a),
    g: top.g * top.a + under.g * (1 - top.a),
    b: top.b * top.a + under.b * (1 - top.a),
    a: 1,
  });
  const channel = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  const luminance = (c) => 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);
  const ratio = (a, b) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  /**
   * The grounds a rectangle of text can sit on: the first opaque colour walking up, with any
   * see-through colour above it laid over. A ground drawn as a picture (the hatch strip) counts
   * only where the text overlaps the part of the box the picture covers; then each of its colours
   * is a ground of its own, so the worst one is what is measured.
   */
  const groundsBehind = (element, rect) => {
    const layers = [];
    let pictures = [];
    for (let el = element; el; el = el.parentElement) {
      const style = getComputedStyle(el);
      if (style.backgroundImage !== "none") {
        const box = el.getBoundingClientRect();
        const size = style.backgroundSize.split(" ")[0];
        const covered = size.endsWith("px") ? parseFloat(size) : box.width;
        if (rect.left < box.left + covered && rect.right > box.left) {
          const colours = style.backgroundImage.match(/rgba?\([^)]+\)/g) ?? [];
          pictures = pictures.concat(colours.map(parse).filter((c) => c && c.a > 0));
        }
      }
      const colour = parse(style.backgroundColor);
      if (colour && colour.a > 0) {
        layers.push(colour);
        if (colour.a === 1) break;
      }
    }
    let ground = { r: 255, g: 255, b: 255, a: 1 };
    for (const layer of layers.reverse()) ground = over(layer, ground);
    return [ground, ...pictures.map((picture) => over(picture, ground))];
  };

  const opacityOf = (element) => {
    let opacity = 1;
    for (let el = element; el; el = el.parentElement) {
      opacity *= parseFloat(getComputedStyle(el).opacity);
    }
    return opacity;
  };

  const shown = (element, rect) => {
    if (rect.width < 1 || rect.height < 1) return false;
    if (rect.bottom + scrollY < 0 || rect.right + scrollX < 0) return false;
    for (let el = element; el; el = el.parentElement) {
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility !== "visible") return false;
      // Text kept for screen readers only is clipped to a pixel.
      if (style.position === "absolute" && style.overflow === "hidden") {
        const box = el.getBoundingClientRect();
        if (box.width <= 1 && box.height <= 1) return false;
      }
    }
    return !element.closest("nextjs-portal");
  };

  const results = [];
  const measure = (element, rect, colourValue, text) => {
    const colour = parse(colourValue);
    if (!colour) return;
    const opacity = opacityOf(element);
    let worst = Infinity;
    for (const ground of groundsBehind(element, rect)) {
      const drawn = over({ ...colour, a: colour.a * opacity }, ground);
      worst = Math.min(worst, ratio(drawn, ground));
    }
    results.push({ text: text.trim().replace(/\s+/g, " ").slice(0, 60), ratio: worst });
  };

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.nodeValue.trim()) continue;
    const element = node.parentElement;
    if (!element || ["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE"].includes(element.tagName)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rect = range.getBoundingClientRect();
    if (!shown(element, rect)) continue;
    measure(element, rect, getComputedStyle(element).color, node.nodeValue);
  }
  // What a field shows is not a text node: its value, or its placeholder while it is empty.
  for (const field of document.querySelectorAll("input, textarea")) {
    const rect = field.getBoundingClientRect();
    if (!shown(field, rect) || field.type === "password") continue;
    if (field.value) {
      measure(field, rect, getComputedStyle(field).color, field.value);
    } else if (field.placeholder) {
      measure(field, rect, getComputedStyle(field, "::placeholder").color, field.placeholder);
    }
  }
  return results;
}

/** Runs in the page. Is anything wider than the window? */
function overflowInPage() {
  const root = document.documentElement;
  const beyond = [];
  for (const el of document.body.querySelectorAll("*")) {
    if (el.closest("nextjs-portal")) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility !== "visible") continue;
    if (rect.right > root.clientWidth + 0.5) {
      const name = el.tagName.toLowerCase() + (el.className ? `.${el.className}` : "");
      beyond.push(`${name.slice(0, 60)} (right edge at ${Math.round(rect.right)})`);
    }
  }
  return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth, beyond };
}

/** Runs in the page. Marks every control a keyboard can reach and returns their names. */
function controlsInPage() {
  const controls = [];
  const selector = "a[href], button, input, select, textarea, summary, [tabindex]";
  for (const el of document.querySelectorAll(selector)) {
    if (el.closest("nextjs-portal") || el.tabIndex < 0 || el.disabled) continue;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility !== "visible") continue;
    if (el.getClientRects().length === 0) continue;
    el.setAttribute("data-screens-control", String(controls.length));
    const words = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim() || el.id;
    controls.push(`${el.tagName.toLowerCase()} "${words.replace(/\s+/g, " ").slice(0, 40)}"`);
  }
  return controls;
}

/** Runs in the page. The outline and shadow of the focused control and of what holds it. */
function ringsInPage() {
  const active = document.activeElement;
  if (!active || active === document.body || active === document.documentElement) return null;
  const rings = [];
  // A client list row draws its ring around the whole row, so the holders are looked at too.
  for (let el = active, depth = 0; el && depth < 4; el = el.parentElement, depth += 1) {
    const style = getComputedStyle(el);
    const outline =
      style.outlineStyle === "none" || parseFloat(style.outlineWidth) === 0
        ? "none"
        : `${style.outlineStyle} ${style.outlineWidth} ${style.outlineColor}`;
    rings.push(`${outline} | ${style.boxShadow}`);
  }
  return { index: active.getAttribute("data-screens-control"), rings };
}

/** Runs in the page. The same outlines and shadows with nothing focused. */
function restingRingsInPage() {
  document.activeElement?.blur();
  const resting = {};
  for (const control of document.querySelectorAll("[data-screens-control]")) {
    const rings = [];
    for (let el = control, depth = 0; el && depth < 4; el = el.parentElement, depth += 1) {
      const style = getComputedStyle(el);
      const outline =
        style.outlineStyle === "none" || parseFloat(style.outlineWidth) === 0
          ? "none"
          : `${style.outlineStyle} ${style.outlineWidth} ${style.outlineColor}`;
      rings.push(`${outline} | ${style.boxShadow}`);
    }
    resting[control.getAttribute("data-screens-control")] = rings;
  }
  return resting;
}

/** Tabs through the page once from the top, then compares each control focused and at rest. */
async function focusCheck(page) {
  const controls = await page.evaluate(controlsInPage);
  await page.evaluate(() => {
    document.activeElement?.blur();
    window.scrollTo(0, 0);
  });
  const focused = new Map();
  // Twice round at most: a page that opens with the focus already somewhere (a refused sign-in)
  // starts from there, goes off the end and comes back in at the top.
  for (let press = 0; press < 2 * controls.length + 6; press += 1) {
    if (focused.size >= controls.length) break;
    await page.keyboard.press("Tab");
    const at = await page.evaluate(ringsInPage);
    if (at && at.index !== null && !focused.has(at.index)) {
      focused.set(at.index, at.rings);
    }
  }
  const resting = await page.evaluate(restingRingsInPage);
  const without = [];
  controls.forEach((name, index) => {
    const rings = focused.get(String(index));
    if (!rings) {
      without.push(`${name}: the Tab key never reached it`);
    } else if (rings.every((ring, depth) => ring === resting[String(index)][depth])) {
      without.push(`${name}: looks the same focused as not`);
    }
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  return { count: controls.length, without };
}

async function settle(page) {
  await page.addStyleTag({ content: STILL });
  await page.evaluate(() => document.fonts.ready);
  // Two frames, so the page is drawn with the fonts it has just been given.
  await page.evaluate(
    () => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))),
  );
}

/** Signs in as the local admin and marks one risk handled, so state 16 has a shared tick. */
async function adminSession(browser) {
  const context = await browser.newContext({ viewport: WIDTHS[0] });
  const page = await context.newPage();
  await page.goto(`${BASE}/admin`, { waitUntil: "networkidle" });
  await page.fill("#passphrase", PASSPHRASE);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByText("Signed in as admin.").waitFor();
  await page.goto(`${BASE}/clients/oakhaven-outfitters`, { waitUntil: "networkidle" });
  if ((await page.getByRole("button", { name: /^Reopen/ }).count()) === 0) {
    const saved = page.waitForResponse((response) => response.url().endsWith("/handled"));
    await page.getByRole("button", { name: "Mark handled" }).first().click();
    if (!(await saved).ok()) {
      throw new Error("state 16: the handled click was not saved by the local backend");
    }
  }
  const state = await context.storageState();
  await context.close();
  return state;
}

async function shoot(browser, state, theme, size, storageState) {
  const name = state.n
    ? `${String(state.n).padStart(2, "0")}-${state.slug}-${theme}-${size.width}.png`
    : `${state.slug} (${theme}, ${size.width})`;
  // The app follows the system's theme unless its switch has saved a choice, so the system's
  // preference is what is set, with nothing saved.
  const context = await browser.newContext({
    viewport: size,
    deviceScaleFactor: 1,
    colorScheme: theme,
    reducedMotion: "reduce",
    storageState,
  });
  const page = await context.newPage();
  const problems = [];
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  try {
    const response = await page.goto(BASE + state.path, { waitUntil: "networkidle" });
    if (!response || response.status() !== 200) {
      problems.push(`the address answered ${response ? response.status() : "nothing"}`);
    }
    await settle(page);

    const ground = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    if (ground !== PAGE_GROUND[theme]) {
      problems.push(`the ${theme} theme is not in force: the page ground is ${ground}`);
    }
    const words = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    for (const must of state.must) {
      if (!words.includes(must)) problems.push(`missing wording: "${must}"`);
    }
    const title = await page.title();
    if (title !== `${state.title} - domain-health`) {
      problems.push(`the tab title is "${title}"`);
    }

    // A state's shot goes in the output folder. The other screens are only kept when asked for.
    const file = state.n
      ? path.join(OUT, name)
      : process.env.SCREENS_ALSO_DIR
        ? path.join(process.env.SCREENS_ALSO_DIR, `${state.slug}-${theme}-${size.width}.png`)
        : null;
    if (file) {
      await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
    }

    const texts = await page.evaluate(contrastInPage);
    const low = texts.filter((text) => text.ratio < 4.5);
    const lowest = texts.reduce((least, text) => Math.min(least, text.ratio), Infinity);
    const overflow = await page.evaluate(overflowInPage);
    const sideways = overflow.scrollWidth > overflow.clientWidth || overflow.beyond.length > 0;
    const focus = await focusCheck(page);

    return {
      name,
      state,
      theme,
      width: size.width,
      problems,
      contrast: { count: texts.length, lowest, low },
      overflow: { ...overflow, sideways },
      focus,
    };
  } finally {
    await context.close();
  }
}

function failed(shot) {
  return (
    shot.problems.length > 0 ||
    shot.contrast.low.length > 0 ||
    shot.overflow.sideways ||
    shot.focus.without.length > 0
  );
}

function readme(shots, also) {
  const all = [...shots, ...also];
  const total = (pick) => all.reduce((sum, shot) => sum + pick(shot), 0);
  const lowest = Math.min(...all.map((shot) => shot.contrast.lowest));
  const lines = [
    "# Screens",
    "",
    "Written by `make screens`. Do not edit by hand: run the command again.",
    "",
    `${shots.length} screenshots: the 17 states of the interface, each in the light and the dark theme, at 1440 and at 390 wide, full page.`,
    "",
    "States 1 to 15 and 17 are drawn from the `?demo=` address in the design document's table, so they are the same on any day. State 16 is real: the script signs in on the local servers with the development passphrase, marks one of Oakhaven Outfitters' risks handled and opens that client's page, so its snapshot day and its handled dates are the day the command was run.",
    "",
    "## The three checks",
    "",
    `Computed in the browser on every one of the screenshots, and on the eval table, "About this demo" and one client's report in the same two themes and two widths (${also.length} more pages, no screenshot kept): ${all.length} pages in all. The command exits non-zero if any fails.`,
    "",
    "| Check | Result |",
    "|---|---|",
    `| Contrast: every visible piece of text against the ground it sits on, at least 4.5:1 | ${total((s) => s.contrast.low.length)} below, of ${total((s) => s.contrast.count)} pieces of text measured; the lowest is ${lowest.toFixed(2)}:1 |`,
    `| No sideways scroll: the page is no wider than the window and no element's right edge is beyond it | ${all.filter((s) => s.overflow.sideways).length} of ${all.length} pages scroll sideways (${all.filter((s) => s.width === 390).length} are 390 wide) |`,
    `| Focus: every link, button and field, reached with the Tab key, shows an outline it does not have at rest | ${total((s) => s.focus.without.length)} without, of ${total((s) => s.focus.count)} controls focused |`,
    `| Each page shows its own wording and tab title, in the theme asked for | ${all.filter((s) => s.problems.length > 0).length} of ${all.length} do not |`,
    "",
    "## The screenshots",
    "",
    "| File | State | Address | Text measured | Lowest contrast | Below 4.5 | Sideways scroll | Controls | Without focus style |",
    "|---|---|---|---|---|---|---|---|---|",
  ];
  for (const shot of shots) {
    lines.push(
      `| [${shot.name}](${shot.name}) | ${shot.state.n} | \`${shot.state.path}\`${shot.state.admin ? ", signed in" : ""} | ${shot.contrast.count} | ${shot.contrast.lowest.toFixed(2)} | ${shot.contrast.low.length} | ${shot.overflow.sideways ? "yes" : "no"} | ${shot.focus.count} | ${shot.focus.without.length} |`,
    );
  }
  lines.push(
    "",
    "## Also checked, without a screenshot",
    "",
    "| Page | Address | Text measured | Lowest contrast | Below 4.5 | Sideways scroll | Controls | Without focus style |",
    "|---|---|---|---|---|---|---|---|",
  );
  for (const shot of also) {
    lines.push(
      `| ${shot.name} | \`${shot.state.path}\` | ${shot.contrast.count} | ${shot.contrast.lowest.toFixed(2)} | ${shot.contrast.low.length} | ${shot.overflow.sideways ? "yes" : "no"} | ${shot.focus.count} | ${shot.focus.without.length} |`,
    );
  }
  const bad = all.filter(failed);
  if (bad.length > 0) {
    lines.push("", "## What failed", "");
    for (const shot of bad) {
      lines.push(`- ${shot.name}`);
      for (const line of failures(shot)) lines.push(`  - ${line}`);
    }
  }
  return `${lines.join("\n")}\n`;
}

function failures(shot) {
  const lines = [...shot.problems];
  for (const text of shot.contrast.low) {
    lines.push(`contrast ${text.ratio.toFixed(2)}:1: "${text.text}"`);
  }
  if (shot.overflow.sideways) {
    lines.push(
      `sideways scroll: the page is ${shot.overflow.scrollWidth} wide in a window of ${shot.overflow.clientWidth}`,
    );
    for (const element of shot.overflow.beyond.slice(0, 5))
      lines.push(`beyond the window: ${element}`);
  }
  for (const control of shot.focus.without) lines.push(`no focus style: ${control}`);
  return lines;
}

async function main() {
  await mkdir(OUT, { recursive: true });
  for (const file of await readdir(OUT)) {
    if (file.endsWith(".png")) await rm(path.join(OUT, file));
  }
  const browser = await chromium.launch();
  const shots = [];
  const also = [];
  try {
    const admin = await adminSession(browser);
    for (const state of [...STATES, ...ALSO_CHECKED]) {
      for (const theme of THEMES) {
        for (const size of WIDTHS) {
          const shot = await shoot(browser, state, theme, size, state.admin ? admin : undefined);
          (state.n ? shots : also).push(shot);
          const verdict = failed(shot) ? "FAIL" : "ok";
          console.log(
            `${verdict}  ${shot.name}  contrast ${shot.contrast.low.length} below 4.5 of ${shot.contrast.count} (lowest ${shot.contrast.lowest.toFixed(2)})  sideways scroll ${shot.overflow.sideways ? "yes" : "no"}  focus ${shot.focus.without.length} without of ${shot.focus.count}`,
          );
          if (failed(shot)) {
            for (const line of failures(shot)) console.log(`      ${line}`);
          }
        }
      }
    }
  } finally {
    await browser.close();
  }
  await writeFile(path.join(OUT, "README.md"), readme(shots, also));

  const all = [...shots, ...also];
  const total = (pick) => all.reduce((sum, shot) => sum + pick(shot), 0);
  const written = (await readdir(OUT)).filter((file) => file.endsWith(".png")).length;
  console.log("");
  console.log(
    `contrast: ${total((s) => s.contrast.low.length)} below 4.5:1 of ${total((s) => s.contrast.count)} pieces of text`,
  );
  console.log(
    `sideways scroll: ${all.filter((s) => s.overflow.sideways).length} of ${all.length} pages (${shots.length} screenshots and ${also.length} more)`,
  );
  console.log(
    `focus: ${total((s) => s.focus.without.length)} controls without a focus style of ${total((s) => s.focus.count)}`,
  );
  console.log(`${written} screenshots`);
  const expected = STATES.length * THEMES.length * WIDTHS.length;
  if (written !== expected) {
    console.error(`expected ${expected} screenshots`);
    process.exitCode = 1;
  }
  if (all.some(failed)) {
    console.error("make screens: a check failed (see FAIL above)");
    process.exitCode = 1;
  }
}

await main();
