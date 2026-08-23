# QMTool Webclient (WEB00)

Vue 3 + TypeScript + Vite foundation for the central product UI.

## Requirements

- Node.js **20.11.x** (see `.nvmrc` and `package.json` `engines`)

## Setup

```powershell
cd webclient
npm ci
```

## Development

```powershell
npm run dev
```

The dev server proxies `/api/v1` to the local backend (default `http://127.0.0.1:8000`).

## Tests

```powershell
npm test
```

## Type generation

After updating `docs/contracts/j04-m0-openapi.json`:

```powershell
npm run generate:types
```
