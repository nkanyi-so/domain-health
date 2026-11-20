# Screens

Written by `make screens`. Do not edit by hand: run the command again.

68 screenshots: the 17 states in `docs/DESIGN.md`, each in the light and the dark theme, at 1440 and at 390 wide, full page.

States 1 to 15 and 17 are drawn from the `?demo=` address in the design document's table, so they are the same on any day. State 16 is real: the script signs in on the local servers with the development passphrase, marks one of Oakhaven Outfitters' risks handled and opens that client's page, so its snapshot day and its handled dates are the day the command was run.

## The three checks

Computed in the browser on every one of the screenshots, and on the eval table and "About this demo" in the same two themes and two widths (8 more pages, no screenshot kept): 76 pages in all. The command exits non-zero if any fails.

| Check | Result |
|---|---|
| Contrast: every visible piece of text against the ground it sits on, at least 4.5:1 | 0 below, of 4670 pieces of text measured; the lowest is 4.99:1 |
| No sideways scroll: the page is no wider than the window and no element's right edge is beyond it | 0 of 76 pages scroll sideways (38 are 390 wide) |
| Focus: every link, button and field, reached with the Tab key, shows an outline it does not have at rest | 0 without, of 1004 controls focused |
| Each page shows its own wording and tab title, in the theme asked for | 0 of 76 do not |

## The screenshots

| File | State | Address | Text measured | Lowest contrast | Below 4.5 | Sideways scroll | Controls | Without focus style |
|---|---|---|---|---|---|---|---|---|
| [01-loading-light-1440.png](01-loading-light-1440.png) | 1 | `/?demo=loading` | 30 | 5.43 | 0 | no | 12 | 0 |
| [01-loading-light-390.png](01-loading-light-390.png) | 1 | `/?demo=loading` | 28 | 5.43 | 0 | no | 12 | 0 |
| [01-loading-dark-1440.png](01-loading-dark-1440.png) | 1 | `/?demo=loading` | 30 | 6.09 | 0 | no | 12 | 0 |
| [01-loading-dark-390.png](01-loading-dark-390.png) | 1 | `/?demo=loading` | 28 | 6.09 | 0 | no | 12 | 0 |
| [02-healthy-light-1440.png](02-healthy-light-1440.png) | 2 | `/clients/harbourlight-books?demo=healthy` | 77 | 4.99 | 0 | no | 12 | 0 |
| [02-healthy-light-390.png](02-healthy-light-390.png) | 2 | `/clients/harbourlight-books?demo=healthy` | 72 | 4.99 | 0 | no | 12 | 0 |
| [02-healthy-dark-1440.png](02-healthy-dark-1440.png) | 2 | `/clients/harbourlight-books?demo=healthy` | 77 | 6.86 | 0 | no | 12 | 0 |
| [02-healthy-dark-390.png](02-healthy-dark-390.png) | 2 | `/clients/harbourlight-books?demo=healthy` | 72 | 6.86 | 0 | no | 12 | 0 |
| [03-fixes-only-light-1440.png](03-fixes-only-light-1440.png) | 3 | `/clients/fernhollow-garden?demo=fixes-only` | 78 | 4.99 | 0 | no | 12 | 0 |
| [03-fixes-only-light-390.png](03-fixes-only-light-390.png) | 3 | `/clients/fernhollow-garden?demo=fixes-only` | 73 | 4.99 | 0 | no | 12 | 0 |
| [03-fixes-only-dark-1440.png](03-fixes-only-dark-1440.png) | 3 | `/clients/fernhollow-garden?demo=fixes-only` | 78 | 6.09 | 0 | no | 12 | 0 |
| [03-fixes-only-dark-390.png](03-fixes-only-dark-390.png) | 3 | `/clients/fernhollow-garden?demo=fixes-only` | 73 | 6.09 | 0 | no | 12 | 0 |
| [04-risks-only-light-1440.png](04-risks-only-light-1440.png) | 4 | `/clients/oakhaven-outfitters?demo=risks-only` | 82 | 4.99 | 0 | no | 14 | 0 |
| [04-risks-only-light-390.png](04-risks-only-light-390.png) | 4 | `/clients/oakhaven-outfitters?demo=risks-only` | 77 | 4.99 | 0 | no | 14 | 0 |
| [04-risks-only-dark-1440.png](04-risks-only-dark-1440.png) | 4 | `/clients/oakhaven-outfitters?demo=risks-only` | 82 | 6.86 | 0 | no | 14 | 0 |
| [04-risks-only-dark-390.png](04-risks-only-dark-390.png) | 4 | `/clients/oakhaven-outfitters?demo=risks-only` | 77 | 6.86 | 0 | no | 14 | 0 |
| [05-both-light-1440.png](05-both-light-1440.png) | 5 | `/clients/northwind-cycles?demo=both` | 86 | 5.43 | 0 | no | 14 | 0 |
| [05-both-light-390.png](05-both-light-390.png) | 5 | `/clients/northwind-cycles?demo=both` | 81 | 5.43 | 0 | no | 14 | 0 |
| [05-both-dark-1440.png](05-both-dark-1440.png) | 5 | `/clients/northwind-cycles?demo=both` | 86 | 6.09 | 0 | no | 14 | 0 |
| [05-both-dark-390.png](05-both-dark-390.png) | 5 | `/clients/northwind-cycles?demo=both` | 81 | 6.09 | 0 | no | 14 | 0 |
| [06-handled-one-light-1440.png](06-handled-one-light-1440.png) | 6 | `/clients/oakhaven-outfitters?demo=handled-one` | 100 | 4.99 | 0 | no | 18 | 0 |
| [06-handled-one-light-390.png](06-handled-one-light-390.png) | 6 | `/clients/oakhaven-outfitters?demo=handled-one` | 95 | 4.99 | 0 | no | 18 | 0 |
| [06-handled-one-dark-1440.png](06-handled-one-dark-1440.png) | 6 | `/clients/oakhaven-outfitters?demo=handled-one` | 100 | 6.86 | 0 | no | 18 | 0 |
| [06-handled-one-dark-390.png](06-handled-one-dark-390.png) | 6 | `/clients/oakhaven-outfitters?demo=handled-one` | 95 | 6.86 | 0 | no | 18 | 0 |
| [07-all-handled-light-1440.png](07-all-handled-light-1440.png) | 7 | `/clients/oakhaven-outfitters?demo=all-handled` | 83 | 4.99 | 0 | no | 14 | 0 |
| [07-all-handled-light-390.png](07-all-handled-light-390.png) | 7 | `/clients/oakhaven-outfitters?demo=all-handled` | 78 | 4.99 | 0 | no | 14 | 0 |
| [07-all-handled-dark-1440.png](07-all-handled-dark-1440.png) | 7 | `/clients/oakhaven-outfitters?demo=all-handled` | 83 | 6.86 | 0 | no | 14 | 0 |
| [07-all-handled-dark-390.png](07-all-handled-dark-390.png) | 7 | `/clients/oakhaven-outfitters?demo=all-handled` | 78 | 6.86 | 0 | no | 14 | 0 |
| [08-risks-unavailable-light-1440.png](08-risks-unavailable-light-1440.png) | 8 | `/clients/northwind-cycles?demo=risks-unavailable` | 80 | 5.43 | 0 | no | 12 | 0 |
| [08-risks-unavailable-light-390.png](08-risks-unavailable-light-390.png) | 8 | `/clients/northwind-cycles?demo=risks-unavailable` | 75 | 5.43 | 0 | no | 12 | 0 |
| [08-risks-unavailable-dark-1440.png](08-risks-unavailable-dark-1440.png) | 8 | `/clients/northwind-cycles?demo=risks-unavailable` | 80 | 6.09 | 0 | no | 12 | 0 |
| [08-risks-unavailable-dark-390.png](08-risks-unavailable-dark-390.png) | 8 | `/clients/northwind-cycles?demo=risks-unavailable` | 75 | 6.09 | 0 | no | 12 | 0 |
| [09-no-snapshot-light-1440.png](09-no-snapshot-light-1440.png) | 9 | `/clients/driftwood-coffee?demo=no-snapshot` | 85 | 4.99 | 0 | no | 13 | 0 |
| [09-no-snapshot-light-390.png](09-no-snapshot-light-390.png) | 9 | `/clients/driftwood-coffee?demo=no-snapshot` | 80 | 4.99 | 0 | no | 13 | 0 |
| [09-no-snapshot-dark-1440.png](09-no-snapshot-dark-1440.png) | 9 | `/clients/driftwood-coffee?demo=no-snapshot` | 85 | 6.09 | 0 | no | 13 | 0 |
| [09-no-snapshot-dark-390.png](09-no-snapshot-dark-390.png) | 9 | `/clients/driftwood-coffee?demo=no-snapshot` | 80 | 6.09 | 0 | no | 13 | 0 |
| [10-check-running-light-1440.png](10-check-running-light-1440.png) | 10 | `/check?domain=example.com&demo=running` | 30 | 5.43 | 0 | no | 11 | 0 |
| [10-check-running-light-390.png](10-check-running-light-390.png) | 10 | `/check?domain=example.com&demo=running` | 28 | 5.43 | 0 | no | 11 | 0 |
| [10-check-running-dark-1440.png](10-check-running-dark-1440.png) | 10 | `/check?domain=example.com&demo=running` | 30 | 6.09 | 0 | no | 11 | 0 |
| [10-check-running-dark-390.png](10-check-running-dark-390.png) | 10 | `/check?domain=example.com&demo=running` | 28 | 6.09 | 0 | no | 11 | 0 |
| [11-check-result-light-1440.png](11-check-result-light-1440.png) | 11 | `/check?domain=example.com&demo=result` | 53 | 4.99 | 0 | no | 12 | 0 |
| [11-check-result-light-390.png](11-check-result-light-390.png) | 11 | `/check?domain=example.com&demo=result` | 48 | 4.99 | 0 | no | 12 | 0 |
| [11-check-result-dark-1440.png](11-check-result-dark-1440.png) | 11 | `/check?domain=example.com&demo=result` | 53 | 6.09 | 0 | no | 12 | 0 |
| [11-check-result-dark-390.png](11-check-result-dark-390.png) | 11 | `/check?domain=example.com&demo=result` | 48 | 6.09 | 0 | no | 12 | 0 |
| [12-check-refused-light-1440.png](12-check-refused-light-1440.png) | 12 | `/check?domain=192.0.2.1&demo=refused` | 24 | 5.43 | 0 | no | 11 | 0 |
| [12-check-refused-light-390.png](12-check-refused-light-390.png) | 12 | `/check?domain=192.0.2.1&demo=refused` | 22 | 5.43 | 0 | no | 11 | 0 |
| [12-check-refused-dark-1440.png](12-check-refused-dark-1440.png) | 12 | `/check?domain=192.0.2.1&demo=refused` | 24 | 6.86 | 0 | no | 11 | 0 |
| [12-check-refused-dark-390.png](12-check-refused-dark-390.png) | 12 | `/check?domain=192.0.2.1&demo=refused` | 22 | 6.86 | 0 | no | 11 | 0 |
| [13-rate-limited-light-1440.png](13-rate-limited-light-1440.png) | 13 | `/check?domain=example.com&demo=rate-limited` | 24 | 5.43 | 0 | no | 12 | 0 |
| [13-rate-limited-light-390.png](13-rate-limited-light-390.png) | 13 | `/check?domain=example.com&demo=rate-limited` | 22 | 5.43 | 0 | no | 12 | 0 |
| [13-rate-limited-dark-1440.png](13-rate-limited-dark-1440.png) | 13 | `/check?domain=example.com&demo=rate-limited` | 24 | 6.50 | 0 | no | 12 | 0 |
| [13-rate-limited-dark-390.png](13-rate-limited-dark-390.png) | 13 | `/check?domain=example.com&demo=rate-limited` | 22 | 6.50 | 0 | no | 12 | 0 |
| [14-cap-reached-light-1440.png](14-cap-reached-light-1440.png) | 14 | `/check?domain=example.com&demo=cap-reached` | 24 | 5.43 | 0 | no | 12 | 0 |
| [14-cap-reached-light-390.png](14-cap-reached-light-390.png) | 14 | `/check?domain=example.com&demo=cap-reached` | 22 | 5.43 | 0 | no | 12 | 0 |
| [14-cap-reached-dark-1440.png](14-cap-reached-dark-1440.png) | 14 | `/check?domain=example.com&demo=cap-reached` | 24 | 6.50 | 0 | no | 12 | 0 |
| [14-cap-reached-dark-390.png](14-cap-reached-dark-390.png) | 14 | `/check?domain=example.com&demo=cap-reached` | 22 | 6.50 | 0 | no | 12 | 0 |
| [15-fallback-light-1440.png](15-fallback-light-1440.png) | 15 | `/?demo=fallback` | 96 | 5.43 | 0 | no | 24 | 0 |
| [15-fallback-light-390.png](15-fallback-light-390.png) | 15 | `/?demo=fallback` | 102 | 5.43 | 0 | no | 24 | 0 |
| [15-fallback-dark-1440.png](15-fallback-dark-1440.png) | 15 | `/?demo=fallback` | 96 | 6.09 | 0 | no | 24 | 0 |
| [15-fallback-dark-390.png](15-fallback-dark-390.png) | 15 | `/?demo=fallback` | 102 | 6.09 | 0 | no | 24 | 0 |
| [16-admin-signed-in-light-1440.png](16-admin-signed-in-light-1440.png) | 16 | `/clients/oakhaven-outfitters`, signed in | 90 | 4.99 | 0 | no | 17 | 0 |
| [16-admin-signed-in-light-390.png](16-admin-signed-in-light-390.png) | 16 | `/clients/oakhaven-outfitters`, signed in | 85 | 4.99 | 0 | no | 17 | 0 |
| [16-admin-signed-in-dark-1440.png](16-admin-signed-in-dark-1440.png) | 16 | `/clients/oakhaven-outfitters`, signed in | 90 | 6.50 | 0 | no | 17 | 0 |
| [16-admin-signed-in-dark-390.png](16-admin-signed-in-dark-390.png) | 16 | `/clients/oakhaven-outfitters`, signed in | 85 | 6.50 | 0 | no | 17 | 0 |
| [17-sign-in-refused-light-1440.png](17-sign-in-refused-light-1440.png) | 17 | `/admin?demo=refused` | 21 | 5.43 | 0 | no | 11 | 0 |
| [17-sign-in-refused-light-390.png](17-sign-in-refused-light-390.png) | 17 | `/admin?demo=refused` | 19 | 5.43 | 0 | no | 11 | 0 |
| [17-sign-in-refused-dark-1440.png](17-sign-in-refused-dark-1440.png) | 17 | `/admin?demo=refused` | 21 | 6.86 | 0 | no | 11 | 0 |
| [17-sign-in-refused-dark-390.png](17-sign-in-refused-dark-390.png) | 17 | `/admin?demo=refused` | 19 | 6.86 | 0 | no | 11 | 0 |

## Also checked, without a screenshot

| Page | Address | Text measured | Lowest contrast | Below 4.5 | Sideways scroll | Controls | Without focus style |
|---|---|---|---|---|---|---|---|
| evals (light, 1440) | `/evals` | 94 | 5.43 | 0 | no | 9 | 0 |
| evals (light, 390) | `/evals` | 113 | 5.43 | 0 | no | 9 | 0 |
| evals (dark, 1440) | `/evals` | 94 | 6.86 | 0 | no | 9 | 0 |
| evals (dark, 390) | `/evals` | 113 | 6.09 | 0 | no | 9 | 0 |
| about (light, 1440) | `/about` | 30 | 5.43 | 0 | no | 11 | 0 |
| about (light, 390) | `/about` | 28 | 5.43 | 0 | no | 11 | 0 |
| about (dark, 1440) | `/about` | 30 | 6.86 | 0 | no | 11 | 0 |
| about (dark, 390) | `/about` | 28 | 6.86 | 0 | no | 11 | 0 |
