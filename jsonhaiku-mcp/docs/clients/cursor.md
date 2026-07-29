# Cursor

## Setup

Open **Settings** (Cmd+, / Ctrl+,) > **MCP Servers** > **Add Server**.

Paste the following configuration:

```json
{
  "mcpServers": {
    "jsonhaiku": {
      "command": "uvx",
      "args": ["jsonhaiku-mcp"]
    }
  }
}
```

The server will appear in the MCP Servers list. Click the toggle to enable it.

## Verify

In a Cursor chat (Cmd+L / Ctrl+L), ask:

> Load `[{"id": 1, "status": "active"}, {"id": 2, "status": "inactive"}]` and describe its schema.

Cursor should call `jsonhaiku_load` and describe the data structure.

## Example workflow

1. Point the agent at a JSON fixture in your project:
   *"Load `tests/fixtures/users.json` and tell me what fields are available."*
2. Drill into specific paths:
   *"What are the stats for the `age` field?"*
3. Filter records:
   *"Show me users where `role` is 'admin'."*
