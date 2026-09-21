# Search criteria

Sourcing criteria for the job-search skill. Read on every sweep.
Roles and titles live in profile/targets.md. This file says WHERE and HOW to
look, not WHAT to look for. When the two disagree, targets.md wins.

## Scope

geography: London UK, United Kingdom, Ireland, European Union
remote_scope: remote, hybrid, onsite
# Onsite is included because logistics.md accepts fully onsite in London.
onsite_requires_city: London
exclude_locations: United States, Canada, India, Singapore, Australia

## Companies

company_stage: seed, series-a, series-b, growth, public
company_size:
industries_prefer: AI infrastructure, developer tools, agents, fintech
industries_avoid: gambling

## Sources

sources: ashby, greenhouse, linkedin, ai-boards, career-pages
sources_disabled:
known_company_boards: ashby:babbage, ashby:lovelace, ashby:turinglabs,
  greenhouse:hopper, greenhouse:noether

## Query terms

query_terms_fde: Forward Deployed Engineer, Deployed Engineer, Solutions
  Engineer, Applied AI Engineer, Solutions Architect, Member of Technical Staff
query_terms_leadership: VP of Engineering, CTO, Head of Engineering,
  Director of Engineering
query_terms_exclude: intern, graduate, apprentice, placement

## Exclusions

company_cooldown: Turing Labs until 2026-12-01
companies_never:

## Pacing

max_new_rows_per_run: 60
max_pages_per_query: 3
