# Entity graph example

This fictional graph illustrates connected entity IDs. Replace every example
value with verified page facts. It is not a complete rich-result eligibility
template and does not promise a particular search appearance.

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://example.com/#organization",
      "name": "Example Company",
      "url": "https://example.com/"
    },
    {
      "@type": "WebSite",
      "@id": "https://example.com/#website",
      "name": "Example Company",
      "url": "https://example.com/",
      "publisher": { "@id": "https://example.com/#organization" }
    },
    {
      "@type": "WebPage",
      "@id": "https://example.com/about#webpage",
      "url": "https://example.com/about",
      "name": "About Example Company",
      "isPartOf": { "@id": "https://example.com/#website" },
      "about": { "@id": "https://example.com/#organization" }
    }
  ]
}
```

For Article, Product, merchant listings, SoftwareApplication, LocalBusiness,
Event, or BreadcrumbList, follow the current feature-specific source linked
from the Google search gallery. Populate only supported real information.
