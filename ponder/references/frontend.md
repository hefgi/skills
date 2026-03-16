# Ponder Frontend Reference

## Table of Contents

- [@ponder/client](#ponderclient)
- [@ponder/react](#ponderreact)
- [Next.js Integration](#nextjs-integration)
- [tRPC Integration](#trpc-integration)
- [Complete Example](#complete-example)

## @ponder/client

A type-safe client for querying Ponder's SQL over HTTP endpoint.

### Installation

```bash
pnpm add @ponder/client
```

### Setup

```ts
import { createClient } from "@ponder/client";
import * as schema from "../ponder/ponder.schema"; // Import from your Ponder project

const client = createClient(
  "http://localhost:42069/sql", // Ponder SQL endpoint
  { schema }
);
```

### Querying

The client exposes a Drizzle-like query builder:

```ts
import { eq, desc, gt } from "@ponder/client/drizzle";
import { transfers, accounts } from "../ponder/ponder.schema";

// Select with filters:
const recentTransfers = await client.db
  .select()
  .from(transfers)
  .where(gt(transfers.amount, 1000000n))
  .orderBy(desc(transfers.timestamp))
  .limit(20);

// Relational queries:
const account = await client.db.query.accounts.findFirst({
  where: eq(accounts.address, "0x..."),
  with: { sentTransfers: { limit: 5 } },
});
```

### Live Queries (SSE)

Subscribe to real-time updates via Server-Sent Events:

```ts
const unsubscribe = client.live(
  (db) =>
    db.select().from(transfers).orderBy(desc(transfers.timestamp)).limit(10),
  (result) => {
    console.log("Updated transfers:", result);
  },
  (error) => {
    console.error("Live query error:", error);
  }
);

// Later: stop listening
unsubscribe();
```

## @ponder/react

React hooks for Ponder, built on `@tanstack/react-query`.

### Installation

```bash
pnpm add @ponder/react @ponder/client @tanstack/react-query
```

### Provider Setup

```tsx
import { PonderProvider } from "@ponder/react";
import { createClient } from "@ponder/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as schema from "../ponder/ponder.schema";

const ponderClient = createClient("http://localhost:42069/sql", { schema });
const queryClient = new QueryClient();

function App({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <PonderProvider client={ponderClient}>{children}</PonderProvider>
    </QueryClientProvider>
  );
}
```

### usePonderQuery

```tsx
import { usePonderQuery } from "@ponder/react";
import { desc, gt } from "@ponder/client/drizzle";
import { transfers } from "../ponder/ponder.schema";

function TransferList() {
  const { data, isLoading, error } = usePonderQuery({
    queryFn: (db) =>
      db
        .select()
        .from(transfers)
        .orderBy(desc(transfers.timestamp))
        .limit(20),
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <ul>
      {data?.map((t) => (
        <li key={t.id}>
          {t.from} -> {t.to}: {t.amount.toString()}
        </li>
      ))}
    </ul>
  );
}
```

### Live Queries with usePonderQuery

Enable real-time updates by setting `live: true`:

```tsx
const { data } = usePonderQuery({
  queryFn: (db) =>
    db.select().from(transfers).orderBy(desc(transfers.timestamp)).limit(10),
  live: true, // Auto-updates when new data is indexed
});
```

### usePonderStatus

Monitor indexing progress:

```tsx
import { usePonderStatus } from "@ponder/react";

function IndexingStatus() {
  const { data: status } = usePonderStatus({ live: true });

  if (!status) return null;

  return (
    <div>
      {status.ready ? "Caught up" : "Backfilling..."}
    </div>
  );
}
```

## Next.js Integration

### Client Components (with @ponder/react)

```tsx
// app/providers.tsx
"use client";
import { PonderProvider } from "@ponder/react";
import { createClient } from "@ponder/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as schema from "../ponder/ponder.schema";

const ponderClient = createClient(
  process.env.NEXT_PUBLIC_PONDER_URL + "/sql",
  { schema }
);
const queryClient = new QueryClient();

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <PonderProvider client={ponderClient}>{children}</PonderProvider>
    </QueryClientProvider>
  );
}
```

```tsx
// app/layout.tsx
import { Providers } from "./providers";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### Server Components (fetching directly)

```tsx
// app/page.tsx (server component)
async function getTransfers() {
  const res = await fetch(
    `${process.env.PONDER_URL}/graphql`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: `{
          transfers(limit: 10, orderBy: "timestamp", orderDirection: "desc") {
            items { id from to amount timestamp }
          }
        }`,
      }),
      next: { revalidate: 10 }, // ISR: revalidate every 10 seconds
    }
  );
  const json = await res.json();
  return json.data.transfers.items;
}

export default async function Page() {
  const transfers = await getTransfers();
  return (
    <table>
      <thead>
        <tr><th>From</th><th>To</th><th>Amount</th></tr>
      </thead>
      <tbody>
        {transfers.map((t: any) => (
          <tr key={t.id}>
            <td>{t.from}</td>
            <td>{t.to}</td>
            <td>{t.amount}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

## tRPC Integration

Use `@hono/trpc-server` to add tRPC routes alongside Ponder's API:

```ts
// src/api/index.ts
import { Hono } from "hono";
import { trpcServer } from "@hono/trpc-server";
import { initTRPC } from "@trpc/server";
import { db } from "ponder:api";
import * as schema from "ponder:schema";
import { graphql } from "ponder";
import { desc, eq } from "ponder/drizzle";
import { replaceBigInts } from "ponder";

const t = initTRPC.create();

const appRouter = t.router({
  transfers: t.procedure
    .input((v: unknown) => v as { address: string })
    .query(async ({ input }) => {
      const result = await db.sql
        .select()
        .from(schema.transfers)
        .where(eq(schema.transfers.from, input.address as `0x${string}`))
        .orderBy(desc(schema.transfers.timestamp))
        .limit(20);
      return replaceBigInts(result, (v) => String(v));
    }),
});

export type AppRouter = typeof appRouter;

const app = new Hono();
app.use("/graphql", graphql({ db, schema }));
app.use("/trpc/*", trpcServer({ router: appRouter }));

export default app;
```

## Complete Example

Next.js page with live-updating transfers table:

```tsx
"use client";
import { usePonderQuery, usePonderStatus } from "@ponder/react";
import { desc } from "@ponder/client/drizzle";
import { transfers } from "../ponder/ponder.schema";

export default function TransfersPage() {
  const { data: status } = usePonderStatus({ live: true });
  const { data, isLoading } = usePonderQuery({
    queryFn: (db) =>
      db.select().from(transfers).orderBy(desc(transfers.timestamp)).limit(50),
    live: true,
  });

  return (
    <div>
      <h1>Recent Transfers</h1>
      {status && !status.ready && <p>Indexing in progress...</p>}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>From</th>
              <th>To</th>
              <th>Amount</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((t) => (
              <tr key={t.id}>
                <td>{t.from.slice(0, 10)}...</td>
                <td>{t.to.slice(0, 10)}...</td>
                <td>{t.amount.toString()}</td>
                <td>{new Date(t.timestamp * 1000).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```
