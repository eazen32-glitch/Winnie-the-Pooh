# Third-party notices and source information

This inventory is based on the files at repository commit `04310007d07189cbcaae90c348250778b4331bbf`. It identifies visible references; it is not a complete provenance certification. The root Apache license applies to the project's original source code and documentation, not to third-party materials under separate terms.

## Frontend resources loaded externally

The HTML pages reference the following resources through CDNs or Google Fonts. These resource files are not bundled in the inspected checkout. Preserve upstream notices if you later download, bundle, or modify them.

| Resource | Use in this project | Upstream license/source |
| --- | --- | --- |
| Tailwind CSS | Browser CDN styling in `mainpage.html` and `analytics_trends.html`; CDN URL does not pin a version | MIT; Copyright (c) Tailwind Labs, Inc. [Upstream license](https://github.com/tailwindlabs/tailwindcss/blob/main/LICENSE) |
| Chart.js | Charts in `analytics_trends.html`; CDN URL does not pin a version | MIT. [Upstream license and copyright notice](https://github.com/chartjs/Chart.js/blob/master/LICENSE.md) |
| Font Awesome Free 6.7.2 and 6.5.0 | Icon styles and webfonts in the home and analytics pages | CSS/code: MIT; webfonts: SIL OFL 1.1; SVG/JS icon assets: CC BY 4.0. Fonticons, Inc. [6.7.2 terms](https://github.com/FortAwesome/Font-Awesome/blob/6.7.2/LICENSE.txt), [6.5.0 terms](https://github.com/FortAwesome/Font-Awesome/blob/6.5.0/LICENSE.txt) |
| Plus Jakarta Sans | Typography loaded through Google Fonts | SIL OFL 1.1. Copyright 2020 The Plus Jakarta Sans Project Authors. [Upstream license](https://github.com/google/fonts/blob/main/ofl/plusjakartasans/OFL.txt) |

For unpinned resources, use the license and notices accompanying the actual version if you later vendor a copy.

## Data and linked evidence

- **Simplify / Coder Quad new-graduate listings:** the embedded skills-radar snapshot identifies [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) and its [listings JSON](https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json) as sources. No root license file was found when the upstream repository was checked on 25 October 2026; GitHub's repository metadata reported no detected license. Attribution alone does not establish permission to redistribute data. Confirm applicable permissions for the embedded snapshot, or replace it with data that you are permitted to redistribute. The project does not claim that this data is Apache-licensed.
- **Hugging Face Transformers releases:** the snapshot cites the [release feed](https://github.com/huggingface/transformers/releases.atom) and individual release pages. This is a source reference; it does not license the release-page content or imply endorsement.
- **Job-posting evidence:** linked employers and job platforms remain the sources of their postings. Source links and company names are references, not claims of ownership or endorsement.
- **UN Sustainable Development Goals:** the radar links to [United Nations SDG pages](https://sdgs.un.org/goals). Those links do not imply UN endorsement or grant rights to UN branding.

The analytics page contains illustrative values. Calendar and interview entries are sample data, not confirmed real bookings.

## Images, screenshots, and branding: provenance to confirm

The inspected repository does not include source or permission records for these files:

- `Wlogo.png`
- `SDCdarklogo.png`
- `SDClogo.png`
- `SDClogo.jpg`
- `Screenshot Replit.png`
- `Screenshot RunPod.png`

Before submission, the maintainers should record which assets the team created and the source and permission for any third-party assets. Preserve applicable copyright and attribution notices. Do not assume that a filename or the repository's Apache license establishes permission to redistribute an image, logo, screenshot, or character depiction.

## Reused code or templates

No existing license or copyright notices were found in the four inspected HTML files. That does not establish that all code is original. If any code came from a template, starter project, or another repository, retain its applicable license, copyright notices, and required attribution. For reused Apache-licensed files, preserve applicable upstream NOTICE information and identify modifications as required by that license.
