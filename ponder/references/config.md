# Ponder Configuration Reference

## Table of Contents

- [createConfig](#createconfig)
- [Chains](#chains)
- [Contracts](#contracts)
- [Factory Contracts](#factory-contracts)
- [mergeAbis](#mergeabis)
- [Accounts](#accounts)
- [Block Intervals](#block-intervals)
- [Database](#database)
- [Ordering Modes](#ordering-modes)
- [Multi-Chain Example](#multi-chain-example)
- [Factory Example](#factory-example)

## createConfig

```ts
import { createConfig } from "ponder";
import { http, fallback, loadBalance } from "viem";

export default createConfig({
  ordering?: "multichain" | "omnichain" | "experimental_isolated",
  database?: { ... },
  chains: { ... },
  contracts?: { ... },
  accounts?: { ... },
  blocks?: { ... },
});
```

## Chains

Each chain needs an `id` (EVM chain ID) and an `rpc` endpoint.

```ts
chains: {
  mainnet: {
    id: 1,
    rpc: process.env.PONDER_RPC_URL_1,
    // Or use an array for automatic fallback:
    // rpc: [process.env.PONDER_RPC_URL_1, process.env.PONDER_RPC_URL_1_FALLBACK],
  },
  base: {
    id: 8453,
    rpc: process.env.PONDER_RPC_URL_8453,
  },
}
```

### Chain Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | `number` | required | EVM chain ID |
| `rpc` | `string \| string[] \| Transport` | required | RPC endpoint(s) or viem Transport |
| `ws` | `string` | - | WebSocket RPC endpoint |
| `pollingInterval` | `number` | 1000 | Milliseconds between polls for new blocks |
| `disableCache` | `boolean` | false | Disable RPC cache. Set `true` for Anvil/Hardhat. |
| `ethGetLogsBlockRange` | `number` | auto | Override max block range for `eth_getLogs` |

### Advanced RPC Configuration

```ts
import { http, fallback, loadBalance } from "viem";

chains: {
  mainnet: {
    id: 1,
    // Fallback: tries each in order
    rpc: fallback([
      http(process.env.PONDER_RPC_URL_1_PRIMARY),
      http(process.env.PONDER_RPC_URL_1_FALLBACK),
    ]),
    // Or load balance across multiple endpoints:
    // rpc: loadBalance([
    //   http(process.env.PONDER_RPC_URL_1_A),
    //   http(process.env.PONDER_RPC_URL_1_B),
    // ]),
  },
}
```

## Contracts

```ts
contracts: {
  MyContract: {
    abi: MyContractAbi,                  // Must use `as const`
    chain: "mainnet",                    // Single chain
    address: "0x...",                    // Single address (lowercase)
    startBlock: 12345678,                // Contract deployment block
    endBlock?: 13000000,                 // Optional: stop indexing at this block
    filter?: { ... },                    // Optional: filter specific events/args
    includeCallTraces?: false,           // Optional: index function calls
    includeTransactionReceipts?: false,  // Optional: include tx receipts
  },
}
```

### Multi-Chain Contract

Same contract on multiple chains:

```ts
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
}
```

### Multiple Addresses (Same Chain)

```ts
contracts: {
  Tokens: {
    abi: ERC20Abi,
    chain: "mainnet",
    address: [
      "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", // USDC
      "0xdac17f958d2ee523a2206206994597c13d831ec7", // USDT
    ],
    startBlock: 6082465,
  },
}
```

### Event Filtering

```ts
contracts: {
  USDC: {
    abi: ERC20Abi,
    chain: "mainnet",
    address: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    startBlock: 6082465,
    filter: {
      event: "Transfer",                      // Single event name
      // event: ["Transfer", "Approval"],      // Or multiple events
      args: {
        from: "0x...",                         // Filter by indexed arg
        // from: ["0x...", "0x..."],           // Or array of values
      },
    },
  },
}
```

## Factory Contracts

For contracts deployed dynamically by a factory:

```ts
import { createConfig, factory } from "ponder";
import { parseAbiItem } from "viem";

export default createConfig({
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

### factory() Options

| Option | Type | Description |
|--------|------|-------------|
| `address` | `string` | Factory contract address (lowercase) |
| `event` | `AbiEvent` | ABI item for the creation event (use `parseAbiItem`) |
| `parameter` | `string` | Name of the event parameter containing the child address |
| `startBlock` | `number` | Optional: override child contract start block |
| `endBlock` | `number` | Optional: stop indexing child contracts at this block |

## mergeAbis

Combine proxy + implementation ABIs:

```ts
import { createConfig, mergeAbis } from "ponder";

export default createConfig({
  contracts: {
    MyProxy: {
      abi: mergeAbis([ProxyAbi, ImplementationAbi]),
      chain: "mainnet",
      address: "0x...",
      startBlock: 12345678,
    },
  },
});
```

## Accounts

Index account-level activity (transactions and native transfers):

```ts
accounts: {
  Vitalik: {
    chain: "mainnet",
    address: "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
    startBlock: 0,
  },
}
```

### Account Handler Types

| Handler | Trigger |
|---------|---------|
| `"Account:transaction:from"` | Transactions sent by the account |
| `"Account:transaction:to"` | Transactions received by the account |
| `"Account:transfer:from"` | Native ETH sent by the account |
| `"Account:transfer:to"` | Native ETH received by the account |

## Block Intervals

Execute a handler at fixed block intervals:

```ts
blocks: {
  PriceOracle: {
    chain: "mainnet",
    interval: 5,          // Every 5 blocks
    startBlock: 18000000,
    endBlock?: 19000000,  // Optional
  },
}
```

## Database

### PGlite (Development)

Automatic in `ponder dev`. No config needed. To customize:

```ts
database: {
  kind: "pglite",
  directory: ".ponder/pglite",
}
```

### Postgres (Production)

```ts
database: {
  kind: "postgres",
  connectionString: process.env.DATABASE_URL,
  poolConfig: {
    max: 30,
    ssl: { rejectUnauthorized: false },
  },
}
```

## Ordering Modes

| Mode | Ordering Guarantee | Performance | Use Case |
|------|-------------------|-------------|----------|
| `multichain` | Per-chain only. Events from different chains interleave freely. | Good | Default. Most projects. |
| `omnichain` | Global order across all chains by block timestamp. | Slower | Bridges, cross-chain aggregators. |
| `experimental_isolated` | Per-chain only. Each chain indexes independently with max parallelism. | Best | High throughput. Requires `chainId` in all PKs. |

```ts
export default createConfig({
  ordering: "experimental_isolated",
  // ...
});
```

## Multi-Chain Example

WETH on mainnet + Base + Optimism:

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

## Factory Example

Uniswap V3 pools:

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
