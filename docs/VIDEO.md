# Walkthrough video: the script

For the owner to record. About two and a half minutes. It is not recorded or uploaded by the build.

The order is the one `docs/SPEC.md` gives under "Who it is for": a product a company would ship, one real thing to try (type a domain), the human loop (tick a risk handled), and the evidence (the eval table). The finding and its limit are said first and again at the eval table, because the README leads with them (decision 0013).

## Before recording

- Browser window about 1440 wide, light theme, signed out. Open <https://domain-health-rose.vercel.app> once beforehand so the first load is warm.
- Use a private window, so the handled ticks start empty. A visitor's ticks go to a sandbox of their own and expire after a day; nothing you click changes what anyone else sees.
- A terminal in the repository folder, with `make setup` already run. The only command used is free.
- Pick the client before you start: open the list and choose one whose row shows risks today. Copperkettle Kitchen (`/clients/copperkettle-kitchen`) has a risk on both of its days. The clients change from day to day on a short cycle, so check on the day you record.
- Say nothing the page or the README does not say. No real company, person or platform is named: the story is "a client's internal platform".

## The script

### 1. What it is, and the finding (0:00 to 0:25)

**Show:** <https://domain-health-rose.vercel.app>, the client list. The claim and its limit are on this screen.

**Say:**

> This is a daily health check for the email sending domains of many clients. It is a public rebuild, on synthetic data, of a monitor I built for a client's internal platform.
>
> The finding first. I built the eval before I wrote the prompt. It showed that a table of rules beats the model on this task. So the product ships that way: rules drive the action list, and the model's risks are shown beside it as advisory.

### 2. The product (0:25 to 0:50)

**Show:** click the client you picked, for example <https://domain-health-rose.vercel.app/clients/copperkettle-kitchen>. Scroll slowly: the fixes first, then the advisory panel, then the labels that say which figures are seeded.

**Say:**

> Twelve invented clients, each checked once a day by a scheduled job. Every day leaves one snapshot per client.
>
> At the top are the fixes. These come from rules: a fault with one correct action. Beside them are the risks a model picked from a closed list. Each one is marked "Advisory, unproven", and none is ever ranked above a rules finding.
>
> The clients, their figures and their DNS answers are seeded, and the page labels them. The model's output here was recorded from real model runs and is replayed. There is no model key in production.

### 3. One real thing: type a domain (0:50 to 1:15)

**Show:** go to <https://domain-health-rose.vercel.app/check>. Type `example.com` and press "Check domain". Wait for the result. Point at the SPF, DKIM and DMARC rows and the fix list, then at the line that says why there are no risks.

**Say:**

> This part is real. Type any public domain and it runs live DNS checks for SPF, DKIM and DMARC, and gives the fix list.
>
> There are no risks for a typed domain, because it has no reputation or sending data, and the page says so. The check is rate limited and capped per day, and the service refuses anything that is not a public domain name.

### 4. The human loop: mark a risk handled (1:15 to 1:40)

**Show:** go back to the client page. Press "Mark handled" on one risk. It leaves the visible list. Reload the page: it is still hidden. Then reopen it from the handled list.

**Say:**

> A person marks a risk handled, and it stays hidden for thirty days. The risk's ID is built in code from its type and the domain, never from the model's text, so "handled" still means the same thing tomorrow.
>
> The daily job and this click write the same documents in transactions, so a click made during a run is never lost. As a visitor I am in a sandbox of my own, so I can try this without changing the page for anyone else.

### 5. The evidence: the eval table (1:40 to 2:20)

**Show:** <https://domain-health-rose.vercel.app/evals>. Stay on the table: the model's row, the rules-only row, the missed bar. Then the row for the version not in use.

**Say:**

> Here is the evidence. Forty-eight labelled cases, three live runs each, scored in code against four bars that were fixed before any prompt existed.
>
> The model's list missed a bar. The harmful bar is zero, and the prompt in use returned nine wrong risks in 144 case-runs. I made five attempts on four prompt versions and two models, and none met all four bars. The final attempt did worse, and why is not established.
>
> The limit, in plain words: on this project's evals a table of rules does better on the risk list than the model. The table meets all four bars and no prompt version did. On the thirty table cases that is by construction, because their labels are the table's own output. On the eighteen open cases the model found one more expected risk than the table in each run, and returned three wrong ones where the table returned none.
>
> The labels were drafted by AI against a written rubric and reviewed by me, the engineer who built the original system. They were not reviewed by a deliverability specialist.

### 6. Check it yourself (2:20 to 2:40)

**Show:** the terminal. Run:

```bash
make eval STRICT=1; echo "exit $?"
```

Let the lines print: `harmful    9 in 144 case-runs           bar == 0     missed`, then the non-zero exit. Then show `README.md` scrolled to "4. Evals".

**Say:**

> Anyone can check this for free. This command scores the committed recordings and exits non-zero, because the bar is missed. The README's table is generated from the same results file, and a test fails if they differ.
>
> The README says what was tried to show the model's judgment, why it fell short, and how this was built.

## If there is time, or as a second take

- **The fallback.** <https://domain-health-rose.vercel.app/?demo=fallback> shows what a visitor sees if the backend cannot be reached: the bundled snapshots, with a notice that this is saved data.
- **The client report** (Phase 6). On the client page, open the report: `/clients/copperkettle-kitchen/report` for HTML and `/clients/copperkettle-kitchen/report.md` for Markdown. Show its four sections: authentication, reputation, sending, actions. Record this only after Phase 6 is merged and you have seen both addresses load on the hosted demo.
- **Phone width and the dark theme.** Narrow the window to about 390 wide and switch the theme, on the client page.

## Do not say

- That the model beats rules, or that the evals show judgment. They do not.
- "Zero harmful", or any number that is not in `evals/results.json`.
- That the hosted demo calls a model. It replays recordings.
- The real client, its platform or its people.
