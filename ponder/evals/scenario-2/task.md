# Cross-Chain Bridge Transfer Monitor

## Problem Description

A cross-chain bridge protocol operates on both Ethereum mainnet and Base. The bridge contract on each chain emits a `BridgeTransfer` event when tokens are bridged:

```
event BridgeTransfer(address indexed sender, address indexed recipient, uint256 amount, uint256 destChainId, bytes32 transferId)
```

The bridge contracts are:
- Ethereum mainnet (chain ID 1): `0x3154cf16ccdb4c6d922629664174b904d80f2c35` deployed at block `18500000`
- Base (chain ID 8453): `0x3154cf16ccdb4c6d922629664174b904d80f2c35` deployed at block `6800000`

The protocol team needs to monitor all bridge transfers across both chains in a single indexer. Because the bridge requires matching transfers between chains (a send on one chain corresponds to a receive on the other), they need cross-chain consistency in the data ordering. They want to query transfers filtered by sender, recipient, or source chain through an API.

## Output Specification

Create a complete Ponder project with:
- `ponder.config.ts` - Multi-chain configuration with appropriate ordering mode
- `ponder.schema.ts` - Schema for bridge transfers with chain awareness and query indexes
- `src/index.ts` - Indexing handler that processes events from both chains
- `src/api/index.ts` - API with both standard query interface and a custom endpoint for transfer volume summary
- `tsconfig.json` - TypeScript configuration
- `package.json` - Dependencies
- `abis/Bridge.ts` - Bridge ABI
- `.env.local` - Environment variables for both chains

The ABI for the bridge contract is:
```json
[{"type":"event","name":"BridgeTransfer","inputs":[{"name":"sender","type":"address","indexed":true},{"name":"recipient","type":"address","indexed":true},{"name":"amount","type":"uint256","indexed":false},{"name":"destChainId","type":"uint256","indexed":false},{"name":"transferId","type":"bytes32","indexed":false}]}]
```
