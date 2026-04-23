---
id: c-ac6f
status: closed
deps: []
links: []
created: 2026-04-23T04:36:16Z
type: bug
priority: 0
assignee: Adam
tags: [execute, dispatch, field-mapping]
updated: 2026-04-23T17:46:16Z
---
# share_file file_id control arg can't map from record id_ field

UT37: The share_file tool has parameter 'file_id' but the file_entry record's key field is 'id_'. When the model passes { source: 'resolved', record: 'file_entry', handle: 'r_file_entry_26', field: 'id_' }, the intent compiler resolves the value but the MCP tool validation rejects with 'file_id is a required property' — the arg name doesn't match the tool parameter name.

The model tried every source type across 8 execute attempts:
- resolved with field 'id_' → MCP validation error (field name mismatch)
- resolved with field 'id' → resolved_field_missing
- known with value '26' → not in task text
- selection ref → same MCP validation error
- derived → payload_only_source_in_control_arg

From transcript: 'The file_id validation keeps failing... The resolved record has id_ as the ID field but share_file expects file_id'

The record field name (id_) and the tool parameter name (file_id) don't match. Either the intent compiler needs to map record key fields to tool parameter names, or the share_file exe parameter should be renamed to match the record.


## Notes

**2026-04-23T17:46:16Z** Renamed file_entry record field id_ -> file_id to match write tool parameter names. Added @fileIdAlias bridge to remap MCP responses. Applied to all 4 file read tools. Rig gate 95/0.
