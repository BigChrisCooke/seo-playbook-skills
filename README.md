# SEO Playbook Skills

Five skills for the [SEO Audit Report Builder playbook](https://seo-audit-site.vercel.app/skill-pack): three original helpers and two independently maintained adaptations of Corey Haines's schema and AI-SEO workflows. Each includes the reference files and any Python helpers it needs.

| Skill | Purpose |
| --- | --- |
| [remove-ai-slop-without-removing-ctas-and-good-marketing-copy](skills/remove-ai-slop-without-removing-ctas-and-good-marketing-copy) | Remove AI slop and humanize AI-written SEO blogs, SaaS content, and marketing copy. Preserve CTAs, conversion copy, product links, offers, brand voice, positioning, and proof with a Python conversion guard. |
| [trend-scan](skills/trend-scan) | Analyze Google Search Console CSV exports for organic traffic growth or decline, monthly click trends, ranking losses, declining pages and queries, content decay signals, and traffic concentration risk. |
| [claim-check](skills/claim-check) | Support fact-checking, source verification, content freshness audits, and SEO report QA by flagging outdated statistics, prices, versions, feature claims, and missing verification dates. The agent verifies primary sources; the script does not establish truth. |
| [schema-markup-better-than-corey-haines](skills/schema-markup-better-than-corey-haines) | Schema markup, JSON-LD, structured data audits, and rich-result debugging with dated eligibility checks. Corrects retired FAQPage, HowTo, and sitelinks search-box guidance; separates validation from Google eligibility and actual display. |
| [ai-seo-better-than-corey-haines](skills/ai-seo-better-than-corey-haines) | AI SEO, GEO, AEO, and AI citation audits with verified primary sources, repeatable prompt panels, and a bundled stale-claim scanner. Replaces unverified citation examples and distinguishes search from training crawlers. |

## Why “better than Corey Haines”?

The names refer to specific corrections documented against an upstream snapshot checked on **2026-09-18**. The schema adaptation addresses retired rich-result guidance; the AI-SEO adaptation replaces an unverified citation example and makes evidence handling explicit. Each package includes a dated comparison with links to the reviewed upstream commit and primary sources:

- [Schema comparison and attribution](skills/schema-markup-better-than-corey-haines/references/comparison.md)
- [AI-SEO comparison and attribution](skills/ai-seo-better-than-corey-haines/references/comparison.md)

These are adapted and rewritten workflows, not a claim of universal superiority or a published head-to-head performance benchmark. Corey Haines's original MIT copyright notice is retained. The adaptations are independently maintained by Chris Cooke and imply no endorsement.

## Install

Requires Node.js/npm for the installer and Python 3.10+ for the helpers. The Python scripts use only the standard library: no pip dependencies or API keys. Web access is needed when the agent verifies claims against live sources.

Choose from all five in the current project:

```bash
npx skills add BigChrisCooke/seo-playbook-skills
```

The installer lets you select skills and your agent. For an explicit, non-interactive installation:

```bash
npx skills add BigChrisCooke/seo-playbook-skills --skill remove-ai-slop-without-removing-ctas-and-good-marketing-copy trend-scan claim-check --agent claude-code --yes
```

Install the two corrected alternatives:

```bash
npx skills add BigChrisCooke/seo-playbook-skills --skill schema-markup-better-than-corey-haines ai-seo-better-than-corey-haines
```

These use distinct names and do not overwrite an existing `schema`, `schema-markup`, or `ai-seo` installation. Ask the agent to use the chosen variant explicitly. They replace the corresponding analysis step when selected; there is no need to run both versions of that step.

Replace `claude-code` with `codex` or `cursor` for those agents. Add `--global` to install for all projects. Restart your agent session after installation if the skills are not yet visible.

Install one skill:

```bash
npx skills add BigChrisCooke/seo-playbook-skills --skill remove-ai-slop-without-removing-ctas-and-good-marketing-copy
npx skills add BigChrisCooke/seo-playbook-skills --skill trend-scan
npx skills add BigChrisCooke/seo-playbook-skills --skill claim-check
npx skills add BigChrisCooke/seo-playbook-skills --skill schema-markup-better-than-corey-haines
npx skills add BigChrisCooke/seo-playbook-skills --skill ai-seo-better-than-corey-haines
```

Browse the collection on [skills.sh](https://skills.sh/BigChrisCooke/seo-playbook-skills). Listings are indexed from CLI installation telemetry; publication on GitHub does not guarantee immediate directory visibility.

### Manual installation

Clone this repository and copy the **whole skill directory**, including `scripts/`, `references/`, and `agents/` where present, into your agent's skills directory. For Claude Code, this is `.claude/skills/` in a project or `~/.claude/skills/` for all projects. Copying only `SKILL.md` leaves the helper files behind.

## Use

### Verify a public playbook installation

For playbook release **2026-09-19.1**, download [check-skills.py](tools/check-skills.py) or use the copy in this repository. From the audit project run `python check-skills.py --project . --standalone` (omit `--standalone` when using the playbook's optional orchestrator). The standalone runbook additionally needs upstream `seo-audit`; both routes need upstream `programmatic-seo`, `site-architecture`, and `competitors`.

The read-only checker verifies every file in our five packages against the checked publication, checks upstream entrypoints and referenced resources, and runs our Python helpers with `--help`. It reports paths, hashes, missing files, and changed copies. Exit 0 means files verified; exit 1 means a dependency needs attention. It does not prove that an existing agent session has refreshed registered instructions. Start a fresh session after installing or updating, then confirm the selected skill paths. For an isolated installation, `--skills-dir PATH` checks only that explicitly chosen skills directory.

The old `edit-conversion-safe-blogs` name is now `remove-ai-slop-without-removing-ctas-and-good-marketing-copy`. The runbook no longer requires a private `schema-detector` patch. Optional `seo-sxo` requires its upstream shared script bundle and runtime; copying only its skill folder is insufficient. The checker can detect missing SXO files with `--with-sxo`, but dependency imports and browser execution still need testing before running SXO.

### Run the skills

Ask your agent to use the skill by name. For example:

- “Use remove-ai-slop-without-removing-ctas-and-good-marketing-copy on this draft. Preserve the trial CTA and product links.”
- “Use trend-scan on these Search Console exports before writing the audit.”
- “Use claim-check on this report, verify flagged claims, and date each check.”

The blog editor includes a prose rubric and final evaluation, so it works without the optional `no-ai-slop` skill. During an audit, edit copies under the audit-data folder and treat proposed edits as evidence until the user authorizes publication.

Run the helpers directly from the repository root:

```bash
python skills/trend-scan/scripts/trend_scan.py --series Dates.csv
python skills/claim-check/scripts/claim_check.py report.md
python skills/remove-ai-slop-without-removing-ctas-and-good-marketing-copy/scripts/conversion_guard.py --help
```

`trend-scan` and `claim-check` return exit code **1 when they find issues**, **0 when no issues are flagged**, and **2 for invalid input or usage**. An issue flag is not a script crash. See each skill's instructions for inputs, limitations, and interpretation.

## License

[MIT](LICENSE), copyright 2026 Chris Cooke for original work. The schema and AI-SEO adaptations also retain Corey Haines's original MIT notice in their individual `LICENSE` files. Other third-party analysis skills mentioned in the playbook are not included.

## Renamed blog-editing skill

`edit-conversion-safe-blogs` is now `remove-ai-slop-without-removing-ctas-and-good-marketing-copy`. Install the new name using the command above and update saved prompts that invoke the old name. Existing installations of the old skill are not renamed automatically; after verifying the new installation, remove the old skill if it is no longer needed.
