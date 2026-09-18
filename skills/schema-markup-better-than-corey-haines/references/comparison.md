# What the comparison means

Reviewed on 2026-09-18 against upstream commit `5b2c0007766c6a1cf1d53fd8fc73e979e0821022`.

Our starting point was a locally installed, corrected schema-markup v1.1.0.
This release rewrites its workflow, carries forward the local corrections,
and adds explicit evidence and eligibility requirements. It is not an exact
fork of the latest upstream version.

| Reviewed upstream behavior | This adaptation |
| --- | --- |
| [Schema entrypoint](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/schema/SKILL.md) lists FAQPage and HowTo in the common-types guidance without a retirement warning. | A dated eligibility check separates semantic vocabulary from currently supported Google presentations. |
| [Schema examples](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/schema/references/schema-examples.md) describe a WebSite SearchAction as enabling the sitelinks search box. | Documents retirement of that feature and treats site-name markup separately. |
| [Evaluation file](https://github.com/coreyhaines31/marketingskills/blob/5b2c0007766c6a1cf1d53fd8fc73e979e0821022/skills/schema/evals/evals.json) is the reference for the upstream FAQ task. | New cases require the current eligibility answer, distinguish validation from appearance, and avoid fabricated ratings. |

See [primary sources](eligibility.md) for the factual basis. ?Better than?
refers to these specific corrections and workflow safeguards, not a measured
claim that every output, ranking, or business result is superior. Upstream can
change after this snapshot; reassess the comparison before repeating it as a
current claim. No affiliation or endorsement is implied.

Original workflow: Corey Haines, MIT. Corrections and rewritten workflow:
Chris Cooke. The [license](../LICENSE) retains both notices.
