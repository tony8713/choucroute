# @choucroute/config

Shared ESLint, TypeScript and madge presets for the choucroute monorepo. Mirrors
the setup of [`@stage-labs/config`](https://github.com/bonustrack/stage) so the JS
workspaces here follow the same house style: strict type-checked lint, single
quotes, banned comments, 400-line file cap, 100-line function cap.

## Usage

Workspaces are declared in the repo-root `choucroute.config.js` via `defineConfig`.
The `choucroute` CLI reads it:

```
choucroute lint       # eslint across every workspace
choucroute typecheck  # tsc --noEmit per workspace
choucroute madge      # circular-dependency check
```

Each workspace extends the shared TS base:

```json
{ "extends": "@choucroute/config/tsconfig/base.json" }
```
