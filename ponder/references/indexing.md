# Ponder Indexing Reference

## Table of Contents

- [Imports](#imports)
- [Handler Types](#handler-types)
- [Event Object](#event-object)
- [Context Object](#context-object)
- [Store API](#store-api)
- [Raw SQL](#raw-sql)
- [Contract Reads](#contract-reads)
- [Error Behavior](#error-behavior)
- [Execution Guarantees](#execution-guarantees)

## Imports

Indexing files use virtual module imports (NOT file paths):

```ts
import { ponder } from "ponder:registry";
import { accounts, transfers } from "ponder:schema";
```

## Handler Types

### Contract Event Handler

The most common handler. Triggered by smart contract log events.

```ts
ponder.on("ContractName:EventName", async ({ event, context }) => {
  // event.args    - Decoded event arguments (typed from ABI)
  // event.log     - Raw log data (address, topics, data, logIndex)
  // event.block   - Block data (number, timestamp, hash)
  // event.transaction - Transaction data (hash, from, to, value, input)
  // event.transactionReceipt - Only if includeTransactionReceipts: true
  // event.id      - Globally unique 75-digit string

  await context.db.insert(transfers).values({
    id: event.id,
    from: event.args.from,
    to: event.args.to,
    amount: event.args.value,
  });
});
```

### Call Trace Handler

Triggered by function calls. Requires `includeCallTraces: true` in config.

```ts
ponder.on("ContractName.functionName()", async ({ event, context }) => {
  // event.args   - Function input arguments
  // event.result - Function return value
  // event.trace  - Raw trace data
  // event.block, event.transaction - same as event handler
});
```

### Account Transaction Handler

Triggered by transactions to/from an account (configured in `accounts`).

```ts
ponder.on("AccountName:transaction:from", async ({ event, context }) => {
  // event.transaction - Full transaction data
  // event.block       - Block data
});

ponder.on("AccountName:transaction:to", async ({ event, context }) => {
  // Same shape as :from
});
```

### Account Transfer Handler

Triggered by native ETH transfers to/from an account.

```ts
ponder.on("AccountName:transfer:from", async ({ event, context }) => {
  // event.transfer.value - Amount of ETH transferred (bigint)
  // event.transfer.from  - Sender address
  // event.transfer.to    - Receiver address
  // event.block, event.transaction
});

ponder.on("AccountName:transfer:to", async ({ event, context }) => {
  // Same shape as :from
});
```

### Block Handler

Triggered at block intervals (configured in `blocks`).

```ts
ponder.on("SourceName:block", async ({ event, context }) => {
  // event.block - Block data (number, timestamp, hash, etc.)
  // No event.args, event.log, or event.transaction
});
```

### Setup Handler

Runs once before indexing starts. Use for initializing singletons or seed data.

```ts
ponder.on("ContractName:setup", async ({ context }) => {
  // No event object - runs once at startup
  await context.db.insert(metadata).values({
    id: "singleton",
    totalTransfers: 0n,
    lastUpdated: 0,
  });
});
```

## Event Object

### event.args

Decoded and typed from the ABI. Access named parameters directly:

```ts
// For: event Transfer(address indexed from, address indexed to, uint256 value)
event.args.from   // `0x${string}`
event.args.to     // `0x${string}`
event.args.value  // bigint
```

### event.id

A 75-digit globally unique string. Unique across chains, blocks, transactions, and logs. Safe to use as a primary key.

### event.log

```ts
event.log.address     // Contract address that emitted the event (lowercase hex)
event.log.topics      // Raw indexed topics
event.log.data        // Raw non-indexed data
event.log.logIndex    // Position in block
event.log.blockNumber // bigint
```

### event.block

```ts
event.block.number    // bigint
event.block.timestamp // bigint (unix seconds)
event.block.hash      // `0x${string}`
event.block.baseFeePerGas // bigint | null
```

### event.transaction

```ts
event.transaction.hash  // `0x${string}`
event.transaction.from  // `0x${string}`
event.transaction.to    // `0x${string}` | null (contract creation)
event.transaction.value // bigint
event.transaction.input // `0x${string}`
event.transaction.gas   // bigint
event.transaction.nonce // number
```

### event.transactionReceipt

Only available when `includeTransactionReceipts: true` in config:

```ts
event.transactionReceipt.gasUsed        // bigint
event.transactionReceipt.status         // "success" | "reverted"
event.transactionReceipt.logs           // All logs in the transaction
event.transactionReceipt.effectiveGasPrice // bigint
```

## Context Object

### context.db

Read-write database access in indexing functions. Uses the Store API (preferred) or raw SQL.

### context.client

A viem public client automatically scoped to the current event's block number:

```ts
const balance = await context.client.readContract({
  abi: ERC20Abi,
  address: "0x...",
  functionName: "balanceOf",
  args: ["0x..."],
  // Block number is automatically set to event.block.number
});
```

### context.chain

```ts
context.chain.id   // number - Chain ID (1, 8453, 10, etc.)
context.chain.name // string - Chain name from config ("mainnet", "base", etc.)
```

### context.contracts

Access contract configurations:

```ts
context.contracts.MyContract.abi     // Contract ABI
context.contracts.MyContract.address // Contract address (may be undefined for factory)
```

## Store API

The Store API is the preferred way to write data. It is 100-1000x faster than raw SQL because writes are batched internally.

### Insert

```ts
await context.db.insert(transfers).values({
  id: event.id,
  from: event.args.from,
  to: event.args.to,
  amount: event.args.value,
});
```

### Insert with Conflict Handling

```ts
// Do nothing on conflict (skip duplicate):
await context.db
  .insert(accounts)
  .values({ address: event.args.to, balance: 0n, isHolder: false })
  .onConflictDoNothing();

// Update on conflict (upsert):
await context.db
  .insert(accounts)
  .values({
    address: event.args.to,
    balance: event.args.value,
  })
  .onConflictDoUpdate((existing) => ({
    // `existing` is the CURRENT row in the database, NOT the values you passed above
    balance: existing.balance + event.args.value,
  }));
```

### Find

```ts
// Single-column PK:
const account = await context.db.find(accounts, { address: "0x..." });
// Returns the row or null

// Composite PK:
const approval = await context.db.find(approvals, {
  owner: "0x...",
  spender: "0x...",
});
```

### Update

```ts
// Static update:
await context.db
  .update(accounts, { address: event.args.from })
  .set({ balance: 0n });

// Dynamic update (receives current row):
await context.db
  .update(accounts, { address: event.args.from })
  .set((row) => ({
    balance: row.balance - event.args.value,
  }));
```

### Delete

```ts
await context.db.delete(accounts, { address: "0x..." });
```

### Common Upsert Pattern (Balance Tracking)

```ts
ponder.on("Token:Transfer", async ({ event, context }) => {
  const { from, to, value } = event.args;

  // Decrement sender balance
  if (from !== "0x0000000000000000000000000000000000000000") {
    await context.db
      .insert(accounts)
      .values({ address: from, balance: -value, isHolder: true })
      .onConflictDoUpdate((existing) => ({
        balance: existing.balance - value,
        isHolder: existing.balance - value > 0n,
      }));
  }

  // Increment receiver balance
  await context.db
    .insert(accounts)
    .values({ address: to, balance: value, isHolder: value > 0n })
    .onConflictDoUpdate((existing) => ({
      balance: existing.balance + value,
      isHolder: existing.balance + value > 0n,
    }));

  // Record transfer
  await context.db.insert(transfers).values({
    id: event.id,
    from,
    to,
    amount: value,
    blockNumber: Number(event.block.number),
    timestamp: Number(event.block.timestamp),
  });
});
```

## Raw SQL

For complex queries that the Store API cannot express. Uses Drizzle ORM query builder.

```ts
import { eq, and, gt, sql } from "ponder/drizzle";

// Select:
const results = await context.db.sql
  .select()
  .from(transfers)
  .where(and(eq(transfers.from, "0x..."), gt(transfers.amount, 1000n)))
  .limit(10);

// Update:
await context.db.sql
  .update(accounts)
  .set({ balance: sql`${accounts.balance} + ${event.args.value}` })
  .where(eq(accounts.address, event.args.to));

// Delete:
await context.db.sql
  .delete(transfers)
  .where(eq(transfers.id, "some-id"));

// Relational query:
const result = await context.db.sql.query.accounts.findMany({
  where: eq(accounts.isHolder, true),
  with: { sentTransfers: true },
  limit: 100,
});
```

## Contract Reads

### Basic Read

```ts
const name = await context.client.readContract({
  abi: ERC20Abi,
  address: event.log.address,
  functionName: "name",
});
```

### Multicall

```ts
const [name, symbol, decimals] = await Promise.all([
  context.client.readContract({
    abi: ERC20Abi,
    address: event.log.address,
    functionName: "name",
  }),
  context.client.readContract({
    abi: ERC20Abi,
    address: event.log.address,
    functionName: "symbol",
  }),
  context.client.readContract({
    abi: ERC20Abi,
    address: event.log.address,
    functionName: "decimals",
  }),
]);
```

### Immutable Cache

For values that never change (name, symbol, decimals), use `cache: "immutable"` to avoid re-fetching:

```ts
const name = await context.client.readContract({
  abi: ERC20Abi,
  address: event.log.address,
  functionName: "name",
  cache: "immutable",
});
```

### Get Balance

```ts
const balance = await context.client.getBalance({
  address: event.args.to,
});
```

## Error Behavior

- **Constraint violations** (duplicate PK without conflict handler): Fatal exit (code 1). Fix your schema or add `.onConflictDoNothing()` / `.onConflictDoUpdate()`.
- **RPC failures**: Retryable exit (code 75). Ponder will auto-retry. Configure fallback RPC URLs.
- **No try/catch needed** for Store API operations. Errors are handled by Ponder's runtime.
- **Unhandled exceptions** in handlers: Fatal exit (code 1). Check your handler logic.

## Execution Guarantees

- **Per-chain ordering**: Events are processed in order of block number -> transaction index -> log index.
- **Deterministic**: Same inputs always produce the same outputs. Re-indexing produces identical state.
- **Automatic reorg handling**: Ponder detects chain reorganizations and replays affected events.
- **Crash recovery**: When restarted with the same schema name, indexing resumes from the last checkpoint.
- **No duplicate processing**: Each event is guaranteed to be processed exactly once (after reorg resolution).
