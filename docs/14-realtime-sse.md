# DEPRECATED - Real-Time Updates via SSE

> **This document is deprecated and no longer applies to the current architecture.**

## What Changed

SSE (Server-Sent Events) has been **removed** from the architecture.

Real-time updates are now handled by **PouchDB live sync** with CouchDB:
- No separate real-time connection needed
- Changes sync automatically in both directions
- Built-in conflict resolution
- Works offline

## Current Documentation

See these documents for the current architecture:
- [01-architecture.md](./01-architecture.md) - System architecture overview
- [05-offline-sync.md](./05-offline-sync.md) - PouchDB/CouchDB sync strategy
- [10-services.md](./10-services.md) - Service configuration

## Why SSE Was Removed

| SSE (Old) | PouchDB Live Sync (New) |
|-----------|-------------------------|
| Separate connection to maintain | Built into database layer |
| Required Redis pub/sub | No additional services |
| Server-to-client only | Bidirectional sync |
| Custom error handling | Battle-tested protocol |
