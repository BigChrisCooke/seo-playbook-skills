# Eligibility checks

Primary sources opened on 2026-09-18. Reopen them during an audit; dates and
feature support can change.

| Decision | Evidence |
| --- | --- |
| Which Google features are currently supported? | [Search gallery](https://developers.google.com/search/docs/appearance/structured-data/search-gallery). Follow the page for the selected feature and its exact required/recommended fields. |
| Does correct markup guarantee a result? | [Structured data guidelines](https://developers.google.com/search/docs/appearance/structured-data/sd-policies). Eligibility and display are separate. |
| Can FAQPage produce FAQ rich results? | [May 2026 documentation updates](https://developers.google.com/search/updates#may-2026): FAQ results stopped from May 7, 2026. The old FAQ documentation now redirects to the update log. |
| Can HowTo produce rich results? | [HowTo and FAQ changes](https://developers.google.com/search/blog/2023/08/howto-faq-changes), including the September 2023 update: HowTo rich results are deprecated. |
| Does SearchAction create a Google sitelinks search box? | [Sitelinks search-box retirement](https://developers.google.com/search/blog/2024/10/sitelinks-search-box): removed from November 21, 2024. |
| Is WebSite markup still useful? | [Site names](https://developers.google.com/search/docs/appearance/site-names): site-name guidance is separate from the retired search box. |
| Is QAPage appropriate? | [QAPage documentation](https://developers.google.com/search/docs/appearance/structured-data/qapage): check the conditions for questions with user-submitted answers; do not substitute it for an ordinary FAQ. |

Record what you checked, not just a link. Use a table with page URL, proposed
type, intended feature, observed facts, eligibility decision, official source,
checked date, validation result, and remaining uncertainty.

For a semantic-only request, schema.org vocabulary validity may be the relevant
goal. State it clearly and do not discard useful existing markup merely because
Google retired a particular presentation feature.
