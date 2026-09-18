# What the comparison means

Reviewed on 2026-09-18 against upstream commit `5b2c0007766c6a1cf1d53fd8fc73e979e0821022`.

Our starting point was a locally installed ai-seo v1.2.0 with its problematic
citation example corrected. This release rewrites the workflow and reference
files to make evidence capture, source verification, and uncertainty explicit.
It is not a complete fork of every feature in the current upstream package.

| Reviewed upstream behavior | This adaptation |
| --- | --- |
| [Content patterns](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/ai-seo/references/content-patterns.md) include a worked example naming a Google 2024 Core Web Vitals report without a source URL supporting its numbers. | Unverified examples become clearly marked templates. Every consequential claim requires an opened primary source and a recorded date. |
| [AI-SEO entrypoint](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/ai-seo/SKILL.md) includes broad visibility-lift percentages and platform prescriptions. | Uses measured sample outcomes; research findings require their actual scope and cannot become promised lifts. |
| The same entrypoint's crawler checklist groups training and search controls together, including Google-Extended alongside AI Overviews. | Checks operator documentation and distinguishes training, search indexing, and user-triggered retrieval before proposing changes. |

This is a comparison of concrete content and safeguards. It does not establish
higher rankings, citation rates, or conversion performance in a controlled
head-to-head test. Upstream can change after this snapshot. Recheck before
repeating the comparison as a current claim; no affiliation or endorsement is
implied.

See [platform sources](platform-verification.md) and [evidence patterns](content-patterns.md).
The bundled Python scanner finds candidates for checking; it does not verify
sources or determine truth on its own.

Original workflow: Corey Haines, MIT. Corrections, rewritten workflow, and
claim scanner: Chris Cooke. The [license](../LICENSE) retains both notices.
