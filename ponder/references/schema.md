# Ponder Schema Reference

## Table of Contents

- [onchainTable](#onchaintable)
- [Column Types](#column-types)
- [Column Modifiers](#column-modifiers)
- [onchainEnum](#onchainenum)
- [Composite Primary Keys](#composite-primary-keys)
- [Indexes](#indexes)
- [Relations](#relations)
- [onchainView](#onchainview)
- [Drizzle Imports](#drizzle-imports)
- [ERC-20 Schema Example](#erc-20-schema-example)

## onchainTable

```ts
import { onchainTable } from "ponder";

export const myTable = onchainTable("my_table", (t) => ({
  id: t.text().primaryKey(),
  // ... columns
}));

// With constraints (composite PK, indexes):
export const myTable = onchainTable(
  "my_table",
  (t) => ({
    chainId: t.integer().notNull(),
    address: t.hex().notNull(),
    balance: t.bigint().notNull(),
  }),
  (table) => ({
    pk: primaryKey({ columns: [table.chainId, table.address] }),
    addressIdx: index("address_idx").on(table.address),
  })
);
```

**Rules:**
- Name must be `snake_case`, max 45 characters
- Every table needs a primary key (single column `.primaryKey()` or composite `primaryKey()`)
- Import `primaryKey` and `index` from `ponder` for constraints

## Column Types

| Type | TypeScript Type | SQL Type | Use For |
|------|----------------|----------|---------|
| `t.text()` | `string` | `TEXT` | Strings, identifiers |
| `t.hex()` | `` `0x${string}` `` | `TEXT` (hex-encoded) | Addresses, bytes, tx hashes |
| `t.bigint()` | `bigint` | `NUMERIC(78)` | uint256, int256, token amounts |
| `t.integer()` | `number` | `INTEGER` (4-byte) | Small numbers, chain IDs, timestamps |
| `t.real()` | `number` | `REAL` (float) | Floating point values |
| `t.boolean()` | `boolean` | `BOOLEAN` | Flags |
| `t.timestamp()` | `Date` | `TIMESTAMP` | Dates/times |
| `t.json()` | `unknown` | `JSONB` | Arbitrary JSON data |

**Key choices:**
- Addresses and byte data: always `t.hex()` (lowercase, `0x`-prefixed)
- Token amounts, balances, uint256: always `t.bigint()`
- Block timestamps: `t.integer()` (unix seconds) or `t.timestamp()` if you want Date objects
- Chain IDs, log indexes: `t.integer()`

## Column Modifiers

```ts
t.text().primaryKey()           // Primary key
t.hex().notNull()               // NOT NULL constraint
t.text().array()                // Array column (TEXT[])
t.integer().default(0)          // Default value (static)
t.bigint().$default(() => 0n)   // Default value (dynamic function)
t.json().$type<MyType>()       // Override TypeScript type
```

## onchainEnum

```ts
import { onchainEnum, onchainTable } from "ponder";

export const transferType = onchainEnum("transfer_type", [
  "mint",
  "burn",
  "transfer",
]);

export const transfers = onchainTable("transfers", (t) => ({
  id: t.text().primaryKey(),
  type: transferType().notNull(),
  // ...
}));
```

## Composite Primary Keys

Use when a single column isn't sufficient to uniquely identify a row:

```ts
import { onchainTable, primaryKey } from "ponder";

export const balances = onchainTable(
  "balances",
  (t) => ({
    chainId: t.integer().notNull(),
    account: t.hex().notNull(),
    token: t.hex().notNull(),
    balance: t.bigint().notNull(),
  }),
  (table) => ({
    pk: primaryKey({ columns: [table.chainId, table.account, table.token] }),
  })
);
```

**When to use composite PKs:**
- Multi-chain indexing with `experimental_isolated` (must include `chainId`)
- Per-account-per-token balances
- Approval tracking (owner + spender)
- Any entity identified by multiple dimensions

## Indexes

Add indexes on columns used in GraphQL filters or API WHERE clauses:

```ts
import { onchainTable, index } from "ponder";

export const transfers = onchainTable(
  "transfers",
  (t) => ({
    id: t.text().primaryKey(),
    from: t.hex().notNull(),
    to: t.hex().notNull(),
    amount: t.bigint().notNull(),
    timestamp: t.integer().notNull(),
  }),
  (table) => ({
    fromIdx: index("from_idx").on(table.from),
    toIdx: index("to_idx").on(table.to),
    // Multi-column index:
    timestampFromIdx: index("timestamp_from_idx").on(
      table.timestamp,
      table.from
    ),
  })
);
```

## Relations

Define relationships between tables for GraphQL joins and relational queries:

```ts
import { onchainTable, relations } from "ponder";

export const accounts = onchainTable("accounts", (t) => ({
  address: t.hex().primaryKey(),
  balance: t.bigint().notNull(),
}));

export const transfers = onchainTable("transfers", (t) => ({
  id: t.text().primaryKey(),
  from: t.hex().notNull(),
  to: t.hex().notNull(),
  amount: t.bigint().notNull(),
}));

// one() = belongs-to, many() = has-many
export const accountRelations = relations(accounts, ({ many }) => ({
  sentTransfers: many(transfers, { relationName: "sender" }),
  receivedTransfers: many(transfers, { relationName: "receiver" }),
}));

export const transferRelations = relations(transfers, ({ one }) => ({
  sender: one(accounts, {
    fields: [transfers.from],
    references: [accounts.address],
    relationName: "sender",
  }),
  receiver: one(accounts, {
    fields: [transfers.to],
    references: [accounts.address],
    relationName: "receiver",
  }),
}));
```

**`relationName`**: Required when multiple relations reference the same table (like `sender` and `receiver` both pointing to `accounts`).

### Many-to-Many

Use a join table:

```ts
export const tokenHolders = onchainTable(
  "token_holders",
  (t) => ({
    token: t.hex().notNull(),
    holder: t.hex().notNull(),
    balance: t.bigint().notNull(),
  }),
  (table) => ({
    pk: primaryKey({ columns: [table.token, table.holder] }),
  })
);
```

## onchainView

Views compute derived data at query time. They are not written to by indexing functions.

```ts
import { onchainTable, onchainView } from "ponder";
import { count, sum, desc, sql } from "ponder/drizzle";

export const transfers = onchainTable("transfers", (t) => ({
  id: t.text().primaryKey(),
  from: t.hex().notNull(),
  to: t.hex().notNull(),
  amount: t.bigint().notNull(),
}));

export const transferStats = onchainView("transfer_stats", (t) => ({
  address: t.hex().primaryKey(),
  totalSent: t.bigint(),
  sendCount: t.integer(),
}));

// Define the view query in the schema file:
// The view is populated by Ponder at query time.
```

**Limitations of views:**
- Cannot be written to via Store API
- No cursor pagination in GraphQL (offset pagination only)
- No singular GraphQL queries (only plural)
- Best for aggregation dashboards and analytics

## Drizzle Imports

```ts
// Operators (for API queries and views)
import { eq, ne, gt, gte, lt, lte, and, or, not, inArray } from "ponder/drizzle";

// Aggregations
import { count, sum, avg, min, max } from "ponder/drizzle";

// Sorting
import { desc, asc } from "ponder/drizzle";

// Raw SQL expressions
import { sql } from "ponder/drizzle";
```

## ERC-20 Schema Example

Complete schema for tracking an ERC-20 token:

```ts
import { onchainTable, onchainView, primaryKey, index, relations } from "ponder";

export const accounts = onchainTable("accounts", (t) => ({
  address: t.hex().primaryKey(),
  balance: t.bigint().notNull(),
  isHolder: t.boolean().notNull(),
  lastUpdatedBlock: t.integer().notNull(),
}));

export const transfers = onchainTable(
  "transfers",
  (t) => ({
    id: t.text().primaryKey(),
    from: t.hex().notNull(),
    to: t.hex().notNull(),
    amount: t.bigint().notNull(),
    blockNumber: t.integer().notNull(),
    timestamp: t.integer().notNull(),
  }),
  (table) => ({
    fromIdx: index("transfers_from_idx").on(table.from),
    toIdx: index("transfers_to_idx").on(table.to),
    timestampIdx: index("transfers_timestamp_idx").on(table.timestamp),
  })
);

export const approvals = onchainTable(
  "approvals",
  (t) => ({
    owner: t.hex().notNull(),
    spender: t.hex().notNull(),
    amount: t.bigint().notNull(),
  }),
  (table) => ({
    pk: primaryKey({ columns: [table.owner, table.spender] }),
  })
);

export const accountRelations = relations(accounts, ({ many }) => ({
  sentTransfers: many(transfers, { relationName: "sender" }),
  receivedTransfers: many(transfers, { relationName: "receiver" }),
}));

export const transferRelations = relations(transfers, ({ one }) => ({
  sender: one(accounts, {
    fields: [transfers.from],
    references: [accounts.address],
    relationName: "sender",
  }),
  receiver: one(accounts, {
    fields: [transfers.to],
    references: [accounts.address],
    relationName: "receiver",
  }),
}));
```
