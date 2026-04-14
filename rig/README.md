# Rig v2

Rig v2 is a small defended agent framework built on mlld.

The public API is:

```mlld
import { @rig } from "./index.mld"

var @agent = @rig.build({
  suite: "workspace",
  defense: "defended",
  records: @records,
  tools: @tools,
  model: "openrouter/z-ai/glm-5.1"
})

var @result = @rig.run(@agent, "Send the follow-up email.")
```

The design docs are the contract:

- [ARCHITECTURE.md](/Users/adam/mlld/clean/rig/ARCHITECTURE.md)
- [INTERFACE.md](/Users/adam/mlld/clean/rig/INTERFACE.md)
- [PHASES.md](/Users/adam/mlld/clean/rig/PHASES.md)
- [SECURITY.md](/Users/adam/mlld/clean/rig/SECURITY.md)
- [EXAMPLE.mld](/Users/adam/mlld/clean/rig/EXAMPLE.mld)
- [CLAUDE.md](/Users/adam/mlld/clean/rig/CLAUDE.md)

Fast local checks:

```sh
mlld --new clean/rig/tests/index.mld
mlld --new clean/rig/tests/flows/smoke.mld
mlld --new clean/rig/tests/flows/resolve.mld
mlld --new clean/rig/tests/flows/extract.mld
mlld --new clean/rig/tests/flows/derive.mld
mlld --new clean/rig/tests/flows/execute.mld
mlld --new clean/rig/tests/flows/guards.mld
```
