# Ponder Production Reference

## Table of Contents

- [Postgres Requirements](#postgres-requirements)
- [Database Configuration](#database-configuration)
- [Schema Isolation](#schema-isolation)
- [Zero-Downtime Deployments](#zero-downtime-deployments)
- [Health Checks](#health-checks)
- [Crash Recovery](#crash-recovery)
- [Scaling](#scaling)
- [Resource Configuration](#resource-configuration)
- [RPC Requirements](#rpc-requirements)
- [Monitoring](#monitoring)
- [Debugging Checklist](#debugging-checklist)
- [Migration Notes](#migration-notes)

## Postgres Requirements

- Version: 14, 15, 16, or 17
- Latency: <50ms from application server (same private network recommended)
- Connection limit: at least 30 connections available for Ponder

## Database Configuration

```ts
// ponder.config.ts
export default createConfig({
  database: {
    kind: "postgres",
    connectionString: process.env.DATABASE_URL,
    poolConfig: {
      max: 30,
      ssl: { rejectUnauthorized: false }, // If using SSL
    },
  },
  // ...
});
```

Or rely on the `DATABASE_URL` environment variable (auto-detected when set).

## Schema Isolation

Production requires schema isolation to prevent conflicts between deployments:

```bash
# Via CLI flag:
ponder start --schema my_app_v1

# Or via environment variable:
DATABASE_SCHEMA=my_app_v1 ponder start
```

Each schema name creates isolated Postgres schemas. Multiple instances can share the same database with different schema names.

### Managing Schemas

```bash
# List all Ponder schemas in the database:
ponder db list

# Remove unused schemas:
ponder db prune
```

## Zero-Downtime Deployments

Use the views pattern to swap between schema versions without downtime:

```bash
# Deploy new version:
ponder start --schema my_app_v2 --views-schema my_app_views

# The --views-schema creates Postgres views that point to the active schema.
# When v2 finishes backfill, the views automatically switch from v1 to v2.
# Your API (ponder serve) reads from the views schema, so it serves v1 data
# until v2 is ready, then seamlessly serves v2 data.
```

### Steps for Zero-Downtime Deploy

1. API servers: `ponder serve --schema my_app_views` (reads from views)
2. Current indexer: `ponder start --schema my_app_v1 --views-schema my_app_views`
3. Deploy new indexer: `ponder start --schema my_app_v2 --views-schema my_app_views`
4. When v2 catches up, views switch. Stop v1.

## Health Checks

| Endpoint | Behavior | Use For |
|----------|----------|---------|
| `/health` | Always returns HTTP 200 | Liveness probes (is the process alive?) |
| `/ready` | Returns 503 during backfill, 200 when caught up | Readiness probes (is the API serving current data?) |
| `/status` | Returns JSON with indexing progress per chain | Monitoring dashboards |

### /status Response Example

```json
{
  "mainnet": {
    "ready": false,
    "block": {
      "current": 18500000,
      "target": 19000000
    },
    "progress": 0.974
  }
}
```

## Crash Recovery

When Ponder restarts with the same schema name, it automatically resumes from the last checkpoint:

- No data loss between checkpoints
- No re-processing of already-indexed events
- Checkpoint frequency is automatic (approximately every few seconds)

This means `ponder start --schema X` is safe to run with auto-restart supervisors (systemd, Docker restart policies, Kubernetes, Railway, etc.).

## Scaling

### Architecture

- **One indexer**: `ponder start --schema X` (writes data, runs indexing functions)
- **N API replicas**: `ponder serve --schema X` (read-only API, no indexing)

`ponder serve` is stateless and horizontally scalable. It reads from the same Postgres database that the indexer writes to.

```bash
# Indexer (single instance):
ponder start --schema my_app

# API replicas (scale horizontally):
ponder serve --schema my_app
```

### With Views Pattern

```bash
# Indexer:
ponder start --schema my_app_v1 --views-schema my_app_views

# API replicas (point to views):
ponder serve --schema my_app_views
```

## Resource Configuration

### Memory

For large indexing jobs, increase Node.js memory:

```bash
NODE_OPTIONS="--max-old-space-size=8192" ponder start --schema my_app
```

### CPU

- `multichain` and `omnichain` ordering: single-threaded indexing
- `experimental_isolated` ordering: uses up to 4 cores (one per chain, parallelized)

## RPC Requirements

### Node Type

- **Archive node**: Required for historical data (reading state at past blocks). Most indexing requires this.
- **Full node**: Only sufficient if your `startBlock` is recent and you don't use `readContract`.

### Required Methods

| Method | Required For |
|--------|-------------|
| `eth_getLogs` | All indexing (core requirement) |
| `eth_getBlockByNumber` | All indexing (core requirement) |
| `eth_call` | `readContract` in handlers |
| `debug_traceBlockByNumber` | `includeCallTraces: true` |

### Rate Limits

- Recommended: 50-100 requests/second
- Ponder automatically manages rate limiting and retries
- Providers: Alchemy, QuickNode, Infura, Ankr, dRPC

### eth_getLogs Block Range

Different providers have different max block ranges for `eth_getLogs`. Ponder auto-detects this, but you can override:

```ts
chains: {
  mainnet: {
    id: 1,
    rpc: process.env.PONDER_RPC_URL_1,
    ethGetLogsBlockRange: 2000, // Override if auto-detection is wrong
  },
}
```

### Load Balancing / Fallback

```ts
import { http, fallback, loadBalance } from "viem";

chains: {
  mainnet: {
    id: 1,
    // Fallback: tries each in order, moves to next on failure
    rpc: fallback([
      http(process.env.PONDER_RPC_URL_1_PRIMARY),
      http(process.env.PONDER_RPC_URL_1_FALLBACK),
    ]),
  },
  base: {
    id: 8453,
    // Load balance: distributes requests across endpoints
    rpc: loadBalance([
      http(process.env.PONDER_RPC_URL_8453_A),
      http(process.env.PONDER_RPC_URL_8453_B),
    ]),
  },
}
```

Or simply use an array of URLs (automatic fallback):

```ts
chains: {
  mainnet: {
    id: 1,
    rpc: [
      process.env.PONDER_RPC_URL_1_PRIMARY,
      process.env.PONDER_RPC_URL_1_FALLBACK,
    ],
  },
}
```

## Monitoring

### Prometheus Metrics

Available at `/metrics` in Prometheus exposition format:

```bash
curl http://localhost:42069/metrics
```

Key metrics:
- `ponder_indexing_completed_events` - Total events processed
- `ponder_indexing_completed_seconds` - Time spent in handlers
- `ponder_historical_total_blocks` - Total blocks to process
- `ponder_historical_completed_blocks` - Blocks processed so far

### Logging

```bash
# Log levels: silent, error, warn, info, debug, trace
ponder start --schema my_app --log-level debug

# JSON format (for log aggregation):
ponder start --schema my_app --log-format json
```

Use `--log-level trace` for maximum detail when debugging RPC or database issues.

## Debugging Checklist

### Slow Indexing

1. **Check `startBlock`**: Should be the contract deployment block, not 0
2. **RPC rate limits**: Check provider dashboard. Add fallback URLs.
3. **Complex handlers**: Profile `readContract` calls. Use `cache: "immutable"` for static values.
4. **Database latency**: Postgres should be <50ms from app. Check `poolConfig.max`.
5. **Ordering mode**: Switch to `experimental_isolated` for max throughput if cross-chain ordering isn't needed.

### RPC Errors

1. **"429 Too Many Requests"**: Lower request rate or upgrade provider plan. Add fallback URLs.
2. **"missing trie node"**: Need an archive node. Full nodes don't have historical state.
3. **Timeout errors**: Add fallback URLs. Check provider status page.
4. **"block range too large"**: Set `ethGetLogsBlockRange` to a smaller value.

### Database Errors

1. **Connection refused**: Check `DATABASE_URL` and network connectivity
2. **Too many connections**: Increase Postgres `max_connections` or reduce `poolConfig.max`
3. **Schema already exists**: Another instance is using this schema name. Use a different name or stop the other instance.
4. **Slow queries**: Add indexes on columns used in WHERE clauses and GraphQL filters

### Fatal Exit (Code 1)

1. Check logs for the error message
2. Common causes: constraint violations, invalid ABI, missing `ponder-env.d.ts`
3. Fix the issue and restart

### Retryable Exit (Code 75)

1. Transient error (RPC timeout, DB connection drop)
2. Safe to auto-restart. Ponder resumes from checkpoint.
3. If persistent, check RPC and DB connectivity.

## Migration Notes

Key breaking changes across Ponder versions:

| Version | Change |
|---------|--------|
| 0.8 | Package renamed from `@ponder/core` to `ponder` |
| 0.9 | API file (`src/api/index.ts`) required. Must export default Hono app. |
| 0.11 | Config: `networks` renamed to `chains`. `transport` renamed to `rpc`. |
| 0.12 | All addresses normalized to lowercase. Remove checksums everywhere. |
| 0.16 | Table/schema names limited to 45 characters. |
