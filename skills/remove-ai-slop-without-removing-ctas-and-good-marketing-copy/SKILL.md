---
name: remove-ai-slop-without-removing-ctas-and-good-marketing-copy
description: Remove AI slop and humanize AI-written marketing copy without removing CTAs or weakening persuasive sales copy. Edit SEO blogs, SaaS content, product-led articles, and commercial drafts to remove robotic language, filler, buzzwords, repetition, and generic AI phrasing while preserving brand voice, calls to action, conversion copy, product links, offers, positioning, proof points, and capability claims. Use for AI content editing, AI-slop removal, blog editing, copy polishing, and conversion-safe rewrites; includes a Python conversion guard to verify protected content and links. Does not bypass AI detectors or rewrite marketing strategy.
---

# Remove AI slop without removing CTAs and good marketing copy

Improve the prose while preserving the article's commercial job. Treat prose
quality and conversion integrity as two separate gates.

## Non-negotiable rule

Do not delete, merge, move, shorten, neutralise, or hide a CTA, product link,
offer, positioning statement, proof point, or capability claim without explicit
user approval. Repetition near a CTA may be deliberate funnel reinforcement,
not accidental redundancy.

This is a line-editing skill. Do not silently turn it into a content-strategy
rewrite.

## Locate the helper files

Resolve `scripts/` and `references/` relative to the directory containing this
`SKILL.md`, not the project working directory. Use an absolute script path when
running from another folder, and keep input/output paths relative to the user
project or make them absolute. On Windows, use `python` if `python3` is unavailable.

## Workflow

### 1. Read and define the conversion contract

Read the full draft before editing. Identify:

- Audience and publication context
- Primary job of the article
- Intended reader action
- Offer or product being advanced
- CTA heading, copy, placement, and destination URLs
- Positioning, proof, differentiators, and capability claims
- Three to five voice signals worth preserving

If the primary job or intended action is unclear, ask one question before
editing. Keep the contract internal unless the user asks to see it.

### 2. Mark protected blocks

In file-backed Markdown, wrap each conversion-critical section before taking a
snapshot:

```markdown
<!-- conversion-safe:start id="primary-cta" -->
## CTA heading
...
<!-- conversion-safe:end -->
```

Use stable, unique IDs such as `primary-cta`, `product-proof`, or
`comparison-offer`. The comments do not render in HTML.

For pasted text that will not be written to a file, keep an exact internal copy
of each protected block instead.

### 3. Snapshot the draft

For file-backed Markdown, run:

```bash
python scripts/conversion_guard.py snapshot <draft.md> --output <contract.json>
```

Store the contract in a temporary task directory, not beside the published
article. The snapshot records the H2 outline, link targets, and protected block
headings, links, list counts, and word volume.

### 4. Edit the prose

If the `no-ai-slop` skill is installed, read its `SKILL.md` and `eval.md`
completely and apply them. Otherwise, read
[`references/prose-rubric.md`](references/prose-rubric.md).

Make the minimum effective edit. Preserve specific facts, useful edge, humour,
cadence, and intentional repetition. Do not invent claims, proof, statistics,
features, or opinions.

Inside a protected block:

- Fix spelling, grammar, clarity, and genuine AI-slop patterns.
- Preserve its heading, placement, URL targets, offer, capability count,
  positioning strength, voice, and approximate length.
- Keep the final action obvious.

Ask before any structural or strategic change.

### 5. Verify conversion integrity

Run:

```bash
python scripts/conversion_guard.py verify <edited.md> --contract <contract.json>
```

If verification fails, restore the missing or weakened contract element and run
the check again. Use `--allow-structure-change`, `--allow-link-removal`, or a
lower word-ratio threshold only after the user explicitly approves that exact
change.

For pasted text, compare the original and edited versions manually using the
same checks.

### 6. Run the final evaluation

Read and answer every check in
[`references/final-eval.md`](references/final-eval.md). Fix every failure
before returning the edit.

## Output

Return:

1. The full edited draft or a direct link to the edited file.
2. A short **What changed** section.
3. A short **Conversion integrity** line confirming the protected CTA, links,
   offer, positioning, and capability claims remain.

Call out every user-approved structural or strategic change explicitly.
