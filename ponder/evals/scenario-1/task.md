# Uniswap V2 Pair Tracker

## Problem Description

A trading analytics platform wants to index all Uniswap V2 liquidity pool Swap events on Ethereum mainnet. The challenge is that Uniswap V2 creates new pair contracts dynamically through its factory contract at `0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f` (deployed at block `10000835`). Each pair contract emits Swap events when trades occur.

The factory emits a `PairCreated` event whenever a new pair is deployed:
```
event PairCreated(address indexed token0, address indexed token1, address pair, uint)
```

Each pair contract emits:
```
event Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to)
```

The team needs to track every swap across all Uniswap V2 pairs, recording which pool the swap occurred in, the amounts, and the trader address. They also want to query this data through an API that supports filtering by pool address.

## Output Specification

Create a complete Ponder project with:
- `ponder.config.ts` - Factory contract configuration for dynamic pair discovery
- `ponder.schema.ts` - Schema for swap records with appropriate keys and indexes
- `src/index.ts` - Indexing handler for Swap events from factory-created pairs
- `src/api/index.ts` - API setup for querying swap data
- `tsconfig.json` - TypeScript configuration
- `package.json` - Dependencies
- `abis/UniswapV2Factory.ts` - Factory ABI
- `abis/UniswapV2Pair.ts` - Pair ABI
- `.env.local` - Environment variable template
