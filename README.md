# SEO Playbook Skills

Three skills used by the [SEO Audit Report Builder playbook](https://seo-audit-site.vercel.app/skill-pack). Each includes its Python helper and any reference files it needs.

| Skill | Purpose |
| --- | --- |
| [edit-conversion-safe-blogs](skills/edit-conversion-safe-blogs) | Edit commercial blog drafts while preserving CTAs, product links, offers, positioning, and proof. Includes a conversion snapshot and verification script. |
| [trend-scan](skills/trend-scan) | Read exported search-performance CSVs to identify traffic direction, declining pages or queries, and concentration risk. |
| [claim-check](skills/claim-check) | Flag potentially stale claims and missing verification dates. The agent checks primary sources; the script does not establish whether a claim is true. |

## Install

Requires Node.js/npm for the installer and Python 3.10+ for the helpers. The Python scripts use only the standard library: no pip dependencies or API keys. Web access is needed when the agent verifies claims against live sources.

Install all three in the current project:

```bash
npx skills add BigChrisCooke/seo-playbook-skills
```

The installer lets you select skills and your agent. For an explicit, non-interactive installation:

```bash
npx skills add BigChrisCooke/seo-playbook-skills --skill edit-conversion-safe-blogs trend-scan claim-check --agent claude-code --yes
```

Replace `claude-code` with `codex` or `cursor` for those agents. Add `--global` to install for all projects. Restart your agent session after installation if the skills are not yet visible.

Install one skill:

```bash
npx skills add BigChrisCooke/seo-playbook-skills --skill edit-conversion-safe-blogs
npx skills add BigChrisCooke/seo-playbook-skills --skill trend-scan
npx skills add BigChrisCooke/seo-playbook-skills --skill claim-check
```

Browse the collection on [skills.sh](https://skills.sh/BigChrisCooke/seo-playbook-skills). Listings are indexed from CLI installation telemetry; publication on GitHub does not guarantee immediate directory visibility.

### Manual installation

Clone this repository and copy the **whole skill directory**, including `scripts/`, `references/`, and `agents/` where present, into your agent's skills directory. For Claude Code, this is `.claude/skills/` in a project or `~/.claude/skills/` for all projects. Copying only `SKILL.md` leaves the helper files behind.

## Use

Ask your agent to use the skill by name. For example:

- “Use edit-conversion-safe-blogs on this draft. Preserve the trial CTA and product links.”
- “Use trend-scan on these Search Console exports before writing the audit.”
- “Use claim-check on this report, verify flagged claims, and date each check.”

The blog editor includes a prose rubric and final evaluation, so it works without the optional `no-ai-slop` skill. During an audit, edit copies under the audit-data folder and treat proposed edits as evidence until the user authorizes publication.

Run the helpers directly from the repository root:

```bash
python skills/trend-scan/scripts/trend_scan.py --series Dates.csv
python skills/claim-check/scripts/claim_check.py report.md
python skills/edit-conversion-safe-blogs/scripts/conversion_guard.py --help
```

`trend-scan` and `claim-check` return exit code **1 when they find issues**, **0 when no issues are flagged**, and **2 for invalid input or usage**. An issue flag is not a script crash. See each skill's instructions for inputs, limitations, and interpretation.

## License

[MIT](LICENSE), copyright 2026 Chris Cooke. These three skills are published here with their supporting files; this repository does not redistribute the third-party analysis skills used elsewhere in the playbook.
