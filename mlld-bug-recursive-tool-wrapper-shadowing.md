# mlld bug: tool-map member call is misclassified as recursive self-call

## Summary

mlld reports a circular self-recursion when an exe named `@read_file` calls a tool-map member `@extractTools.read_file(...)`, even though the call target is an imported tools-map entry and the local exe is explicitly declared `recursive`.

This blocked the fp-proof signed-file recovery canary in cloud:

```text
Circular reference detected: executable '@read_file' calls itself recursively
without a terminating condition. If this recursion is intentional, declare it
with 'exe recursive @read_file(...)'.
```

The executable already was declared `exe recursive @read_file(...)`.

## Why It Looks Like A Compiler/Runtime Bug

The code shape is not direct recursion:

```mlld
let @file = @extractTools.read_file(@file_path)
```

`@extractTools.read_file` is a tools-map member imported from another module. It points at the imported module's `@read_file` wrapper. The local wrapper in the agent happens to share the same name.

Expected behavior:

- resolve `@extractTools.read_file` as a member access on the imported tools map;
- call that tool-map entry;
- do not classify it as a call to the local `@read_file`.

Actual behavior:

- circular-reference detection treats the member call as if the local `@read_file` calls itself;
- the error suggests adding `exe recursive`, but the exe is already recursive;
- the failure happens before useful agent execution and is reported as infrastructure failure.

## Minimal Repro

Repro module:

```mlld
>> tmp/repro-read-file-tools.mld

exe @read_file(path) = [
  => {
    file_path: @path,
    content: "ok"
  }
]

var tools @extractTools = {
  read_file: {
    mlld: @read_file,
    description: "minimal read_file entry"
  }
}

export { @extractTools, @read_file }
```

Repro caller:

```mlld
>> tmp/repro-read-file-wrapper.mld

import { @extractTools } from "./repro-read-file-tools.mld"

exe recursive @read_file(request) = [
  let @file = @extractTools.read_file(@request)
  => @file
]

show @read_file("demo.txt")
```

Run:

```sh
uv run --project bench mlld tmp/repro-read-file-wrapper.mld
```

Actual output:

```text
CircularReference: Circular reference detected: executable '@read_file' calls itself recursively without a terminating condition.
If this recursion is intentional, declare it with 'exe recursive @read_file(...)'.
at line 4, column 15 in .../tmp/repro-read-file-wrapper.mld

3 | exe recursive @read_file(request) = [
4 |   let @file = @extractTools.read_file(@request)
                  ^
5 |   => @file
```

## Important Isolation

If the imported module's underlying exe is renamed while keeping the tools-map key `read_file`, the repro succeeds:

```mlld
exe @inner_read_file(path) = [
  => { file_path: @path, content: "ok" }
]

var tools @extractTools = {
  read_file: {
    mlld: @inner_read_file,
    description: "minimal read_file entry"
  }
}

export { @extractTools }
```

So the property key `read_file` alone is not enough. The failure appears when:

- the imported module exports or defines an exe named `@read_file`;
- a tools-map member `@extractTools.read_file` points at that exe;
- the caller defines a local wrapper also named `@read_file`;
- the local wrapper calls `@extractTools.read_file(...)`.

## Real fp-proof Site

Committed fp-proof code at `0075647` has this shape:

```mlld
>> bench/domains/banking/tools.mld
exe extract:r, tool:r, untrusted @read_file(file_path) = [...]

var tools @extractTools = {
  read_file: {
    mlld: @read_file,
    ...
  }
}

export { @extractTools, ..., @read_file, ... }
```

```mlld
>> bench/agents/banking.mld
import { @resolveTools, @extractTools, @writeTools } from "../domains/banking/tools.mld"

exe recursive @read_file(request) = [
  ...
  let @file = @extractTools.read_file(@file_path)
  ...
]
```

Cloud benign canary:

```text
bench-run 25984404787
suite=banking
tasks=user_task_0 user_task_2 user_task_12 user_task_13
commit=0075647ba4d3f6b0f066b35bb9be5fe38ee05193
```

Observed:

- `user_task_0`, `user_task_2`, `user_task_13`: infrastructure error with the circular-reference message above.
- `user_task_12`: separate OpenCode sqlite initialization error in this run, not the mlld circular-reference repro.

## Workaround

Rename the local wrapper to avoid the executable-name collision while keeping the planner-facing tool key:

```mlld
exe recursive @read_attested_file(request) = [
  let @file = @extractTools.read_file(@file_path)
  ...
]

var tools @plannerTools = {
  read_file: {
    mlld: @read_attested_file,
    ...
  }
}
```

That should avoid the false recursion detection, but it is a workaround. The member-call resolver/circular-reference checker should distinguish `@extractTools.read_file(...)` from a local `@read_file(...)` call.

## Expected Fix

The circular-reference detector should use the resolved call target, including member-access base identity, rather than the final property/identifier segment alone. A call to `@extractTools.read_file(...)` should not be considered a local `@read_file(...)` self-call unless resolution actually points back to the local executable.
