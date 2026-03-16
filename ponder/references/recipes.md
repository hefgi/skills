# Ponder Recipes

## Table of Contents

- [ERC-20 Token Tracker](#erc-20-token-tracker)
- [NFT Collection Indexer](#nft-collection-indexer)
- [DEX Factory Pattern](#dex-factory-pattern)
- [Multi-Chain WETH](#multi-chain-weth)
- [Chainlink Price Oracle](#chainlink-price-oracle)
- [Tricky Patterns Cookbook](#tricky-patterns-cookbook)

---

## ERC-20 Token Tracker

Tracks USDC balances, transfers, and holder count on Ethereum mainnet.

**Contract:** USDC (`0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48`), deployed at block `6082465`.

### ABI (abis/ERC20Abi.ts)

```ts
export const ERC20Abi = [
  {
    type: "event",
    name: "Transfer",
    inputs: [
      { name: "from", type: "address", indexed: true },
      { name: "to", type: "address", indexed: true },
      { name: "value", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "Approval",
    inputs: [
      { name: "owner", type: "address", indexed: true },
      { name: "spender", type: "address", indexed: true },
      { name: "value", type: "uint256", indexed: false },
    ],
  },
  {
    type: "function",
    name: "name",
    inputs: [],
    outputs: [{ type: "string" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "symbol",
    inputs: [],
    outputs: [{ type: "string" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "decimals",
    inputs: [],
    outputs: [{ type: "uint8" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "balanceOf",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ type: "uint256" }],
    stateMutability: "view",
  },
] as const;
```

### ponder.config.ts

```ts
import { createConfig } from "ponder";
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

### ponder.schema.ts

```ts
import { onchainTable, primaryKey, index, relations } from "ponder";

export const accounts = onchainTable("accounts", (t) => ({
  address: t.hex().primaryKey(),
  balance: t.bigint().notNull(),
  isHolder: t.boolean().notNull(),
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
  })
);

export const metadata = onchainTable("metadata", (t) => ({
  id: t.text().primaryKey(),
  totalTransfers: t.bigint().notNull(),
  holderCount: t.integer().notNull(),
}));

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

### src/index.ts

```ts
import { ponder } from "ponder:registry";
import { accounts, transfers, metadata } from "ponder:schema";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000" as const;

ponder.on("USDC:setup", async ({ context }) => {
  await context.db.insert(metadata).values({
    id: "global",
    totalTransfers: 0n,
    holderCount: 0,
  });
});

ponder.on("USDC:Transfer", async ({ event, context }) => {
  const { from, to, value } = event.args;

  // Update sender (skip zero address for mints)
  if (from !== ZERO_ADDRESS) {
    const prevSender = await context.db.find(accounts, { address: from });
    const newBalance = (prevSender?.balance ?? 0n) - value;
    const wasHolder = prevSender?.isHolder ?? false;
    const isNowHolder = newBalance > 0n;

    await context.db
      .insert(accounts)
      .values({ address: from, balance: newBalance, isHolder: isNowHolder })
      .onConflictDoUpdate((existing) => ({
        balance: existing.balance - value,
        isHolder: existing.balance - value > 0n,
      }));

    // Update holder count if they stopped holding
    if (wasHolder && !isNowHolder) {
      await context.db
        .update(metadata, { id: "global" })
        .set((row) => ({ holderCount: row.holderCount - 1 }));
    }
  }

  // Update receiver
  const prevReceiver = await context.db.find(accounts, { address: to });
  const wasHolder = prevReceiver?.isHolder ?? false;

  await context.db
    .insert(accounts)
    .values({ address: to, balance: value, isHolder: value > 0n })
    .onConflictDoUpdate((existing) => ({
      balance: existing.balance + value,
      isHolder: existing.balance + value > 0n,
    }));

  // Update holder count if they became a new holder
  if (!wasHolder) {
    await context.db
      .update(metadata, { id: "global" })
      .set((row) => ({ holderCount: row.holderCount + 1 }));
  }

  // Record transfer
  await context.db.insert(transfers).values({
    id: event.id,
    from,
    to,
    amount: value,
    blockNumber: Number(event.block.number),
    timestamp: Number(event.block.timestamp),
  });

  // Update total transfers
  await context.db
    .update(metadata, { id: "global" })
    .set((row) => ({ totalTransfers: row.totalTransfers + 1n }));
});
```

### src/api/index.ts

```ts
import { Hono } from "hono";
import { db } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql, replaceBigInts } from "ponder";
import { eq } from "ponder/drizzle";

const app = new Hono();

app.use("/graphql", graphql({ db, schema }));

app.get("/stats", async (c) => {
  const [stats] = await db.sql
    .select()
    .from(schema.metadata)
    .where(eq(schema.metadata.id, "global"));

  return c.json(replaceBigInts(stats, (v) => String(v)));
});

export default app;
```

---

## NFT Collection Indexer

Tracks BAYC (Bored Ape Yacht Club) ownership and token metadata.

**Contract:** BAYC (`0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d`), deployed at block `12287507`.

### ABI (abis/ERC721Abi.ts)

```ts
export const ERC721Abi = [
  {
    type: "event",
    name: "Transfer",
    inputs: [
      { name: "from", type: "address", indexed: true },
      { name: "to", type: "address", indexed: true },
      { name: "tokenId", type: "uint256", indexed: true },
    ],
  },
  {
    type: "function",
    name: "tokenURI",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ type: "string" }],
    stateMutability: "view",
  },
] as const;
```

### ponder.config.ts

```ts
import { createConfig } from "ponder";
import { ERC721Abi } from "./abis/ERC721Abi";

export default createConfig({
  chains: {
    mainnet: { id: 1, rpc: process.env.PONDER_RPC_URL_1 },
  },
  contracts: {
    BAYC: {
      abi: ERC721Abi,
      chain: "mainnet",
      address: "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d",
      startBlock: 12287507,
    },
  },
});
```

### ponder.schema.ts

```ts
import { onchainTable, index, relations } from "ponder";

export const tokens = onchainTable("tokens", (t) => ({
  id: t.bigint().primaryKey(),
  owner: t.hex().notNull(),
  tokenUri: t.text(),
  mintedAt: t.integer().notNull(),
}));

export const owners = onchainTable("owners", (t) => ({
  address: t.hex().primaryKey(),
  tokenCount: t.integer().notNull(),
}));

export const nftTransfers = onchainTable(
  "nft_transfers",
  (t) => ({
    id: t.text().primaryKey(),
    tokenId: t.bigint().notNull(),
    from: t.hex().notNull(),
    to: t.hex().notNull(),
    timestamp: t.integer().notNull(),
  }),
  (table) => ({
    tokenIdx: index("nft_transfers_token_idx").on(table.tokenId),
  })
);

export const ownerRelations = relations(owners, ({ many }) => ({
  tokens: many(tokens),
}));

export const tokenRelations = relations(tokens, ({ one }) => ({
  ownerRef: one(owners, {
    fields: [tokens.owner],
    references: [owners.address],
  }),
}));
```

### src/index.ts

```ts
import { ponder } from "ponder:registry";
import { tokens, owners, nftTransfers } from "ponder:schema";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000" as const;

ponder.on("BAYC:Transfer", async ({ event, context }) => {
  const { from, to, tokenId } = event.args;
  const isMint = from === ZERO_ADDRESS;

  // Read tokenURI on mint
  let tokenUri: string | undefined;
  if (isMint) {
    try {
      tokenUri = await context.client.readContract({
        abi: context.contracts.BAYC.abi,
        address: event.log.address,
        functionName: "tokenURI",
        args: [tokenId],
        cache: "immutable",
      });
    } catch {
      // tokenURI may not be set yet
    }
  }

  // Upsert token
  if (isMint) {
    await context.db.insert(tokens).values({
      id: tokenId,
      owner: to,
      tokenUri: tokenUri ?? null,
      mintedAt: Number(event.block.timestamp),
    });
  } else {
    await context.db.update(tokens, { id: tokenId }).set({ owner: to });
  }

  // Decrement previous owner count (skip on mint)
  if (!isMint) {
    await context.db
      .update(owners, { address: from })
      .set((row) => ({ tokenCount: row.tokenCount - 1 }));
  }

  // Increment new owner count
  await context.db
    .insert(owners)
    .values({ address: to, tokenCount: 1 })
    .onConflictDoUpdate((existing) => ({
      tokenCount: existing.tokenCount + 1,
    }));

  // Record transfer
  await context.db.insert(nftTransfers).values({
    id: event.id,
    tokenId,
    from,
    to,
    timestamp: Number(event.block.timestamp),
  });
});
```

### src/api/index.ts

```ts
import { Hono } from "hono";
import { db } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql } from "ponder";

const app = new Hono();
app.use("/graphql", graphql({ db, schema }));
export default app;
```

---

## DEX Factory Pattern

Indexes Uniswap V3 pools created by the factory contract.

**Factory:** Uniswap V3 Factory (`0x1f98431c8ad98523631ae4a59f267346ea31f984`), deployed at block `12369621`.

### ABI (abis/PoolAbi.ts)

```ts
export const PoolAbi = [
  {
    type: "event",
    name: "Swap",
    inputs: [
      { name: "sender", type: "address", indexed: true },
      { name: "recipient", type: "address", indexed: true },
      { name: "amount0", type: "int256", indexed: false },
      { name: "amount1", type: "int256", indexed: false },
      { name: "sqrtPriceX96", type: "uint160", indexed: false },
      { name: "liquidity", type: "uint128", indexed: false },
      { name: "tick", type: "int24", indexed: false },
    ],
  },
] as const;
```

### ponder.config.ts

```ts
import { createConfig, factory } from "ponder";
import { parseAbiItem } from "viem";
import { PoolAbi } from "./abis/PoolAbi";

export default createConfig({
  chains: {
    mainnet: { id: 1, rpc: process.env.PONDER_RPC_URL_1 },
  },
  contracts: {
    UniswapV3Pool: {
      abi: PoolAbi,
      chain: "mainnet",
      address: factory({
        address: "0x1f98431c8ad98523631ae4a59f267346ea31f984",
        event: parseAbiItem(
          "event PoolCreated(address indexed token0, address indexed token1, uint24 indexed fee, int24 tickSpacing, address pool)"
        ),
        parameter: "pool",
      }),
      startBlock: 12369621,
    },
  },
});
```

### ponder.schema.ts

```ts
import { onchainTable, primaryKey, index } from "ponder";

export const pools = onchainTable("pools", (t) => ({
  address: t.hex().primaryKey(),
  token0: t.hex().notNull(),
  token1: t.hex().notNull(),
  fee: t.integer().notNull(),
  swapCount: t.integer().notNull(),
}));

export const swaps = onchainTable(
  "swaps",
  (t) => ({
    id: t.text().primaryKey(),
    pool: t.hex().notNull(),
    sender: t.hex().notNull(),
    recipient: t.hex().notNull(),
    amount0: t.bigint().notNull(),
    amount1: t.bigint().notNull(),
    timestamp: t.integer().notNull(),
  }),
  (table) => ({
    poolIdx: index("swaps_pool_idx").on(table.pool),
    timestampIdx: index("swaps_timestamp_idx").on(table.timestamp),
  })
);
```

### src/index.ts

```ts
import { ponder } from "ponder:registry";
import { pools, swaps } from "ponder:schema";

ponder.on("UniswapV3Pool:Swap", async ({ event, context }) => {
  const poolAddress = event.log.address; // Which pool emitted this event

  // Ensure pool exists (factory auto-registers, but we track metadata)
  await context.db
    .insert(pools)
    .values({
      address: poolAddress,
      token0: "0x0000000000000000000000000000000000000000", // Would need PoolCreated event to get these
      token1: "0x0000000000000000000000000000000000000000",
      fee: 0,
      swapCount: 1,
    })
    .onConflictDoUpdate((existing) => ({
      swapCount: existing.swapCount + 1,
    }));

  // Record swap
  await context.db.insert(swaps).values({
    id: event.id,
    pool: poolAddress,
    sender: event.args.sender,
    recipient: event.args.recipient,
    amount0: event.args.amount0,
    amount1: event.args.amount1,
    timestamp: Number(event.block.timestamp),
  });
});
```

### src/api/index.ts

```ts
import { Hono } from "hono";
import { db } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql, replaceBigInts } from "ponder";
import { desc } from "ponder/drizzle";

const app = new Hono();

app.use("/graphql", graphql({ db, schema }));

app.get("/top-pools", async (c) => {
  const result = await db.sql
    .select()
    .from(schema.pools)
    .orderBy(desc(schema.pools.swapCount))
    .limit(20);

  return c.json(replaceBigInts(result, (v) => String(v)));
});

export default app;
```

---

## Multi-Chain WETH

Indexes WETH transfers on mainnet, Base, and Optimism with `experimental_isolated` ordering.

### ABI (abis/WETHAbi.ts)

```ts
export const WETHAbi = [
  {
    type: "event",
    name: "Transfer",
    inputs: [
      { name: "src", type: "address", indexed: true },
      { name: "dst", type: "address", indexed: true },
      { name: "wad", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "Deposit",
    inputs: [
      { name: "dst", type: "address", indexed: true },
      { name: "wad", type: "uint256", indexed: false },
    ],
  },
] as const;
```

### ponder.config.ts

```ts
import { createConfig } from "ponder";
import { WETHAbi } from "./abis/WETHAbi";

export default createConfig({
  ordering: "experimental_isolated",
  chains: {
    mainnet: { id: 1, rpc: process.env.PONDER_RPC_URL_1 },
    base: { id: 8453, rpc: process.env.PONDER_RPC_URL_8453 },
    optimism: { id: 10, rpc: process.env.PONDER_RPC_URL_10 },
  },
  contracts: {
    WETH: {
      abi: WETHAbi,
      chain: {
        mainnet: {
          address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
          startBlock: 4719568,
        },
        base: {
          address: "0x4200000000000000000000000000000000000006",
          startBlock: 1,
        },
        optimism: {
          address: "0x4200000000000000000000000000000000000006",
          startBlock: 1,
        },
      },
    },
  },
});
```

### ponder.schema.ts

```ts
import { onchainTable, primaryKey, index } from "ponder";

// experimental_isolated requires chainId in ALL primary keys
export const balances = onchainTable(
  "balances",
  (t) => ({
    chainId: t.integer().notNull(),
    address: t.hex().notNull(),
    balance: t.bigint().notNull(),
  }),
  (table) => ({
    pk: primaryKey({ columns: [table.chainId, table.address] }),
    addressIdx: index("balances_address_idx").on(table.address),
  })
);

export const wethTransfers = onchainTable(
  "weth_transfers",
  (t) => ({
    chainId: t.integer().notNull(),
    id: t.text().notNull(),
    from: t.hex().notNull(),
    to: t.hex().notNull(),
    amount: t.bigint().notNull(),
    timestamp: t.integer().notNull(),
  }),
  (table) => ({
    pk: primaryKey({ columns: [table.chainId, table.id] }),
  })
);
```

### src/index.ts

```ts
import { ponder } from "ponder:registry";
import { balances, wethTransfers } from "ponder:schema";

ponder.on("WETH:Transfer", async ({ event, context }) => {
  const chainId = context.chain.id;
  const { src, dst, wad } = event.args;

  // Update sender balance
  await context.db
    .insert(balances)
    .values({ chainId, address: src, balance: -wad })
    .onConflictDoUpdate((existing) => ({
      balance: existing.balance - wad,
    }));

  // Update receiver balance
  await context.db
    .insert(balances)
    .values({ chainId, address: dst, balance: wad })
    .onConflictDoUpdate((existing) => ({
      balance: existing.balance + wad,
    }));

  // Record transfer
  await context.db.insert(wethTransfers).values({
    chainId,
    id: event.id,
    from: src,
    to: dst,
    amount: wad,
    timestamp: Number(event.block.timestamp),
  });
});
```

### src/api/index.ts

```ts
import { Hono } from "hono";
import { db } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql, replaceBigInts } from "ponder";
import { eq, desc } from "ponder/drizzle";

const app = new Hono();

app.use("/graphql", graphql({ db, schema }));

app.get("/balances/:address", async (c) => {
  const address = c.req.param("address") as `0x${string}`;
  const result = await db.sql
    .select()
    .from(schema.balances)
    .where(eq(schema.balances.address, address));

  return c.json(replaceBigInts(result, (v) => String(v)));
});

export default app;
```

---

## Chainlink Price Oracle

Fetches ETH/USD price at regular block intervals using a block handler.

**Contract:** Chainlink ETH/USD Price Feed (`0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419`).

### ABI (abis/AggregatorAbi.ts)

```ts
export const AggregatorAbi = [
  {
    type: "function",
    name: "latestRoundData",
    inputs: [],
    outputs: [
      { name: "roundId", type: "uint80" },
      { name: "answer", type: "int256" },
      { name: "startedAt", type: "uint256" },
      { name: "updatedAt", type: "uint256" },
      { name: "answeredInRound", type: "uint80" },
    ],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "decimals",
    inputs: [],
    outputs: [{ type: "uint8" }],
    stateMutability: "view",
  },
] as const;
```

### ponder.config.ts

```ts
import { createConfig } from "ponder";
import { AggregatorAbi } from "./abis/AggregatorAbi";

export default createConfig({
  chains: {
    mainnet: { id: 1, rpc: process.env.PONDER_RPC_URL_1 },
  },
  contracts: {
    EthUsdFeed: {
      abi: AggregatorAbi,
      chain: "mainnet",
      address: "0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419",
      startBlock: 18000000,
    },
  },
  blocks: {
    PriceSnapshot: {
      chain: "mainnet",
      interval: 5, // Every 5 blocks (~1 minute)
      startBlock: 18000000,
    },
  },
});
```

### ponder.schema.ts

```ts
import { onchainTable, index } from "ponder";

export const priceSnapshots = onchainTable(
  "price_snapshots",
  (t) => ({
    id: t.text().primaryKey(),
    price: t.bigint().notNull(),
    decimals: t.integer().notNull(),
    blockNumber: t.integer().notNull(),
    timestamp: t.integer().notNull(),
  }),
  (table) => ({
    timestampIdx: index("price_snapshots_timestamp_idx").on(table.timestamp),
  })
);
```

### src/index.ts

```ts
import { ponder } from "ponder:registry";
import { priceSnapshots } from "ponder:schema";
import { AggregatorAbi } from "../abis/AggregatorAbi";

const ETH_USD_FEED = "0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419" as const;

ponder.on("PriceSnapshot:block", async ({ event, context }) => {
  const [, answer] = await context.client.readContract({
    abi: AggregatorAbi,
    address: ETH_USD_FEED,
    functionName: "latestRoundData",
  });

  const decimals = await context.client.readContract({
    abi: AggregatorAbi,
    address: ETH_USD_FEED,
    functionName: "decimals",
    cache: "immutable",
  });

  await context.db.insert(priceSnapshots).values({
    id: `${event.block.number}`,
    price: answer,
    decimals,
    blockNumber: Number(event.block.number),
    timestamp: Number(event.block.timestamp),
  });
});
```

### src/api/index.ts

```ts
import { Hono } from "hono";
import { db } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql, replaceBigInts } from "ponder";
import { desc } from "ponder/drizzle";

const app = new Hono();

app.use("/graphql", graphql({ db, schema }));

app.get("/latest-price", async (c) => {
  const [latest] = await db.sql
    .select()
    .from(schema.priceSnapshots)
    .orderBy(desc(schema.priceSnapshots.blockNumber))
    .limit(1);

  if (!latest) return c.json({ error: "No data" }, 404);

  const priceUsd = Number(latest.price) / 10 ** latest.decimals;
  return c.json({ priceUsd, blockNumber: latest.blockNumber, timestamp: latest.timestamp });
});

export default app;
```

---

## Tricky Patterns Cookbook

Snippets for common edge cases. Not full projects.

### Handling Zero Address in Mints/Burns

```ts
const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000" as const;

ponder.on("Token:Transfer", async ({ event, context }) => {
  const { from, to, value } = event.args;
  const isMint = from === ZERO_ADDRESS;
  const isBurn = to === ZERO_ADDRESS;

  if (isMint) {
    // Don't decrement zero address balance
    // Only create/increment receiver
  } else if (isBurn) {
    // Only decrement sender
    // Don't create zero address as holder
  } else {
    // Normal transfer: decrement sender, increment receiver
  }
});
```

### Batch Processing (ERC-1155 TransferBatch)

```ts
ponder.on("Token:TransferBatch", async ({ event, context }) => {
  const { from, to, ids, values } = event.args;

  for (let i = 0; i < ids.length; i++) {
    const tokenId = ids[i]!;
    const amount = values[i]!;

    await context.db.insert(tokenBalances).values({
      account: to,
      tokenId,
      balance: amount,
    }).onConflictDoUpdate((existing) => ({
      balance: existing.balance + amount,
    }));
  }
});
```

### Setup Handler for Singleton Initialization

```ts
ponder.on("MyContract:setup", async ({ context }) => {
  // Runs once before any events are processed
  await context.db.insert(globalStats).values({
    id: "singleton",
    totalVolume: 0n,
    totalTransactions: 0,
    lastUpdated: 0,
  });
});
```

### Conditional Logic Based on Chain ID

```ts
ponder.on("WETH:Transfer", async ({ event, context }) => {
  const chainId = context.chain.id;

  // Different logic per chain
  const nativeSymbol = chainId === 1 ? "ETH" : chainId === 8453 ? "ETH" : "ETH";
  const chainLabel = context.chain.name; // "mainnet", "base", etc.

  await context.db.insert(transfers).values({
    chainId,
    id: event.id,
    chainLabel,
    // ...
  });
});
```

### Using onConflictDoUpdate Correctly

```ts
// The callback receives the EXISTING row, not your .values() input
await context.db
  .insert(accounts)
  .values({
    address: event.args.to,
    balance: event.args.value,       // Used only for INSERT
    transferCount: 1,                // Used only for INSERT
  })
  .onConflictDoUpdate((existing) => ({
    // `existing` = the current row in the database
    balance: existing.balance + event.args.value,
    transferCount: existing.transferCount + 1,
  }));

// WRONG: Don't reference values from .values() inside the callback
// .onConflictDoUpdate((existing) => ({
//   balance: existing.balance + balance, // `balance` is not in scope!
// }));
// Use the event args directly instead.
```

### Reading Multiple Contract Methods

```ts
ponder.on("Factory:PoolCreated", async ({ event, context }) => {
  // Parallel reads for better performance
  const [token0Symbol, token1Symbol, fee] = await Promise.all([
    context.client.readContract({
      abi: ERC20Abi,
      address: event.args.token0,
      functionName: "symbol",
      cache: "immutable",
    }),
    context.client.readContract({
      abi: ERC20Abi,
      address: event.args.token1,
      functionName: "symbol",
      cache: "immutable",
    }),
    context.client.readContract({
      abi: PoolAbi,
      address: event.args.pool,
      functionName: "fee",
      cache: "immutable",
    }),
  ]);

  await context.db.insert(pools).values({
    address: event.args.pool,
    token0: event.args.token0,
    token1: event.args.token1,
    token0Symbol,
    token1Symbol,
    fee: Number(fee),
    // ...
  });
});
```
