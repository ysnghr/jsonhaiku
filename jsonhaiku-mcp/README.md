# jsonhaiku-mcp

MCP server for [jsonhaiku](https://github.com/ysnghr/jsonhaiku) — explore
large JSON payloads from Claude Desktop, Cursor, Continue, Zed, or any
MCP-capable client.

## Quick start

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

Paste the above into your MCP client's configuration. That's it — no cloning,
no venv, no pip.

### Alternative installs

```bash
pip install jsonhaiku-mcp
# then use "jsonhaiku-mcp" as the command

pipx install jsonhaiku-mcp
```

## Tools

| Tool | What it does |
|---|---|
| `jsonhaiku_load` | Load JSON from a file, URL, or inline text. Returns a session ID. |
| `jsonhaiku_overview` | High-level summary: root type, size, top keys. |
| `jsonhaiku_describe` | Inferred type schema at any JSONPath. |
| `jsonhaiku_sample` | Representative sample values (covers edge cases). |
| `jsonhaiku_enum` | Unique values at a path, sorted by frequency. |
| `jsonhaiku_stats` | Numeric/string statistics: min, max, mean, lengths. |
| `jsonhaiku_filter` | Records matching a safe filter expression. |
| `jsonhaiku_search` | Substring search across all values. |
| `jsonhaiku_list_paths` | All observed JSONPaths in the data. |
| `jsonhaiku_unload` | Release session memory. |

## Client setup

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

### Cursor

Open Settings > MCP Servers > Add Server:

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

### Continue.dev

Add to `.continue/config.yaml`:

```yaml
mcpServers:
  - name: jsonhaiku
    command: uvx
    args:
      - jsonhaiku-mcp
```

### Zed

Add to Zed settings (`zed: settings`):

```json
{
  "context_servers": {
    "jsonhaiku": {
      "command": {
        "path": "uvx",
        "args": ["jsonhaiku-mcp"]
      }
    }
  }
}
```

## Example workflow

1. Ask Claude: *"Load `/tmp/api_response.json` and tell me what's in it."*
2. Claude calls `jsonhaiku_load`, gets a session ID and overview.
3. Claude calls `jsonhaiku_describe` to see the schema.
4. Claude calls `jsonhaiku_filter` to find specific records.
5. When done, Claude calls `jsonhaiku_unload` to free memory.

## License

MIT — see the root [LICENSE](../LICENSE).
