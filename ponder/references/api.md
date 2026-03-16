# Ponder API Reference

## Table of Contents

- [Setup](#setup)
- [GraphQL Middleware](#graphql-middleware)
- [SQL over HTTP](#sql-over-http)
- [Custom Hono Routes](#custom-hono-routes)
- [replaceBigInts](#replacebigints)
- [Reserved Routes](#reserved-routes)

## Setup

API routes are defined in `src/api/index.ts`. The file must `export default` a Hono app.

```ts
import { Hono } from "hono";
import { db, publicClients } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql, client as sqlClient } from "ponder";

const app = new Hono();

// Add middleware and routes...

export default app;
```

**Key imports:**
- `db` from `ponder:api` - Read-only database access (NOT the same as `context.db` in indexing)
- `publicClients` from `ponder:api` - Viem public clients per chain (e.g., `publicClients.mainnet`)
- `schema` from `ponder:schema` - Table definitions for queries
- `graphql` from `ponder` - GraphQL middleware factory
- `client` from `ponder` - SQL over HTTP middleware factory

## GraphQL Middleware

```ts
import { graphql } from "ponder";

app.use("/graphql", graphql({ db, schema }));
```

This auto-generates a GraphQL API with singular and plural queries for every table.

### Generated Query Fields

For a table named `transfers`:
- `transfers` (plural) - List with filtering, sorting, pagination
- `transfer` (singular) - Single record by primary key

### Filtering

Available filter suffixes for each column:

| Suffix | Description | Example |
|--------|-------------|---------|
| (none) | Exact match | `{ from: "0x..." }` |
| `_gt` | Greater than | `{ amount_gt: "1000" }` |
| `_lt` | Less than | `{ amount_lt: "1000" }` |
| `_gte` | Greater or equal | `{ timestamp_gte: "1700000000" }` |
| `_lte` | Less or equal | `{ timestamp_lte: "1700000000" }` |
| `_in` | In array | `{ from_in: ["0x...", "0x..."] }` |
| `_not_in` | Not in array | `{ from_not_in: ["0x..."] }` |
| `_contains` | String contains | `{ name_contains: "token" }` |
| `_starts_with` | String starts with | `{ name_starts_with: "USD" }` |
| `_ends_with` | String ends with | `{ name_ends_with: "coin" }` |
| `_has` | Array contains | `{ tags_has: "defi" }` |

Combine with `AND` / `OR`:

```graphql
{
  transfers(
    where: {
      AND: [
        { amount_gt: "1000000" },
        { OR: [{ from: "0x..." }, { to: "0x..." }] }
      ]
    }
  ) {
    items { id from to amount }
  }
}
```

### Sorting

```graphql
{
  transfers(orderBy: "timestamp", orderDirection: "desc") {
    items { id from to amount timestamp }
  }
}
```

### Cursor Pagination

```graphql
{
  transfers(limit: 10, after: "cursor_string") {
    items { id from to amount }
    pageInfo {
      startCursor
      endCursor
      hasNextPage
      hasPreviousPage
    }
    totalCount
  }
}
```

### Offset Pagination

```graphql
{
  transfers(limit: 10, offset: 20) {
    items { id from to amount }
    totalCount
  }
}
```

### Relations in GraphQL

Relations defined in the schema are automatically available:

```graphql
{
  account(address: "0x...") {
    address
    balance
    sentTransfers {
      items { id to amount }
    }
    receivedTransfers {
      items { id from amount }
    }
  }
}
```

## SQL over HTTP

Exposes a SQL-compatible endpoint for direct database queries from `@ponder/client`:

```ts
import { client } from "ponder";

app.use("/sql/*", client({ db, schema }));
```

This is used by `@ponder/client` on the frontend. See `references/frontend.md`.

## Custom Hono Routes

Use standard Hono routing with Drizzle queries on `db.sql`:

```ts
import { eq, desc, and, gt } from "ponder/drizzle";
import { replaceBigInts } from "ponder";
import { transfers, accounts } from "ponder:schema";

app.get("/top-holders", async (c) => {
  const result = await db.sql
    .select()
    .from(accounts)
    .where(eq(accounts.isHolder, true))
    .orderBy(desc(accounts.balance))
    .limit(10);

  return c.json(replaceBigInts(result, (v) => String(v)));
});

app.get("/transfers/:address", async (c) => {
  const address = c.req.param("address") as `0x${string}`;
  const result = await db.sql
    .select()
    .from(transfers)
    .where(
      and(
        gt(transfers.amount, 0n),
        eq(transfers.from, address)
      )
    )
    .orderBy(desc(transfers.timestamp))
    .limit(50);

  return c.json(replaceBigInts(result, (v) => String(v)));
});
```

### Using Public Clients

Access chain RPC from API routes:

```ts
import { publicClients } from "ponder:api";

app.get("/block-number", async (c) => {
  const blockNumber = await publicClients.mainnet.getBlockNumber();
  return c.json({ blockNumber: Number(blockNumber) });
});
```

### Aggregation Queries

```ts
import { count, sum, avg } from "ponder/drizzle";

app.get("/stats", async (c) => {
  const [stats] = await db.sql
    .select({
      totalTransfers: count(),
      totalVolume: sum(transfers.amount),
      avgAmount: avg(transfers.amount),
    })
    .from(transfers);

  return c.json(replaceBigInts(stats, (v) => String(v)));
});
```

### Relational Queries

```ts
app.get("/account/:address", async (c) => {
  const address = c.req.param("address") as `0x${string}`;
  const result = await db.sql.query.accounts.findFirst({
    where: eq(accounts.address, address),
    with: {
      sentTransfers: { limit: 10, orderBy: desc(transfers.timestamp) },
      receivedTransfers: { limit: 10, orderBy: desc(transfers.timestamp) },
    },
  });

  if (!result) return c.json({ error: "Not found" }, 404);
  return c.json(replaceBigInts(result, (v) => String(v)));
});
```

## replaceBigInts

JSON cannot serialize `BigInt` values. Use `replaceBigInts` to convert them:

```ts
import { replaceBigInts } from "ponder";

// Convert to string:
replaceBigInts(data, (v) => String(v));

// Convert to number (loses precision for large values):
replaceBigInts(data, (v) => Number(v));

// Custom formatting:
replaceBigInts(data, (v) => `${v}n`);
```

## Reserved Routes

These routes are handled by Ponder internally and cannot be overridden:

| Route | Description |
|-------|-------------|
| `/health` | Always returns 200. Use for liveness probes. |
| `/ready` | Returns 503 during backfill, 200 when caught up. Use for readiness probes. |
| `/status` | Returns indexing progress as JSON. |
| `/metrics` | Prometheus-format metrics. |
