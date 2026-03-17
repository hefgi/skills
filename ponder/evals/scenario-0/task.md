# ERC-20 Token Transfer Indexer

## Problem Description

A DeFi analytics team needs to track all transfer events for the USDC token on Ethereum mainnet. They want a Ponder indexer that captures every Transfer event, stores the sender, receiver, amount, and block timestamp, and exposes the data through a standard query interface with filtering and pagination.

The USDC contract address on mainnet is `0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48` and it was deployed at block `6082465`.

The standard ERC-20 Transfer event ABI is:
```json
[{"type":"event","name":"Transfer","inputs":[{"name":"from","type":"address","indexed":true},{"name":"to","type":"address","indexed":true},{"name":"value","type":"uint256","indexed":false}]},{"type":"event","name":"Approval","inputs":[{"name":"owner","type":"address","indexed":true},{"name":"spender","type":"address","indexed":true},{"name":"value","type":"uint256","indexed":false}]}]
```

## Output Specification

Create a complete Ponder project with the following files:
- `ponder.config.ts` - Chain and contract configuration
- `ponder.schema.ts` - Database schema for transfer records
- `src/index.ts` - Indexing function for Transfer events
- `src/api/index.ts` - API route setup for querying data
- `tsconfig.json` - TypeScript configuration
- `package.json` - Project dependencies
- `abis/ERC20Abi.ts` - The ABI file
- `.env.local` - Environment variable template

The project should be ready to run with `ponder dev` after providing an RPC URL.
