---
name: ponder
description: >
  Build EVM blockchain data indexers using Ponder (ponder.sh) - an open-source TypeScript
  framework for indexing smart contract events, transactions, and traces into custom database
  schemas with type-safe APIs. Use when the user mentions ponder, blockchain/EVM indexing,
  onchain data pipelines, subgraph replacement, or wants to index smart contract events into
  a queryable database.
invocations:
  - /ponder
tags:
  - blockchain
  - ethereum
  - evm
  - indexing
  - typescript
  - web3
  - ponder
version: 1.0.0
---

# Ponder Skill

## What is Ponder

Ponder is an open-source TypeScript framework that indexes EVM blockchain data into Postgres with type-safe APIs. It replaces subgraphs with 10-15x faster indexing, hot reloading, and zero-codegen type safety.

**Architecture flow:**
`ponder.config.ts` (what to index) -> `ponder.schema.ts` (where to store) -> `src/*.ts` (how to transform) -> `src/api/index.ts` (how to query)

**Stack:** v0.16.x, Drizzle ORM, Hono for HTTP, viem for Ethereum.

## Quick Start

### Scaffold

```bash
pnpm create ponder  # also: npm, yarn, bun
```

### Requirements

- Node >= 18.18, TypeScript >= 5.0.4, viem >= 2, hono >= 4.5

### tsconfig.json (exact)

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

### ponder-env.d.ts

Must exist at project root. Run `ponder codegen` to generate it.

### Environment Variables

- `PONDER_RPC_URL_<CHAIN_ID>` - RPC endpoint per chain (e.g., `PONDER_RPC_URL_1` for mainnet)
- `DATABASE_URL` - Postgres connection string (production)
- `DATABASE_SCHEMA` - Schema isolation name (production)

### Minimal Working Example

**ponder.config.ts:**
```ts
import { createConfig } from "ponder";
import { http } from "viem";
import { ERC20Abi } from "./abis/ERC20Abi";

export default createConfig({
  chains: {
    mainnet: { id: 1, rpc: process.env.PONDER_RPC_URL_1 },
  },
  contracts: {
    USDC: {
      abi: ERC20Abi,
      chain: "mainnet",
      address: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
      startBlock: 6082465,
    },
  },
});
```

**ponder.schema.ts:**
```ts
import { onchainTable } from "ponder";

export const transfers = onchainTable("transfers", (t) => ({
  id: t.text().primaryKey(),
  from: t.hex().notNull(),
  to: t.hex().notNull(),
  amount: t.bigint().notNull(),
  timestamp: t.integer().notNull(),
}));
```

**src/index.ts:**
```ts
import { ponder } from "ponder:registry";
import { transfers } from "ponder:schema";

ponder.on("USDC:Transfer", async ({ event, context }) => {
  await context.db.insert(transfers).values({
    id: event.id,
    from: event.args.from,
    to: event.args.to,
    amount: event.args.value,
    timestamp: Number(event.block.timestamp),
  });
});
```

**src/api/index.ts:**
```ts
import { Hono } from "hono";
import { db } from "ponder:api";
import { graphql } from "ponder";
import * as schema from "ponder:schema";

const app = new Hono();
app.use("/graphql", graphql({ db, schema }));
export default app;
```

## CLI Commands

| Command | Purpose |
|---------|---------|
| `ponder dev` | Development with hot reload, PGlite, port 42069 |
| `ponder start --schema <name>` | Production with Postgres |
| `ponder serve --schema <name>` | API only (no indexing), for horizontal scaling |
| `ponder codegen` | Regenerate types and `ponder-env.d.ts` |
| `ponder db list` | List schemas in database |
| `ponder db prune` | Remove unused schemas |

**Exit codes:** 75 = retryable (safe to auto-restart), 1 = fatal (check logs).

## Decision Heuristics

### Ordering Mode

| Mode | When to Use |
|------|-------------|
| `multichain` (default) | Per-chain ordering, low latency. Most projects. |
| `omnichain` | Cross-chain consistency needed (bridges, aggregators, cross-chain protocols). |
| `experimental_isolated` | Max performance. Requires `chainId` in ALL table primary keys. |

### Table vs View

- **Table** (`onchainTable`): Data written by indexing functions. Source of truth.
- **View** (`onchainView`): Aggregations/rollups computed at query time. No writes, no store API.

### Store API vs Raw SQL

- **Store API** (`context.db`): Always prefer in indexing functions. 100-1000x faster (batched writes).
- **Raw SQL** (`db.sql`): Only for complex multi-table updates that Store API cannot express.

### Factory vs Explicit Addresses

- **`factory()`**: Contract instances created dynamically at runtime (Uniswap pools, token clones).
- **Explicit `address`**: Known addresses at config time. Use array for multiple fixed addresses.

### Call Traces vs Events

- **Events**: Default choice for most indexing use cases.
- **Call traces** (`includeCallTraces: true`): Only when you need function inputs/outputs not emitted as events. Requires `debug_traceBlockByNumber` RPC support.

### includeTransactionReceipts

Only enable when you need `gasUsed`, logs from other contracts, or tx `status`. Adds significant RPC overhead.

### PGlite vs Postgres

- **PGlite**: Dev only (`ponder dev` uses it automatically).
- **Postgres**: Any shared or production environment.

### GraphQL vs Custom Routes

- **GraphQL middleware**: Standard CRUD with built-in filtering, sorting, pagination.
- **Custom Hono routes**: Complex joins, aggregations, non-standard responses, or non-GraphQL APIs.

## Gotchas and Anti-Patterns

### Setup

- ABIs MUST use `as const` assertion for type inference:
  ```ts
  export const MyAbi = [...] as const; // REQUIRED
  ```
- `ponder-env.d.ts` must exist and be current. Run `ponder codegen` after config changes.
- Set `startBlock` to the contract deployment block, NOT `0`. Setting `0` scans entire chain history (hours vs seconds).
- Local dev nodes (Anvil/Hardhat): set `disableCache: true` in chain config.
- Table/schema names: `snake_case`, max 45 characters.

### Schema

- ANTI-PATTERN: String concatenation for composite keys (`${owner}-${spender}`).
  USE: `primaryKey({ columns: [table.owner, table.spender] })`.
- All addresses are lowercase since v0.12. Never use checksummed addresses.
- Use `t.hex()` for addresses and byte data, `t.bigint()` for uint256/int256.
- Always add indexes on columns used in GraphQL filters or API WHERE clauses.

### Indexing

- Virtual module imports: `ponder:registry`, `ponder:schema`, `ponder:api`. NOT regular file paths.
- `context.db` (indexing functions, read-write) vs `db` from `ponder:api` (API routes, read-only).
- ANTI-PATTERN: Writing to database in API routes. `db` from `ponder:api` is read-only.
- `onConflictDoUpdate` callback receives the EXISTING row, not the values you passed to `.values()`.
- `context.client.readContract` automatically scopes reads to the current event's block number.
- Factory contracts: use `event.log.address` to get which child contract emitted the event.
- Multi-chain shared handlers: use `context.chain.id` to distinguish chains.
- Execution order per chain: block number -> tx index -> log index (deterministic).
- `event.id` is a 75-digit string, globally unique across chains.

### Deployment

- `ponder start` requires `--schema` flag (or `DATABASE_SCHEMA` env var).
- `experimental_isolated` ordering requires `chainId` in ALL table primary keys.

## Reference Navigation

Load the appropriate reference based on the task:

| Task | Reference |
|------|-----------|
| Configure chains, contracts, factory, accounts, blocks | `references/config.md` |
| Define tables, columns, relations, views, enums | `references/schema.md` |
| Write event handlers, DB operations, contract reads | `references/indexing.md` |
| Set up GraphQL, SQL over HTTP, custom API routes | `references/api.md` |
| Build frontend with @ponder/client, React, Next.js, tRPC | `references/frontend.md` |
| Deploy, scale, debug, monitor, configure RPC | `references/production.md` |
| Need a complete working example to start from | `references/recipes.md` |

## Common Task Checklists

### Scaffold a New Project

1. Run `pnpm create ponder` and select template
2. Add RPC URL to `.env.local` as `PONDER_RPC_URL_<CHAIN_ID>`
3. Update `ponder.config.ts` with contract address, ABI, and `startBlock`
4. Define schema in `ponder.schema.ts`
5. Write indexing functions in `src/index.ts`, then run `ponder dev`

### Add a New Contract to Index

1. Add ABI file with `as const` assertion
2. Add contract entry to `ponder.config.ts` (abi, chain, address, startBlock)
3. Add tables to `ponder.schema.ts` for the data you want to store
4. Write handler in `src/` using `ponder.on("ContractName:EventName", ...)`

### Add a Factory Contract

1. Import `parseAbiItem` from viem to define the creation event
2. Use `factory()` in config: `address: factory({ address, event, parameter })`
3. Write handler using `event.log.address` to identify the child contract
4. Schema tables may need composite PKs including the child contract address

### Add a Custom API Endpoint

1. Open `src/api/index.ts`
2. Import `db` from `ponder:api` and schema from `ponder:schema`
3. Add Hono route (`app.get("/path", ...)`) with Drizzle queries on `db.sql`

### Set Up Multi-Chain Indexing

1. Choose ordering mode (see Decision Heuristics above)
2. Add chain configs for each chain in `ponder.config.ts`
3. Use composite PKs with `chainId` if using `experimental_isolated`
4. Use `context.chain.id` in handlers when chain-specific logic is needed

### Deploy to Production

1. Provision Postgres v14-17 with <50ms latency to app server
2. Set `DATABASE_URL` and choose a `DATABASE_SCHEMA` name
3. Run `ponder start --schema <name>`
4. Health checks: `/health` (always 200), `/ready` (503 during backfill, 200 when caught up)
5. For zero-downtime redeploys, use `--views-schema` pattern
