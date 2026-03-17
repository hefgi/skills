# NFT Collection Tracker with Ownership Aggregation

## Problem Description

An NFT marketplace wants to index an ERC-721 collection on Ethereum mainnet to track current token ownership and per-account statistics. The contract is at `0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d` (Bored Ape Yacht Club), deployed at block `12287507`.

For each Transfer event, the indexer should:
- Record the transfer itself (from, to, token ID, timestamp)
- Update a token ownership record so the current owner is always queryable
- Maintain per-account aggregate counts (total tokens currently held, total transfers sent, total transfers received)

When an account receives a token, their held count goes up and received count increments. When they send, held count goes down and sent count increments. The account record should be created on first interaction and updated on subsequent ones.

The standard ERC-721 Transfer event:
```
event Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
```

The team wants to query tokens by current owner and accounts by number of tokens held.

## Output Specification

Create a complete Ponder project with:
- `ponder.config.ts` - Contract configuration
- `ponder.schema.ts` - Schema for transfers, token ownership, and account aggregates
- `src/index.ts` - Indexing handler with upsert logic for accounts and ownership
- `src/api/index.ts` - API setup
- `tsconfig.json` - TypeScript configuration
- `package.json` - Dependencies
- `abis/ERC721.ts` - ABI file
- `.env.local` - Environment variables

The ABI:
```json
[{"type":"event","name":"Transfer","inputs":[{"name":"from","type":"address","indexed":true},{"name":"to","type":"address","indexed":true},{"name":"tokenId","type":"uint256","indexed":true}]}]
```
