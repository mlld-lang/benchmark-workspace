# Record Refine Migration

This guide covers the mlld 2.1 record syntax change from top-level record `when [...]` to `labels:` plus `refine [...]`.

## Core Mapping

Old record conditional tiers:

```mlld
record @contact = {
  facts: [email: string],
  data: [notes: string?],
  when [
    internal => :internal
    * => :external
  ]
}
```

New shape:

```mlld
record @contact = {
  facts: [email: string],
  data: [notes: string?],
  refine [
    when [
      internal => facts += ["internal"]
      * => facts += ["external"]
    ]
  ]
}
```

Old `=> data` demotion:

```mlld
when [
  verified => :verified
  * => data
]
```

New demotion:

```mlld
refine [
  when [
    verified => facts += ["verified"]
    * => facts = []
  ]
]
```

Old data trust overrides:

```mlld
when [
  @input.author_association == "MEMBER" => :maintainer {
    data: { trusted: [title] }
  }
]
```

New field-targeted trust:

```mlld
refine [
  @input.author_association == "MEMBER" => [
    facts += ["maintainer"]
    data.title = trusted
  ]
]
```

## Tool Labels

Input records can now carry static and conditional tool operation labels:

```mlld
record @send_email_inputs = {
  facts: [recipient: string],
  data: [subject: string, body: string],
  labels: ["tool:w", "exfil:send", "comm:w"],
  refine [
    body.length > 0 => labels += ["message:body"]
  ],
  validate: "strict"
}
```

Tool-entry `labels:` still work. The effective operation labels are:

```text
record labels + matching record refine labels + tool-entry labels
```

Prefer putting labels that describe the input contract on the input record. Keep tool-entry labels for wrapper-specific labels or while migrating non-record-backed tools.

## Semantics To Preserve

- Top-level `refine` entries are all-match.
- Nested `when [...]` groups are first-match.
- `labels += [...]` is the only label action. Records cannot remove or replace labels.
- `facts += [...]` adds tiers to all fact fields.
- `facts.field += [...]` adds tiers to one fact field.
- `facts = []` demotes all fact fields to data for that matching path.
- `facts.field = []` demotes one fact field.
- `data.field = trusted` clears inherited untrusted taint for that data field without minting fact proof.
- `data.field = untrusted` keeps inherited untrusted taint.
- `kind` and `accepts` remain static fact-field metadata. Do not move them into `refine`.

## Migration Checklist

1. Replace every record-level `when [...]` section with `refine [...]`.
2. Convert tier shorthand `=> :tier` to `facts += ["tier"]`.
3. Convert `=> data` to `facts = []`.
4. Convert `data: { trusted: [field] }` branch overrides to `data.field = trusted`.
5. Move stable tool-operation labels from tool entries into input records when they describe the record contract.
6. Keep catalog labels for non-record-backed tools and wrapper-specific operation labels.
7. Run zero-LLM tests after each converted cluster.

## Things That Should Fail

These are intentional errors in the new syntax:

```mlld
when [ ... ]                 >> record-level when is removed
labels = ["safe"]            >> records cannot replace labels
labels -= ["untrusted"]      >> records cannot remove labels
facts.body += ["verified"]   >> body must be a fact field
data.email = trusted         >> email must be a data field
```
