# Design: domain-health

The design direction, the tokens, the layout rules and every screen and state. Phase 5 builds the screens from this file and asks nobody about visuals. Where this file and `docs/SPEC.md` disagree, the spec wins and the build stops to say so.

## 1. Direction

### The idea: ink and pencil

The page is a daily check sheet for a person who looks after many sending domains. It has one visual idea, and the idea is the product rule:

- **What the rules found is written in ink.** Fixes sit on a white sheet with a solid border and a solid bar of the darkest colour on the page. Nothing else on the page is heavier.
- **What the model picked is pencilled in beside it.** Advisory risks sit straight on the page ground, inside a dashed outline, in a quieter colour, and their wording is set in a serif. They carry the words "Advisory, unproven" every time they appear.
- **What a person has dealt with is struck through,** with a tick and a date.
- **What is made up for the demo carries a small "seeded" tag,** in the one colour that means nothing else.

A reader who has seen one client page can tell on every later page which words came from a rule, which from a model, and which figures are not real, without reading a legend.

It is modelled, in spirit, on an operations tool a company would ship to its own account team: quiet, dense enough to scan twelve clients without scrolling, every number labelled with where it came from, read in two minutes. It should feel like a maintained inspection log, not a marketing page and not a dashboard.

### What it deliberately avoids

- A hero with a big number, a gradient or an illustration. The first screen is the claim, the live-check field and the client list.
- Cards. Content is not chopped into identical rounded boxes. There are two containers on the whole site, the ink sheet and the pencil box, and each means something.
- Shadows, gradients, glows and glass. Depth is shown with a border and a change of ground colour only.
- A warning colour for fixes. Fixes are ink: the strongest contrast, no hue. Colour is kept for status (healthy, refused, seeded, notice) and for things you can press.
- Charts, sparklines and gauges. Every figure is a number with a label and, where it has one, its previous value in words.
- Labels in capitals, labels above every heading, strings joined with dots, arrows after link text, emoji.
- Anything that makes the model look like the product. No sparkle icon, no "insights", no "AI" badge. The model's column is the quiet one.
- Motion on load or on scroll.

### Typography

Two loaded families and the system monospace. Each has one job, and the split carries information.

| Role | Family | Used for |
|---|---|---|
| Interface | **Instrument Sans** (variable: weight 400 to 700, width 75 to 100; SIL Open Font Licence) | Everything the code wrote: headings, navigation, fix instructions, figures, labels, buttons, messages |
| The model's words | **Newsreader** (variable: weight 200 to 800, optical size 6 to 72; upright only; SIL Open Font Licence) | Only text a model wrote: a risk's title and its reason. Nowhere else, ever |
| Raw data | The system monospace stack (`ui-monospace, monospace`), not a loaded font | DNS records as read, domain names, the typed-domain field |

The rule "serif means the model wrote it" is checkable on a screenshot and the verifier checks it: no serif outside a risk item, and no risk title or reason in the sans.

**How they load.** With `next/font/local`, from files committed to the repository, not fetched at build or at run time: the build then needs no network, CI stays offline and the page still loads the same in a year.

- `frontend/src/fonts/InstrumentSans-Variable.woff2` and `frontend/src/fonts/Newsreader-Variable.woff2`, the Latin subset of each family's open-source release, with each licence text beside it (`OFL-InstrumentSans.txt`, `OFL-Newsreader.txt`).
- In `src/app/layout.tsx`: two `localFont({ src, variable, display: "swap", weight: "<range>" })` calls giving `--font-instrument-sans` and `--font-newsreader`; both class names go on `<html>`. Only Instrument Sans is preloaded.
- No new package, so nothing to add to `docs/decisions/dependencies.md`. Read `node_modules/next/dist/docs/` for the current `next/font/local` options before writing it.

**Scale.** Sizes in px, line height after the slash. There is nothing smaller than 12.

| Token | 1440 | 390 | Weight, width | Used for |
|---|---|---|---|---|
| `text-title` | 30 / 36 | 24 / 30 | 600, width 82 | The page's one `h1`: "Clients", a client's name, a typed domain |
| `text-heading` | 20 / 28 | 18 / 26 | 600, width 88 | Section headings: "Fixes", "Advisory risks", "What was checked" |
| `text-lead` | 17 / 26 | 16 / 24 | 400, width 100 | The claim sentence, a fix instruction (weight 500), the first line of an empty state |
| `text-body` | 15 / 22 | 15 / 22 | 400 | Default text, buttons (500), table cells |
| `text-small` | 13 / 18 | 13 / 18 | 400 | Captions, facts, chips (500), the limit sentence's caption |
| `text-tag` | 12 / 16 | 12 / 16 | 500 | The "seeded" tag only |
| `text-model-title` | 17 / 24 | 17 / 24 | Newsreader 500 | A risk's title |
| `text-model` | 15 / 23 | 15 / 23 | Newsreader 400 | A risk's reason |
| `text-record` | 13 / 20 | 13 / 20 | monospace 400 | A DNS record as read; breaks anywhere (`overflow-wrap: anywhere`) |

The narrow widths on the two heading sizes (`font-stretch: 82%` and `88%`) are the only place type is used as a visual device: condensed, firm headings over normal-width text. Headings are sentence case. Figures in tables and lists use `font-variant-numeric: tabular-nums` and align right; if the released font file lacks tabular figures the columns still align right, and that is noted in the phase log, not worked around.

Line length: text blocks stop at 68 characters (`max-width: 68ch`); the model's serif text at 62.

### Spacing

A 4 px base. Only these steps are used: **4, 8, 12, 16, 24, 32, 48, 64**. Tailwind 4's default spacing unit (`--spacing: 0.25rem`) already gives them as `1, 2, 3, 4, 6, 8, 12, 16`; no other step appears in a class name.

- Inside an item: 16. Between items in a list: a 1 px line, no gap.
- Between a heading and its list: 12. Between sections: 48 at 1440, 32 at 390.
- Page side padding: 32 at 1440, 16 at 390. Content width stops at 1184.

### Radius

Radius says what a thing is, so there are three, not one:

| Token | Value | Meaning |
|---|---|---|
| `radius-sheet` | 3 px | Holds content: the ink sheet, the pencil box, banners, tables |
| `radius-control` | 6 px | Can be pressed or typed in: buttons, the field, the theme switch |
| `radius-chip` | 999 px | Says a status and cannot be pressed: chips and the seeded tag |

### Borders, not shadows

No `box-shadow` anywhere except the focus ring's outline. A solid 1 px border in `line-strong` means "this is a rule's output or a control". A dashed 1 px border in `pencil-line` means "advisory". A dotted 1 px border means "seeded". A strip of diagonal hatch means "unavailable". Hairlines between rows use `line`.

### Density

Twelve client rows, the header, the claim and the live-check field fit in one 1440 by 900 window without scrolling: rows are 56 high. On a phone a row is three short lines and 96 high. A client page shows all fixes and the first advisory risk above the fold at 1440.

### Motion

Almost none.

- Hover and focus colour changes: 120 ms, `ease-out`.
- A risk marked handled: its row collapses in 160 ms and appears in the handled list. Reopen does the reverse.
- The loading placeholder: opacity moves between 1 and 0.6 over 1.2 s.
- Nothing moves on load, on scroll or between pages.

Under `prefers-reduced-motion: reduce` every duration is 0: the handled row moves at once and the loading placeholder is still. One rule in `globals.css` does this for the whole site.

## 2. Tokens

### How the themes switch

- The default follows the system (`prefers-color-scheme`).
- A switch in the header overrides it. It is a single button that names what it will do: "Dark theme" while the page is light, "Light theme" while it is dark. A press sets `data-theme="dark"` or `data-theme="light"` on `<html>` and saves the choice in `localStorage` under `theme`.
- A short inline script in `<head>` reads `theme` and sets the attribute before the first paint, so a saved choice never flashes. `<html>` carries `suppressHydrationWarning` for that attribute only.
- `make screens` takes its dark shots by emulating the system preference, with nothing saved.
- Components never use Tailwind's `dark:` variant and never name a hex value. They use the tokens, and the tokens change.

### Colour tokens

| Token | Light | Dark | Job |
|---|---|---|---|
| `page` | `#F1F4F2` | `#131C1A` | The ground of every screen. The pencil box sits straight on it |
| `surface` | `#FFFFFF` | `#1B2724` | The ink sheet, tables, the field, secondary buttons |
| `sunk` | `#E6EBE8` | `#0D1513` | Table header rows, the records well, loading placeholders |
| `ink` | `#15201C` | `#E8EEEB` | Primary text; the fix bar; the fix count chip's ground |
| `ink-2` | `#44514C` | `#B7C3BE` | Secondary text; all of the model's wording |
| `ink-3` | `#59665F` | `#98A6A0` | Captions, facts, handled (struck) text, unavailable text |
| `on-ink` | `#FFFFFF` | `#131C1A` | Text on the fix count chip |
| `line` | `#CDD5D1` | `#2F3D39` | Hairlines between rows. Decoration only: never the edge of a control |
| `line-strong` | `#77857F` | `#71827B` | Edges of controls and of the ink sheet |
| `pencil-line` | `#77857F` | `#71827B` | The dashed edge of everything advisory |
| `accent` | `#2446C4` | `#9DB2FF` | Links, the primary button's ground, the focus ring |
| `accent-hover` | `#1B3599` | `#BDCBFF` | Links and the primary button on hover |
| `on-accent` | `#FFFFFF` | `#0E1740` | Text on the primary button |
| `ok` | `#1B6A3C` | `#74D39C` | Healthy, "met", "Found, no problems": text, icon and edge |
| `ok-wash` | `#E2F1E7` | `#143524` | Ground of the healthy band and chip |
| `error` | `#A8231C` | `#FF9A8F` | Refused, failed, "missed": text, icon and edge |
| `error-wash` | `#FBE9E7` | `#42191A` | Ground of an error or refusal message |
| `seeded` | `#84286A` | `#E79ACD` | The seeded tag: text and dotted edge. Used for nothing else |
| `seeded-wash` | `#F6E8F1` | `#3A1B31` | Ground of the seeded tag |
| `notice` | `#5C4200` | `#F3D172` | The fallback banner and "not now" messages: heading text and icon |
| `notice-wash` | `#FCEFC4` | `#3A2E0A` | Ground of a notice |
| `notice-line` | `#8F6A00` | `#B8942E` | Edge of a notice |

### Semantic colours: what each thing looks like

Colour is never the only signal. Each has a shape, an icon and a word as well.

| Meaning | Ground | Edge | Text | Icon | Words |
|---|---|---|---|---|---|
| A rules finding (a fix) | `surface` | solid 1 px `line-strong`, plus a solid 4 px `ink` bar on the left of each fix | `ink`, weight 500 | none | The instruction itself |
| An advisory model risk | `page` (no fill) | dashed 1 px `pencil-line` | `ink-2`, serif | none | "Advisory, unproven" on the box, once, in sans `ink-2` |
| Handled | `page` | none | `ink-3`, struck through | tick in a square | "Handled 20 Nov. Hidden until 20 Dec." |
| Healthy | `ok-wash` | solid 1 px `ok` | `ink`; the label in `ok` | tick in a circle | "Healthy today" / "Nothing to fix" |
| Unavailable | `page`, with a 12 px strip of 45 degree hatch in `line` (1 px every 8 px) down the left edge; the hatch is never behind text | dashed 1 px `pencil-line` | `ink-3` | a dash in a circle | "Risks unavailable today" / "Check not made" |
| Seeded | `seeded-wash` | dotted 1 px `seeded` | `seeded` | none | "seeded" |
| Error or refused | `error-wash` | solid 1 px `error` | `ink`; the first line in `error` | cross in a circle | Says what was refused and what to type instead |
| Notice (fallback, limits) | `notice-wash` | solid 1 px `notice-line` | `ink`; the first line in `notice` | "i" in a circle | Says what is switched off and why |

### Contrast, computed

Computed with the WCAG 2 relative-luminance formula by a short script (not kept in the repository). Text pairs must reach 4.5:1; edges of controls, icons and the focus ring must reach 3:1. `line` is decoration and is not counted. A pair that is not in these tables is not allowed on the page: `ink-3` never sits on a status wash other than `notice-wash`, and status colours never sit on each other's washes.

**Text pairs**

| Text | Ground | Light | Dark |
|---|---|---|---|
| `ink` | `page` | 15.11 | 14.78 |
| `ink` | `surface` | 16.73 | 13.11 |
| `ink` | `sunk` | 13.87 | 15.75 |
| `ink` | `ok-wash` | 14.32 | 11.42 |
| `ink` | `error-wash` | 14.27 | 12.89 |
| `ink` | `seeded-wash` | 14.13 | 12.93 |
| `ink` | `notice-wash` | 14.56 | 11.34 |
| `ink-2` | `page` | 7.50 | 9.57 |
| `ink-2` | `surface` | 8.31 | 8.49 |
| `ink-2` | `sunk` | 6.89 | 10.20 |
| `ink-2` | `ok-wash` | 7.11 | 7.39 |
| `ink-2` | `error-wash` | 7.09 | 8.35 |
| `ink-2` | `seeded-wash` | 7.02 | 8.37 |
| `ink-2` | `notice-wash` | 7.23 | 7.34 |
| `ink-3` | `page` | 5.43 | 6.86 |
| `ink-3` | `surface` | 6.02 | **6.09** |
| `ink-3` | `sunk` | **4.99** | 7.32 |
| `ink-3` | `notice-wash` | 5.24 | 5.27 |
| `on-ink` | `ink` | 16.73 | 14.78 |
| `accent` | `page` | 6.90 | 8.48 |
| `accent` | `surface` | 7.64 | 7.52 |
| `accent` | `sunk` | 6.34 | 9.04 |
| `accent` | `notice-wash` | 6.65 | 6.50 |
| `accent-hover` | `page` | 9.41 | 10.88 |
| `accent-hover` | `surface` | 10.42 | 9.65 |
| `accent-hover` | `sunk` | 8.64 | 11.60 |
| `accent-hover` | `notice-wash` | 9.07 | 8.35 |
| `on-accent` | `accent` | 7.64 | 8.43 |
| `on-accent` | `accent-hover` | 10.42 | 10.82 |
| `ok` | `ok-wash` | 5.66 | 7.38 |
| `ok` | `surface` | 6.62 | 8.47 |
| `ok` | `page` | 5.98 | 9.55 |
| `ok` | `sunk` | 5.49 | 10.18 |
| `error` | `error-wash` | 6.13 | 7.41 |
| `error` | `surface` | 7.19 | 7.54 |
| `error` | `page` | 6.49 | 8.50 |
| `error` | `sunk` | 5.96 | 9.06 |
| `seeded` | `seeded-wash` | 7.11 | 7.17 |
| `seeded` | `surface` | 8.42 | 7.27 |
| `seeded` | `page` | 7.61 | 8.19 |
| `seeded` | `sunk` | 6.99 | 8.73 |
| `notice` | `notice-wash` | 8.18 | 9.00 |

The lowest text pair is 4.99 in the light theme (`ink-3` on `sunk`) and 6.09 in the dark theme (`ink-3` on `surface`).

**Edges, icons and the focus ring (3:1)**

| Mark | Ground | Light | Dark |
|---|---|---|---|
| `line-strong` | `page` | 3.48 | 4.29 |
| `line-strong` | `surface` | 3.86 | 3.80 |
| `line-strong` | `sunk` | **3.20** | 4.57 |
| `line-strong` | `notice-wash` | 3.36 | **3.29** |
| `pencil-line` | `page` | 3.48 | 4.29 |
| `ink` (the fix bar) | `surface` | 16.73 | 13.11 |
| `accent` (focus ring) | `page` | 6.90 | 8.48 |
| `accent` (focus ring) | `surface` | 7.64 | 7.52 |
| `accent` (focus ring) | `sunk` | 6.34 | 9.04 |
| `accent` (focus ring) | `notice-wash` | 6.65 | 6.50 |
| `ok` | `ok-wash` | 5.66 | 7.38 |
| `error` | `error-wash` | 6.13 | 7.41 |
| `seeded` | `seeded-wash` | 7.11 | 7.17 |
| `notice-line` | `notice-wash` | 4.32 | 4.64 |
| `notice-line` | `page` | 4.48 | 6.05 |

The lowest is 3.20 in the light theme and 3.29 in the dark theme.

### The CSS, ready for `globals.css`

This replaces the placeholder tokens in `frontend/src/app/globals.css`. The dark values appear twice on purpose: once for the system preference, once for the switch.

```css
@import "tailwindcss";

:root {
  color-scheme: light;
  --page: #f1f4f2;
  --surface: #ffffff;
  --sunk: #e6ebe8;
  --ink: #15201c;
  --ink-2: #44514c;
  --ink-3: #59665f;
  --on-ink: #ffffff;
  --line: #cdd5d1;
  --line-strong: #77857f;
  --pencil-line: #77857f;
  --accent: #2446c4;
  --accent-hover: #1b3599;
  --on-accent: #ffffff;
  --ok: #1b6a3c;
  --ok-wash: #e2f1e7;
  --error: #a8231c;
  --error-wash: #fbe9e7;
  --seeded: #84286a;
  --seeded-wash: #f6e8f1;
  --notice: #5c4200;
  --notice-wash: #fcefc4;
  --notice-line: #8f6a00;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #131c1a;
    --surface: #1b2724;
    --sunk: #0d1513;
    --ink: #e8eeeb;
    --ink-2: #b7c3be;
    --ink-3: #98a6a0;
    --on-ink: #131c1a;
    --line: #2f3d39;
    --line-strong: #71827b;
    --pencil-line: #71827b;
    --accent: #9db2ff;
    --accent-hover: #bdcbff;
    --on-accent: #0e1740;
    --ok: #74d39c;
    --ok-wash: #143524;
    --error: #ff9a8f;
    --error-wash: #42191a;
    --seeded: #e79acd;
    --seeded-wash: #3a1b31;
    --notice: #f3d172;
    --notice-wash: #3a2e0a;
    --notice-line: #b8942e;
  }
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #131c1a;
  --surface: #1b2724;
  --sunk: #0d1513;
  --ink: #e8eeeb;
  --ink-2: #b7c3be;
  --ink-3: #98a6a0;
  --on-ink: #131c1a;
  --line: #2f3d39;
  --line-strong: #71827b;
  --pencil-line: #71827b;
  --accent: #9db2ff;
  --accent-hover: #bdcbff;
  --on-accent: #0e1740;
  --ok: #74d39c;
  --ok-wash: #143524;
  --error: #ff9a8f;
  --error-wash: #42191a;
  --seeded: #e79acd;
  --seeded-wash: #3a1b31;
  --notice: #f3d172;
  --notice-wash: #3a2e0a;
  --notice-line: #b8942e;
}

@theme inline {
  /* Drop Tailwind's own palette, radii, shadows and breakpoints: only these tokens exist. */
  --color-*: initial;
  --radius-*: initial;
  --shadow-*: initial;
  --breakpoint-*: initial;

  --color-page: var(--page);
  --color-surface: var(--surface);
  --color-sunk: var(--sunk);
  --color-ink: var(--ink);
  --color-ink-2: var(--ink-2);
  --color-ink-3: var(--ink-3);
  --color-on-ink: var(--on-ink);
  --color-line: var(--line);
  --color-line-strong: var(--line-strong);
  --color-pencil-line: var(--pencil-line);
  --color-accent: var(--accent);
  --color-accent-hover: var(--accent-hover);
  --color-on-accent: var(--on-accent);
  --color-ok: var(--ok);
  --color-ok-wash: var(--ok-wash);
  --color-error: var(--error);
  --color-error-wash: var(--error-wash);
  --color-seeded: var(--seeded);
  --color-seeded-wash: var(--seeded-wash);
  --color-notice: var(--notice);
  --color-notice-wash: var(--notice-wash);
  --color-notice-line: var(--notice-line);

  --font-sans: var(--font-instrument-sans), ui-sans-serif, system-ui, sans-serif;
  --font-model: var(--font-newsreader), ui-serif, serif;
  --font-mono: ui-monospace, monospace;

  --radius-sheet: 3px;
  --radius-control: 6px;
  --radius-chip: 999px;

  /* One breakpoint. Below it everything is one column. */
  --breakpoint-wide: 64rem;

  --text-title: 1.5rem;
  --text-title--line-height: 1.875rem;
  --text-heading: 1.125rem;
  --text-heading--line-height: 1.625rem;
  --text-lead: 1rem;
  --text-lead--line-height: 1.5rem;
  --text-body: 0.9375rem;
  --text-body--line-height: 1.375rem;
  --text-small: 0.8125rem;
  --text-small--line-height: 1.125rem;
  --text-tag: 0.75rem;
  --text-tag--line-height: 1rem;
  --text-model-title: 1.0625rem;
  --text-model-title--line-height: 1.5rem;
  --text-model: 0.9375rem;
  --text-model--line-height: 1.4375rem;
  --text-record: 0.8125rem;
  --text-record--line-height: 1.25rem;
}

body {
  background: var(--page);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: 0.9375rem;
  line-height: 1.375rem;
}

/* The three sizes that grow at the wide breakpoint. */
@media (width >= 64rem) {
  :root {
    --text-title: 1.875rem;
    --text-title--line-height: 2.25rem;
    --text-heading: 1.25rem;
    --text-heading--line-height: 1.75rem;
    --text-lead: 1.0625rem;
    --text-lead--line-height: 1.625rem;
  }
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0s !important;
    transition-duration: 0s !important;
  }
}
```

If Tailwind 4 does not let a `--text-*` theme value be overridden from `:root` inside a media query as written, set the three wide sizes with the `wide:` variant on the heading components instead; the sizes in the type table are what count.

## 3. Layout rules

### The grid

- One breakpoint, `wide`, at 1024 px. At 1440 everything described as "1440" applies; at 390 everything is one column.
- Content is left aligned, always. Nothing is centred except the text inside a button.
- 1440: content width 1184, side padding 32, twelve columns, gutter 32.
- 390: side padding 16, content 358 wide. Nothing has a fixed width above 358. Long strings (records, domains) wrap anywhere. No element scrolls sideways, tables included: at 390 a table becomes a list of labelled rows.

### The product rule, as layout

The owner's rule: the rules drive the action list; the model's risks are beside it, marked advisory and unproven, never ranked above a rules finding, with a plain link to the eval result. Every one of these is a layout rule the verifier can check on a screenshot.

1. **Fixes are first in the document.** In the HTML, the fixes section comes before the advisory section on every page that has both. Reading order, tab order and the phone layout all follow from that.
2. **1440: fixes take columns 1 to 7, advisory risks take columns 8 to 12.** The advisory box starts 32 px lower than the fixes sheet, so no advisory item is ever higher on the screen than the first fix.
3. **390: the advisory box is below the fixes sheet,** after all fixes, with 32 between them.
4. **The fixes sheet never disappears.** With no fixes it shows its empty state in the same place and the advisory box stays in its own place. Risks never move into the left column or to the top.
5. **The advisory box always opens with the same three things,** in this order, before any risk: the heading "Advisory risks"; the line "Advisory, unproven."; the sentence and link below. They are not hidden behind a tooltip or a disclosure.

   > Advisory, unproven. A model picked these from a fixed list of risk types. On this project's evals a table of rules did better than the model, so read them as things to look at, not things to do. [See the eval result](/evals)

   The link text is "See the eval result". It is an ordinary underlined link to `/evals`.
6. **In any list of clients, fixes decide the order.** Clients sort by number of fixes, most first, then by name. The advisory count never sorts or filters anything, and its chip sits to the right of the fixes chip (below it at 390).
7. **Weight.** A fix instruction is `text-lead`, weight 500, `ink`. A risk title is `text-model-title`, `ink-2`. No advisory text is larger, bolder or darker than a fix instruction.
8. **Counts.** The heading "Fixes" carries its count in the ink chip. The heading "Advisory risks" carries its count in a dashed chip.

### The claim and its limit

Wherever the claim sentence is shown (the client list and "About this demo"), its limit is shown with it, in the same block, at the same time: never on a second line of a collapsed panel, never behind a link.

- The claim comes from `CLAIM` in `frontend/src/content/claim.ts`, unchanged.
- The limit is the sentence in `docs/SPEC.md` under "Claim", copied word for word into a constant `LIMIT` in a new file `frontend/src/content/limit.ts`:

  > On this project's evals a table of rules does better on the risk list than the model: it meets all four bars over the forty-eight cases and no prompt version did (on the thirty table cases the labels are that table's own output; on the eighteen open cases, in each of the three runs, the model found one more expected risk than the table, 18 of 25 against 17, and returned three wrong ones to its none).

- 1440: one block, two columns under a single 1 px `line-strong` top rule. Columns 1 to 7: the caption "What this is" (`text-small`, `ink-3`) and the claim in `text-lead`, `ink`. Columns 8 to 12: the caption "Its limit" and the limit in `text-body`, `ink`, followed by the link "See the eval result". The two columns start on the same line.
- 390: the claim, then 16, then the limit directly under it, both inside the same ruled block.
- The limit is in `ink`, not a muted colour. It is smaller than the claim only because it is longer.

### Seeded labels

- Every figure that is not real carries the seeded tag immediately after its label: "Reputation `seeded`", "Complaint rate `seeded`", and so on for bounce rate, weekly volume, open rate, blocklist status and domain age.
- Each seeded client's page carries one line under its title: "Seeded client. Its figures and its DNS answers are made up for this demo." with the link "About this demo".
- A seeded client's DNS checks carry the tag too ("SPF `seeded`"), because their answers come from fixture zones.
- A fix shows its source as words: "From DNS" or "From seeded figures". On a seeded client both are followed by the seeded tag.
- On the live check nothing is seeded. Its checks carry a solid `ok`-edged tag "Live DNS" instead, and there are no figures.
- The client list carries one line above the table: "Twelve invented clients on `.example` domains. Their figures are seeded." It does not tag each row.

### Snapshot facts

On a client page, directly under the seeded line, a definition list in `text-small` (`ink-3` labels, `ink` values). 1440: one row of three pairs, 32 apart. 390: stacked, one pair per line.

| Label | Value, with an example |
|---|---|
| Snapshot | The snapshot's UTC day: "20 Nov 2026 (UTC)" |
| Prompt version | The number from the snapshot: "3" |
| Model output | "Recorded from a real model run, not generated on this visit" |

When risks are unavailable, "Prompt version" still shows and "Model output" reads "Dropped: it did not pass its checks". On the live check the facts are "Checked" (time, UTC) and "Model output: none for a typed domain".

Dates are written "20 Nov 2026". Times are 24-hour UTC, "14:02 UTC".

## 4. Screens and states

### Routes

| Screen | Route |
|---|---|
| Client list | `/` |
| Client page | `/clients/[id]` (the seeded id, for example `/clients/harbourlight-books`) |
| Report | `/clients/[id]/report`, and `/clients/[id]/report.md` for the same report as a Markdown file |
| Live check | `/check` and `/check?domain=<typed>` |
| Eval table | `/evals` |
| About this demo | `/about` |
| Admin sign-in | `/admin` |

### The demo flag

Some states cannot be reached by clicking, or depend on the day. A query flag, `?demo=<name>`, makes the page render that state from a fixed view bundled with the frontend (`frontend/src/data/demo-states.ts`). The flag only changes what is drawn: it never writes, never signs anyone in and never calls the backend. While a flag is on, the footer shows, in `text-small` on a notice ground: "Showing a demo state: <name>. Remove `?demo` from the address for live data." `make screens` uses a flag for every state so the 68 files are the same on any day.

### Shared chrome

**Header.** 56 high at 1440, a 1 px `line` rule below, `page` ground. Left: the wordmark "domain-health" in `text-body`, weight 600, width 82, a link to `/`. Then the navigation, 24 apart: "Clients", "Check a domain", "Evals", "About this demo". The current page's link is `ink` with a 2 px `ink` underline; the others are `ink-2`, underlined on hover. Right: the theme switch, a secondary button 36 high reading "Dark theme" or "Light theme".

At 390 the header is two rows, 104 high: row one, the wordmark and the theme switch (44 high); row two, the four links reading "Clients", "Check", "Evals", "About", each with a 44 high hit area, spread across the 358. There is no menu button.

**Skip link.** The first focusable thing on every page: "Skip to content". Hidden until focused, then shown top left on `surface` with the focus ring.

**Footer.** 48 above it, a 1 px `line` rule, `text-small`, `ink-3`: "A public rebuild on seeded data. The twelve clients are invented." then the links "About this demo", "Source" (the repository address from an environment variable; left out if unset) and "Admin sign-in". Links are 44 high at 390.

**Admin bar.** Only when signed in as admin, directly under the header, full width, `notice-wash` ground, `notice-line` rule below, 40 high at 1440 (wraps at 390): the "i" icon, "Signed in as admin. Handled and reopen change the shared list, not a visitor's own." and a quiet button "Sign out".

### Components

Icons are inline SVG, 16 px, 1.5 px stroke, `currentColor`, each beside a word. There are six: tick in a circle, tick in a square, empty square, cross in a circle, dash in a circle, "i" in a circle. No icon package.

| Component | 1440 | 390 |
|---|---|---|
| **Button, primary** (`accent` ground, `on-accent` text, weight 500, radius 6; hover `accent-hover`) | 40 high, 16 side padding | 44 high; full width when it is the only action in a form |
| **Button, secondary** (`surface` ground, 1 px `line-strong` edge, `ink` text; hover edge `ink`) | 40 high | 44 high |
| **Button, quiet** (no ground or edge, `accent` text, underlined) | 40 high | 44 high |
| **Button, disabled** (any kind: `page` ground, dashed 1 px `line-strong` edge, `ink-3` text, `aria-disabled`, with a sentence nearby saying why) | same | same |
| **Field** (`surface`, 1 px `line-strong`, radius 6, monospace 16 px, 12 side padding; label above in `text-small` weight 500) | 44 high, 420 wide | 44 high, full width |
| **Status chip** (radius 999, `text-small` weight 500, 8 side padding, icon 14 then 4) | 24 high | 24 high |
| **Seeded tag** (radius 999, `text-tag`, 6 side padding, dotted edge) | 20 high | 20 high |
| **Client list row** | 56 high, a grid: name and domain (flexible), fixes chip (176), advisory chip (176), snapshot (152); 16 side padding | 96 high or more, stacked: name; domain; the two chips on one line; snapshot. 12 top and bottom, 16 sides |
| **Fix item** | 16 padding, 4 px `ink` bar on the left edge; instruction, then 8, then the source line | the same, full width |
| **Risk item** | 16 padding; title, 4, reason, 8, "Based on" line, 12, the "Mark handled" button | the same; the button is full width |
| **Handled item** | one line, 44 high: tick in a square, struck title, the dates, "Reopen" on the right | two lines: struck title and dates; "Reopen" below, full width |
| **Live-check form** | label, then field and primary button on one line, 8 apart, then the hint | label, field, button and hint stacked, 8 apart |
| **Banner** (notice or error; radius 3; icon, first line weight 600, body `ink`) | 16 padding; full content width | 12 padding |
| **Fallback banner** | full window width under the header, `notice-wash`, `notice-line` rule below, 12 top and bottom, text aligned to the content grid | the same, text wraps |

**Status chips, complete list.**

| Chip | Look | Text |
|---|---|---|
| Fixes | `ink` ground, `on-ink` text, no icon | "1 fix", "3 fixes" |
| Nothing to fix | `ok-wash`, 1 px `ok` edge, `ok` text, tick in a circle | "Nothing to fix" |
| Advisory | no ground, dashed 1 px `pencil-line`, `ink-2` text | "2 advisory" |
| No advisory | no ground, dashed 1 px `pencil-line`, `ink-3` text | "No advisory" |
| Unavailable | no ground, dashed 1 px `pencil-line`, `ink-3` text, dash in a circle | "Risks unavailable" |
| Met | `ok-wash`, 1 px `ok`, `ok` text, tick in a circle | "met" |
| Missed | `error-wash`, 1 px `error`, `error` text, cross in a circle | "missed" |
| Live DNS | `surface`, 1 px `ok`, `ok` text | "Live DNS" |
| Admin | `notice-wash`, 1 px `notice-line`, `notice` text | "Admin" |

**Fix item, in full.** The instruction is the rule's own text from the snapshot, unchanged (for example "Publish an SPF record for this domain that lists every service that sends its mail."). The source line, `text-small`, `ink-3`: "From DNS" or "From seeded figures", then the seeded tag where it applies. Fixes are in the order the snapshot gives them and are not numbered: they are not steps.

**Risk item, in full.** Title and reason are the model's text, unchanged, rendered as text and never as HTML, in Newsreader. The "Based on" line is sans `text-small`, `ink-3`: "Based on: " then the evidence field names in plain words, joined with commas (see the table below). Then the secondary button "Mark handled", with the empty-square icon before the words. Items are separated by a dashed 1 px `pencil-line`. Risks keep the order the snapshot gives them and carry no numbers.

| Evidence field | Plain words |
|---|---|
| `spf` fields | "the SPF record" |
| `dkim` fields | "the DKIM keys" |
| `dmarc` fields | "the DMARC record" |
| `reputation` fields | "reputation grade" |
| `complaint_rate_pct` | "complaint rate" |
| `bounce_rate_pct` | "bounce rate" |
| `volume_7d`, `volume_prev_7d` | "weekly volume" |
| `open_rate_pct`, `open_rate_prev_pct` | "open rate" |
| `blocklist` fields | "blocklist history" |
| `domain_age_days` | "domain age" |

Phase 5 fills this table from the real field names in `SnapshotInput`; a field with no entry shows its own name, and a test lists any that do.

**Handled and reopen.** One action, one name all the way through: the button says "Mark handled", the result says "Handled".

- Pressing "Mark handled" moves the risk out of the list at once and into "Handled" below it, and moves focus to that item's "Reopen" button. A polite live region says "Marked handled. Hidden until 20 Dec."
- If a sixth risk was waiting, it appears at the end of the list and a line under the list says: "1 handled. The next risk moved into the list."
- "Reopen" puts the risk back in its place. The live region says "Reopened."
- If the save fails, the change is undone and an error banner appears above the list: "That did not save, so nothing changed. Try again."
- Under the "Handled" heading, one line says whose list it is. A visitor: "Only you see these ticks. They reset a day after your first one." Admin: "These ticks are on the shared list. Visitors do not see it: each has a list of their own."

### Wireframes

Client list, 1440:

```
+--------------------------------------------------------------------------------+
| domain-health   Clients  Check a domain  Evals  About this demo   [Dark theme] |
+--------------------------------------------------------------------------------+
| What this is                              | Its limit                          |
| A daily email-domain health check for     | On this project's evals a table of |
| many clients: clear-cut fixes from ...    | rules does better ... See the eval |
|                                           | result                             |
+--------------------------------------------------------------------------------+
| Check any domain                                                               |
| Domain                                                                         |
| [ example.com                  ] [Check domain]   Real DNS lookups. No sign-in.|
+--------------------------------------------------------------------------------+
| Clients                                                                        |
| Twelve invented clients on .example domains. Their figures are seeded.         |
| Client                         Fixes            Advisory        Snapshot       |
| Copperkettle Kitchen           (2 fixes)        ( 1 advisory )  Today          |
|   copperkettle-kitchen.example                                                 |
| Harbourlight Books             (Nothing to fix) ( No advisory ) Today          |
+--------------------------------------------------------------------------------+
```

Client page, 1440:

```
| Clients / Northwind Cycles                                                     |
| Northwind Cycles                                                               |
| northwind-cycles.example                                                       |
| Seeded client. Its figures and its DNS answers are made up for this demo.      |
| Snapshot 20 Nov 2026 (UTC)   Prompt version 3   Model output Recorded from ... |
|                                                                                |
| Fixes (2 fixes)                             |                                  |
| Found by rules. Each has one correct fix.   |  Advisory risks ( 2 advisory )   |
| +-----------------------------------------+ |  + - - - - - - - - - - - - - - + |
| |# Publish a DKIM key for this domain ... | |  : Advisory, unproven. A model : |
| |  From DNS  (seeded)                     | |  : picked these ... See the    : |
| |-----------------------------------------| |  : eval result                 : |
| |# Publish a DMARC record for this ...    | |  : - - - - - - - - - - - - - - : |
| |  From DNS  (seeded)                     | |  : A new domain sending volume : |
| +-----------------------------------------+ |  : (serif reason text)         : |
|                                             |  : Based on: domain age, ...   : |
|                                             |  : [ Mark handled ]            : |
|                                             |  + - - - - - - - - - - - - - - + |
|                                             |  Handled                         |
| What was checked                                                               |
| SPF (seeded)  Found, no problems   v=spf1 include:... ~all                     |
| ...                                                                            |
| Figures                                                                        |
| Reputation (seeded)  high, was high      Complaint rate (seeded)  0.04%        |
```

Client page, 390: title block; "Fixes" sheet; 32; "Advisory risks" box; "Handled"; "What was checked"; "Figures". One column, in that order.

### Screen: client list (`/`)

In order: the claim block; the live-check form under the heading "Check any domain"; the heading "Clients" (the page's `h1`) with the seeded line; the table.

- Table header (`sunk` ground, `text-small`, `ink-2`): "Client", "Fixes", "Advisory", "Snapshot". At 390 there is no header row; each row's chips say what they are.
- A row: the client's name (`text-body`, weight 600, `ink`, a link whose hit area covers the whole row), its domain below in monospace `text-small` `ink-3`; the fixes chip or "Nothing to fix"; the advisory chip; the snapshot cell, "Today" or the date with "No snapshot today".
- Row hover: `surface` ground. Row focus: the focus ring around the whole row.
- Order: most fixes first, then by name.
- The live-check form's hint: "Real DNS lookups for SPF, DKIM and DMARC. No sign-in." Submitting goes to `/check?domain=<typed>`.

### Screen: client page (`/clients/[id]`)

In order: a breadcrumb link "Clients" (`text-small`); the client's name as `h1`; its domain in monospace; the seeded line; the snapshot facts; the secondary button "Open report"; then the two columns; then "What was checked"; then "Figures".

- **Open report.** A link drawn as a secondary button, directly under the snapshot facts, to `/clients/[id]/report`. Full width at 390. It is there whenever a snapshot is shown, demo states included; from a demo state it opens the client's live report, without the flag. It takes the focus ring like any other control.

- **Fixes.** Heading "Fixes" with the count chip. Under it, `text-small` `ink-3`: "Found by rules. Each has one correct fix." Then the ink sheet with one fix item per fix.
- **Advisory risks.** Heading "Advisory risks" with the dashed count chip, then the pencil box: the advisory sentence and link, then the risk items. Under the box, the "Handled" list if there is anything in it.
- **What was checked.** Three rows on a `surface` table: "SPF", "DKIM", "DMARC", each with the seeded tag, a status in words with its icon ("Found, no problems" in `ok` with the tick; "Problem found" in `ink` with the cross, followed by the problems in plain words from the snapshot; "Check not made" in `ink-3` with the dash), and the records as read in a `sunk` well in `text-record`. At 390 each check is a block: name and status on one line, records below.
- **Figures.** A list of label, seeded tag, value, in two columns at 1440 and one at 390. Values say their previous reading in words where there is one: "Reputation `seeded` medium, was high"; "Complaint rate `seeded` 0.04%"; "Bounce rate `seeded` 0.8%"; "Weekly volume `seeded` 6,200, was 6,000"; "Open rate `seeded` 41%, was 40%"; "Blocklist `seeded` Not listed. 0 listings in 90 days"; "Domain age `seeded` 400 days". No colour is put on a figure: whether a figure is a problem is the fix list's job.

### Screen: report (`/clients/[id]/report`)

One snapshot as a document to hand to a client: one column, in the site's chrome, read only. It is built from the same view as the client page, so it is the list as this visitor sees it, and from the saved snapshots when the live service cannot be reached.

In order: a breadcrumb link back to the client's page; the secondary button "Download as Markdown" (the same report as a file, `<client id>-<day>.md`) with a line in `text-small` saying the page prints without the header, footer and buttons; the `h1` "Domain health report: <client>"; the facts, stacked at both widths: "Client", "Domain" (monospace), "Snapshot", "Prompt version", "Model output", worded as on the client page; the line "This client is invented. Its figures and its DNS answers are made up for this demo."; when the saved snapshots are showing, "From saved data. The live service could not be reached, so this report is built from the snapshot saved with this site on <day>."; then four sections, each an `h2`, always in this order.

- **Authentication.** A `surface` sheet with a block each for SPF, DKIM and DMARC: the name with the seeded tag, the status in words, the problems in plain words, and the records as read in a `sunk` well.
- **Reputation.** Reputation, blocklist, complaint rate and domain age, each label with the seeded tag, in the client page's words.
- **Sending.** Weekly volume, bounce rate and open rate, the same way.
- **Actions.** The product rule holds here as on the page. First "Fixes": the line "Found by rules. Each has one correct fix.", then the ink sheet with the fixes numbered, each with its source and the seeded tag, or "Nothing to fix today. Every rule passed." Only after every fix, 32 lower, "Advisory risks" in `ink-2`: the pencil box, opening with "Advisory, unproven.", the sentence and the link "See the eval result" before any risk, then the risks in the serif with no numbers and no buttons, or the same empty and unavailable wording as the page. A handled risk is not in that list: it is named under it, struck through, with its dates.

No snapshot: the `h1`, then the notice "No snapshot for today yet" with "The daily run has not reached this client, so there is nothing to report. No report was made." An unknown client is the "No such client" page. The Markdown file answers 404 in both cases.

On paper (`@media print`) the header, footer, strips, breadcrumb and every button are left out, and the page prints in the light theme's colours on white whichever theme the screen is in. A check, a figure, a fix or a risk is not split across two sheets.

### Screen: live check (`/check`)

In order: `h1` "Check a domain"; one sentence, "Type any public domain. This runs real DNS lookups for SPF, DKIM and DMARC and lists what to fix."; the form (label "Domain", placeholder `example.com`, button "Check domain"); the hint, `text-small` `ink-3`: "Five checks per ten minutes. Results are kept for ten minutes."; then the result area.

The result uses the client page's layout so the two read alike: the typed domain as a heading in monospace with the "Live DNS" chip; the facts ("Checked 14:02 UTC", "Model output: none for a typed domain"); "Fixes" on the left; on the right, where advisory risks would be, an empty pencil box (see state 11); then "What was checked" with no seeded tags. There is no "Figures" section.

### Screen: eval table (`/evals`)

Every number on this screen is read from `evals/results.json` at build time. Nothing is typed in by hand, and a value the file does not hold is not shown.

In order:

1. `h1`: "How the model's list scored".
2. The finding, in `text-lead`: "The evals were written before the prompt. They showed that a table of rules does better than the model on this task, so the product ships that way: rules write the fix list, and the model's risks are advisory."
3. The limit sentence (`LIMIT`), in `text-body`.
4. Facts, as a definition list: "Prompt version", "Model", "Recorded" (date), "Cases" ("48, three runs each: 144 case-runs").
5. Heading "The four bars". A table: "Measure", "Bar", "Model", "Result". Rows: "Coverage", "Precision", "Harmful", "Stability". Bars read "at least 0.80", "at least 0.80", "exactly 0", "at least 0.90". Scores show three decimals. Harmful is written as a count: "9 in 144 case-runs". The result cell is the "met" or "missed" chip. Under the table, one sentence that names every missed bar in words, built from the file: for example "One bar is missed: harmful. The model returned a risk the label calls wrong 9 times in 144 case-runs."
6. Heading "By set, beside rules alone". A table: "Set", "Measure", "Model", "Rules only". Two groups of rows, "Table cases (30)" and "Open cases (18)", each with coverage, precision and harmful. Under it: "On the table cases the labels are the rules table's own output, so rules alone score full marks there by construction."
7. Heading "Not in use". One row for each entry in the file's `not_in_use` list: prompt version and its four scores, with "Did worse than the version in use. Why is not established."
8. Heading "Where the labels came from": "Drafted by AI against a written rubric and public guidance, and reviewed by the engineer who built the original system. Not written or reviewed by a deliverability specialist."
9. A link: "Read the rubric, the cases and the full results in the repository" (left out if the repository address is unset).

At 390 each table becomes a list: one block per measure, with "Bar", "Model", "Rules only" and "Result" as labelled lines.

### Screen: about this demo (`/about`)

`h1`: "About this demo". Text blocks at 68 characters, in this order:

1. The claim block, exactly as on the client list (claim and limit together).
2. Heading "What is real": "The DNS checks. Type any public domain and the page looks up its SPF, DKIM and DMARC records and lists what to fix."
3. Heading "What is seeded": "The twelve clients, their reputation grades, blocklist status and sending figures. Those come from accounts this demo does not have, so they are made up. The clients' DNS answers come from fixed zone files. Everything seeded carries this tag: `seeded`."
4. Heading "What the model does here": "For each seeded client, a model picked risks from a fixed list. What you see was recorded from real model runs and is replayed. Nothing is generated on your visit, and a typed domain gets no model output at all. The risks are advisory: on this project's evals, rules did better." Then the link "See the eval result".
5. Heading "Marking a risk handled": "Marking a risk handled hides it for thirty days. Your ticks are yours alone and reset a day after your first one. Other visitors do not see them."
6. Heading "What this rebuilds": "A deliverability monitor built for a client's internal platform, rebuilt in public on invented data."

### Screen: admin sign-in (`/admin`)

A single column 420 wide at 1440, full width at 390, left aligned. `h1`: "Admin sign-in". One sentence: "For the owner. Signing in lets handled and reopen change the shared list. Visitors do not need to sign in." Label "Passphrase", a password field (sans, not monospace), the primary button "Sign in".

### The 17 states

Each is one screenshot target. "Flag" is the address `make screens` uses; "Seeded" is where a visitor meets it.

| # | State | Screen | Flag | Seeded |
|---|---|---|---|---|
| 1 | Loading | Client list | `/?demo=loading` | Any slow load |
| 2 | Healthy, nothing to do | Client page | `/clients/harbourlight-books?demo=healthy` | Harbourlight Books, both days |
| 3 | Fixes only | Client page | `/clients/copperkettle-kitchen?demo=fixes-only` | Expected: Copperkettle Kitchen |
| 4 | Risks only | Client page | `/clients/oakhaven-outfitters?demo=risks-only` | Oakhaven Outfitters, all three days |
| 5 | Both | Client page | `/clients/northwind-cycles?demo=both` | Northwind Cycles, both days |
| 6 | A handled risk, the next one moved up | Client page | `/clients/oakhaven-outfitters?demo=handled-one` | Any client with risks, after one "Mark handled" |
| 7 | Everything handled | Client page | `/clients/oakhaven-outfitters?demo=all-handled` | Any client with risks, after marking each |
| 8 | Risks unavailable | Client page | `/clients/northwind-cycles?demo=risks-unavailable` | Any seeded day whose recording was not kept |
| 9 | No snapshot today | Client page | `/clients/driftwood-coffee?demo=no-snapshot` | Any client before the daily run |
| 10 | Live check running | Live check | `/check?domain=example.com&demo=running` | Between pressing "Check domain" and the answer |
| 11 | Live check result | Live check | `/check?domain=example.com&demo=result` | Type `example.com` |
| 12 | Live check refused | Live check | `/check?domain=192.0.2.1&demo=refused` | Type an IP address |
| 13 | Rate limited | Live check | `/check?domain=example.com&demo=rate-limited` | A sixth check in ten minutes |
| 14 | Daily cap reached | Live check | `/check?domain=example.com&demo=cap-reached` | After 200 checks in a day |
| 15 | Backend unreachable (fallback) | Client list | `/?demo=fallback` | The backend not answering |
| 16 | Admin signed in | Client page | none: the script signs in with the local passphrase, then opens `/clients/oakhaven-outfitters` | Sign in at `/admin` |
| 17 | Sign-in refused | Admin sign-in | `/admin?demo=refused` | A wrong passphrase |

Which seeded client shows states 2 to 5 without a flag depends on the recordings Phase 4 makes; Phase 5 checks the "Seeded" column against them, corrects a name if a recording differs, and says so in its log.

**1. Loading.** The header, the claim block and the form are real. Where the table will be: the heading "Clients", the visible line "Loading today's snapshots", and six placeholder rows, each 56 high (96 at 390), with two `sunk` bars (40% and 25% wide, 12 high). The region has `aria-busy="true"`. A client page loads the same way: the breadcrumb, then "Loading this client's snapshot", then a placeholder sheet on the left and a placeholder dashed box on the right.

**2. Healthy, nothing to do.** Above the two columns, a full-width band on `ok-wash` with a 1 px `ok` edge and the tick: first line "Healthy today", second line "Nothing to fix and no advisory risks." The fixes sheet shows its empty state: "Nothing to fix today. Every rule passed." The pencil box still opens with the advisory sentence and link, then: "No advisory risks today. The model raised nothing for this client." "What was checked" and "Figures" show as usual.

**3. Fixes only.** The fixes sheet with its fixes. The pencil box as in state 2: "No advisory risks today. The model raised nothing for this client." Chips: "2 fixes", "No advisory". No healthy band.

**4. Risks only.** The fixes sheet, in its place, with the empty state and the "Nothing to fix" chip beside its heading: "Nothing to fix today. Every rule passed." The pencil box with its risks. No healthy band: the band needs both lists empty. The advisory column does not move left.

**5. Both.** The full layout in the wireframe above.

**6. A handled risk, the next one moved up.** The view is built with six ranked risks, the first marked handled. The pencil box shows five risks, the last being the one that moved up, and under the list: "1 handled. The next risk moved into the list." Below the box, the heading "Handled" with one handled item: the tick in a square, the title struck through in `ink-3`, "Handled 20 Nov. Hidden until 20 Dec.", and the secondary button "Reopen". Then the line saying whose ticks these are. The advisory chip counts visible risks only.

**7. Everything handled.** The pencil box opens with the advisory sentence and link, then: "Every advisory risk is handled. Each one comes back after thirty days, or when you reopen it." Under it, "Handled" lists every risk with its "Reopen" button. The advisory chip reads "No advisory". The fixes sheet is unchanged: handled never applies to a fix.

**8. Risks unavailable.** Fixes show as usual. The pencil box has the hatch strip down its left edge and the dash icon: first line "Risks unavailable today", then "The model's answer did not pass its checks, so it was dropped, not repaired. The fixes do not depend on it." The advisory sentence and the eval link still show above. No "Mark handled" buttons. The fact "Model output" reads "Dropped: it did not pass its checks". On the client list this client's chip is "Risks unavailable".

**9. No snapshot today.** Under the title, a notice banner: first line "No snapshot for today yet", then "The daily run has not reached this client." If an earlier snapshot is served, the banner adds "Showing the latest one, from 19 Nov 2026." and the page shows it, with the "Mark handled" buttons disabled and the sentence "Handled can be marked on today's snapshot only." If no snapshot exists, the banner stands alone with the link "Back to clients" and the two columns are not drawn. On the client list the snapshot cell reads "No snapshot today".

**10. Live check running.** The field keeps the typed domain and is read-only. The button is disabled and reads "Checking". Under the form, in a live region: "Looking up DNS records for example.com. This takes a few seconds." Then the "What was checked" table with its three rows, "SPF", "DKIM", "DMARC", each reading "Looking up" in `ink-3` with a placeholder bar where the record will be. The two columns are not drawn yet.

**11. Live check result.** Heading: `example.com` in monospace with the "Live DNS" chip. Facts: "Checked 14:02 UTC" and "Model output: none for a typed domain". A result from the cache adds: "This result is 4 minutes old. Results are kept for ten minutes." Left: "Fixes" with the count chip and the fix items, each with the source line "From DNS"; or the empty state "Nothing to fix. SPF, DKIM and DMARC all passed these checks." Right: the pencil box with the heading "Advisory risks" and only this: "None for a typed domain. Advisory risks need reputation and sending figures, and this demo has those for its seeded clients only." with the link "See a seeded client" to `/`. Below: "What was checked" with the records as read. A check that did not answer reads "Check not made" with "The lookup did not answer in time, so nothing is assumed. No fix is listed for it."

**12. Live check refused.** The field keeps what was typed, gets a 2 px `error` edge and `aria-invalid`, and is tied to the message by `aria-describedby`. Under the form, an error banner with the cross icon. First line: "That is not a domain this can check". Second line, by reason:

| Reason | Second line |
|---|---|
| An IP address | "That is an IP address. Type a domain name, like example.com." |
| A single label | "A domain name has at least two parts, like example.com." |
| Too long | "That is longer than a domain name can be (253 characters)." |
| A reserved name | "That name is reserved, so no one can send mail from it." |
| An internal name | "That is an internal name, not a public domain." |
| A scheme or a path | "That is a web address. Leave out everything but the domain, like example.com." |
| A port | "Leave out the port. Type the domain only, like example.com." |
| Anything else | "That is not a domain name. Type one like example.com." |

Nothing is looked up, and the banner's last line says so: "No lookup was made."

**13. Rate limited.** A notice banner under the form, with the "i" icon: first line "Five checks in ten minutes is the limit", then "Wait a few minutes and try again. The seeded clients are not limited." with the link "See the clients". If the API gives the time the limit lifts, the second line begins "Try again at 14:12 UTC." The form stays usable.

**14. Daily cap reached.** A notice banner under the form: first line "Today's 200 checks are used up", then "This demo stops at 200 live checks a day. It opens again at 00:00 UTC. The seeded clients still work." with the link "See the clients". The field is read-only and the button is disabled.

**15. Backend unreachable (fallback).** The fallback banner, full width under the header on every page while it lasts: first line "Showing saved data", then "The live service cannot be reached. These are the snapshots saved with this page on 20 Nov 2026. Marking handled and the live check are switched off until it is back." The client list and client pages render from the bundled snapshots, and the snapshot fact shows the saved date. "Mark handled" and "Reopen" are disabled. The live-check button is disabled, with the line "Switched off while the live service cannot be reached." under the form. `/evals` and `/about` are unaffected.

**16. Admin signed in.** The admin bar under the header. The "Admin" chip after the client's name. Under "Handled": "These ticks are on the shared list. Visitors do not see it: each has a list of their own." Everything else is the same page. After signing out, the page returns to `/` with a live-region message "Signed out."

**17. Sign-in refused.** The field is emptied, gets a 2 px `error` edge and `aria-invalid`, and takes focus. An error banner above the form: first line "That passphrase is not right", then "Nothing was changed. Try again." After too many tries the banner is a notice: first line "Too many tries", then "Wait a few minutes before trying again." The message never says how close the passphrase was.

### Messages used in more than one place

| Where | Text |
|---|---|
| Any page that fails to load for another reason | First line "This page did not load", then "Something went wrong on our side. Reload the page." with the secondary button "Reload" |
| A client id that does not exist | `h1` "No such client", then "There is no client at this address." and the link "Back to clients" |
| Any other address | `h1` "Nothing here", then the link "Back to clients" |
| The page title in the browser tab | "<Screen or client name> - domain-health" |

## 5. Accessibility

**Focus.** Every control shows a 2 px solid `accent` outline, 2 px off its edge, on `:focus-visible`. It is never removed and never replaced by a colour change alone. The ring's contrast against every ground it can sit on is at least 6.34 in light and 6.50 in dark (see the table). On a client list row the ring goes around the whole row. Focus is moved by code in three places only: to "Reopen" after "Mark handled", back to the risk's "Mark handled" after "Reopen", and to the field after a refused sign-in.

**Keyboard order.** The order is the document order, and the document order is the reading order: skip link; wordmark; the four navigation links; the theme switch; the admin bar's "Sign out" when present; then the main content from top to bottom. On a client page that is: breadcrumb; (fixes have no controls); the eval link in the advisory box; each risk's "Mark handled" in list order; each handled item's "Reopen"; then the footer links. At 1440 the two columns are read left then right, which is the same order. No `tabindex` above 0. Everything works with Enter and Space; nothing needs a pointer or a hover.

**Structure.** One `h1` per page. "Fixes", "Advisory risks", "Handled", "What was checked" and "Figures" are `h2`. Lists are real lists, tables are real tables with header cells, and at 390 the tables are definition lists. The header, main and footer are landmarks. The two columns are `section`s named by their headings.

**Hit targets.** At 390 every control is at least 44 by 44, links in the header and footer included. At 1440 buttons are 40 high, the theme switch 36, and the field 44. Controls are at least 8 apart. A link inside a sentence is exempt and is always underlined.

**Colour is never the only signal.**

- A fix: a solid bar, a solid sheet, sans text. A risk: a dashed box, serif text and the words "Advisory, unproven".
- Handled: a tick, a strike-through and the word "Handled" with dates.
- Healthy, met, missed, refused, unavailable: each has its own icon and its own word.
- Seeded: a dotted edge and the word "seeded".
- Links are underlined. The current navigation link has an underline bar and `aria-current="page"`.
- A field in error has a thicker edge, an icon and a message tied to it.

**Announcements.** One polite live region per page carries: "Marked handled. Hidden until 20 Dec.", "Reopened.", "Signed out.", the live check's "Looking up DNS records for example.com." and "Check finished: 2 fixes." Errors and refusals use `role="alert"`. The loading region uses `aria-busy`.

**Reduced motion.** With `prefers-reduced-motion: reduce`, nothing animates: the handled row moves at once, the loading placeholder holds still, and colour changes are instant. No information is carried by motion in either mode.

**Text.** Nothing below 12 px. The page holds at 200% zoom and with text spacing increased, because nothing has a fixed height except the header at 1440 and no text is cut off with an ellipsis: long names and records wrap. `lang="en"` is set. Dates are written out so no one has to guess the order of day and month.

**What the verifier checks against this file.** In each of the 68 screenshots: every text and ground pair is one in the contrast table; no sideways scroll at 390; a visible focus ring on every control (tabbed through once per screen); the fixes section before and never below the advisory box; "Advisory, unproven" and the link "See the eval result" present wherever a risk or an advisory empty state is; no serif outside a risk item; the limit sentence wherever the claim sentence is; a seeded tag on every seeded figure; the three snapshot facts on every client page.
