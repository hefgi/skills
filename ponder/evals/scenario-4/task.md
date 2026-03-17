# Production-Ready Token Indexer Deployment

## Problem Description

A team has been running a Ponder indexer in development that tracks ERC-20 token balances on Ethereum mainnet. Now they need to prepare it for production deployment. The indexer watches the WETH contract at `0xc02aaa39b223fe8d0a0e5d4e34be79256ae984e4` (deployed at block `4719568`) for Transfer and Approval events, maintaining current balances and approval allowances per account.

They need:
1. The complete Ponder project configured for production with Postgres
2. A deployment script (`deploy.sh`) that documents the exact commands to start the indexer and a separate API-only process for horizontal scaling
3. A health check configuration document (`healthcheck.md`) that describes the available health endpoints and their behavior during backfill vs when caught up
4. The project should support zero-downtime redeployments

The ERC-20 ABI events needed:
```
event Transfer(address indexed from, address indexed to, uint256 value)
event Approval(address indexed owner, address indexed spender, uint256 value)
```

## Output Specification

Create a complete Ponder project with:
- `ponder.config.ts` - Production-ready configuration
- `ponder.schema.ts` - Schema for balances and allowances
- `src/index.ts` - Indexing handlers for Transfer and Approval events
- `src/api/index.ts` - API setup
- `tsconfig.json` - TypeScript configuration
- `package.json` - Dependencies
- `abis/ERC20.ts` - ABI file
- `.env.local` - Environment variable template with all required production variables
- `deploy.sh` - Deployment commands for starting indexer and separate API process
- `healthcheck.md` - Documentation of health check endpoints and their status codes
