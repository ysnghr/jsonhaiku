# Continue.dev

## Setup

Add the following to your Continue configuration file:

- **VS Code:** `.continue/config.yaml` in your project or `~/.continue/config.yaml`
- **JetBrains:** same paths, or configure via the Continue sidebar

```yaml
mcpServers:
  - name: jsonhaiku
    command: uvx
    args:
      - jsonhaiku-mcp
```

Reload the Continue extension after saving.

## Verify

In the Continue chat panel, ask:

> Load this JSON and describe it: `[{"id": 1, "name": "Alice"}]`

Continue should invoke the `jsonhaiku_load` tool and respond with the structure.

## Example workflow

1. Ask: *"Load `data/events.json` and give me an overview."*
2. Ask: *"What types does `$[*].payload` contain?"*
3. Ask: *"Search for events containing 'error'."*
