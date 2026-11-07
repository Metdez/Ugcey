# Research & integrations

Before any research-backed recommendation or feature build, use Firecrawl. Gather current, permitted primary sources first; then inspect relevant public GitHub repositories and product examples.

## Research standard

1. Define the question and success criteria.
2. Use Firecrawl to collect sources, documentation, examples, and constraints.
3. Record URLs, dates, key claims, licensing, and unresolved assumptions.
4. Convert findings into original, explainable recommendations—not copied scripts or creative work.
5. Re-check freshness before shipping a claim or integration that may have changed.

## Integration guardrails

- Use documented APIs and authorized connections for Glasshand, Higgsfield, Cloudflare, and social platforms.
- Store secrets only in approved secret-management systems; never in source, prompts, or logs.

## Agent tools

- Firecrawl (`backend/ugecy/tools/firecrawl.py`): `firecrawl_search`, `firecrawl_scrape`, and `firecrawl_map`, wired into the research agent by `backend/ugecy/agent.py`. The key comes from the `FIRECRAWL_API` environment variable. Each call is logged to the `ugecy.audit` logger; scraped pages carry their source URL and retrieval time.


For UI research, also use Mobbin MCP; see [interface.md](interface.md). For build rules, see [engineering-rules.md](engineering-rules.md).

