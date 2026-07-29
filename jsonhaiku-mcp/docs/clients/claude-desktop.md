# Claude Desktop

## Setup

Add the following to your Claude Desktop configuration file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart Claude Desktop after saving.

## Verify

Open a new conversation and ask:

> Load this JSON and tell me what's in it: `[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]`

Claude should call `jsonhaiku_load` and respond with the structure of the data.

## Example workflow

1. Drop a JSON file on your Desktop, e.g. `~/Desktop/api_response.json`.
2. Ask Claude: *"Load `~/Desktop/api_response.json` and summarize its structure."*
3. Claude calls `jsonhaiku_load`, sees the overview.
4. Ask: *"What are the unique values of the `status` field?"*
5. Claude calls `jsonhaiku_enum` to list them.
6. Ask: *"Filter for records where `status` is 'active'."*
7. Claude calls `jsonhaiku_filter`.
