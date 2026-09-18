# Platform verification

Sources opened 2026-09-18. Recheck before changing crawler policies or claiming
that a requirement or platform behavior is current.

- [Google AI features](https://developers.google.com/search/docs/appearance/ai-features) and [Google's optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide): ordinary Search eligibility and useful content remain relevant; special AI schema or files are not required. Do not promise Google visibility from llms.txt or formatting alone.
- [Google crawler documentation](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers): distinguish Googlebot's Search role from Google-Extended's controls. Do not present Google-Extended as the switch for AI Overviews inclusion.
- [OpenAI crawler documentation](https://developers.openai.com/api/docs/bots): distinguish OAI-SearchBot, GPTBot, and ChatGPT-User. Their purposes and treatment differ; a training opt-out is not automatically a search opt-out.
- [Perplexity crawler documentation](https://docs.perplexity.ai/docs/resources/perplexity-crawlers): distinguish the search crawler from user-initiated fetching and check the published verification information.

For Claude, Gemini outside Google Search, Copilot, or another surface, inspect
the operator's current documentation and the actual product mode. Record the
source and date; do not assume that a historical search partner or one product
surface describes every current mode.

Observed citation patterns are sample evidence, not known ranking weights.
Separate verified product behavior from correlations, hypotheses, and vendor
marketing claims. Paid monitoring tools can help collect a panel, but do not
make its sample representative of the whole market.
