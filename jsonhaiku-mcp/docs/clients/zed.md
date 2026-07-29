# Zed

## Setup

Open Zed settings (`zed: settings` from the command palette) and add:

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

Save and restart Zed.

## Verify

Open the assistant panel and ask:

> Load `[{"id": 1, "type": "event"}]` and tell me about it.

Zed should call `jsonhaiku_load` and describe the structure.

## Example workflow

1. Ask: *"Load `~/Downloads/response.json` and summarize it."*
2. Ask: *"List all paths up to depth 3."*
3. Ask: *"What are the enum values at `$[*].category`?"*
