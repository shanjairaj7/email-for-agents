# MCP Server Email & SMS Examples

Run `commune-mcp` as a local MCP server and connect it to Claude Desktop, Cursor, Windsurf, or any MCP-compatible client. No SDK integration, no code changes — the model calls Commune tools directly from within a chat session.

---

## Examples

| Example | Description |
|---------|-------------|
| [Customer Support via Claude Desktop](claude_desktop/) | Full support workflow through a Claude Desktop conversation |
| [SMS Notifications via MCP](sms/) | Provision a phone number and send SMS from within a chat session |
| [Structured Extraction via MCP](extraction/) | Define schemas and query structured data extracted from inbound emails |

---

## Install

```bash
npm install -g commune-mcp
# or
pip install commune-mcp
```

## Configure

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "commune": {
      "command": "commune-mcp",
      "args": [],
      "env": {
        "COMMUNE_API_KEY": "comm_..."
      }
    }
  }
}
```

Restart Claude Desktop. The Commune tools appear automatically in the tool selector.

### Cursor

Add to `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` globally):

```json
{
  "mcpServers": {
    "commune": {
      "command": "commune-mcp",
      "env": {
        "COMMUNE_API_KEY": "comm_..."
      }
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "commune": {
      "command": "commune-mcp",
      "env": {
        "COMMUNE_API_KEY": "comm_..."
      }
    }
  }
}
```

---

## Available tools

Once connected, the model has access to these tools automatically:

| Tool | Description |
|------|-------------|
| `commune_create_inbox` | Create an inbox and get a real email address |
| `commune_list_threads` | List threads in an inbox |
| `commune_get_thread` | Read all messages in a thread |
| `commune_send_message` | Send or reply to an email |
| `commune_search_threads` | Semantic search across threads |
| `commune_set_thread_status` | Update thread status |
| `commune_send_sms` | Send an SMS from a provisioned number |
| `commune_provision_phone` | Get a real phone number |

---

## Usage example

With `commune-mcp` running in Claude Desktop, you can have natural conversations:

> "Create an inbox called `support`, check if there are any new messages, and reply to any open tickets."

Claude will call `commune_create_inbox`, then `commune_list_threads`, then `commune_get_thread` for each open thread, then `commune_send_message` for each reply — all in a single conversation turn, with no code written.

### SMS via MCP

> "Give me a phone number I can use for notifications, then send a test SMS to +14155551234 saying 'Your order has shipped.'"

Claude calls `commune_provision_phone`, receives the number, then calls `commune_send_sms` — no SDK, no code, just a conversation.

---

## Running the MCP server manually

For development or non-standard clients:

```bash
# Start the MCP server on stdio (default — used by Claude Desktop, Cursor)
COMMUNE_API_KEY=comm_... commune-mcp

# Start on a TCP port (for clients that prefer HTTP transport)
COMMUNE_API_KEY=comm_... commune-mcp --transport http --port 3100
```

### Verify the server is working

```bash
# List available tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | COMMUNE_API_KEY=comm_... commune-mcp
```

---

## Building a custom MCP server

If you want to build your own MCP server that includes Commune alongside other tools:

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CommuneClient } from 'commune-ai';
import { z } from 'zod';

const commune = new CommuneClient({ apiKey: process.env.COMMUNE_API_KEY! });
const server = new McpServer({ name: 'my-commune-mcp', version: '1.0.0' });

server.tool(
    'send_email',
    'Send an email from the agent inbox. Provide thread_id to reply to an existing conversation.',
    {
        to:        z.string().email().describe('Recipient email address'),
        subject:   z.string().describe('Email subject'),
        body:      z.string().describe('Plain text email body'),
        inbox_id:  z.string().describe('Commune inbox ID to send from'),
        thread_id: z.string().optional().describe('Thread ID to reply into (optional)'),
    },
    async ({ to, subject, body, inbox_id, thread_id }) => {
        const msg = await commune.messages.send({
            to,
            subject,
            text: body,
            inboxId: inbox_id,
            threadId: thread_id,
        });
        return {
            content: [{ type: 'text', text: `Email sent. Message ID: ${msg.id}` }],
        };
    }
);

server.tool(
    'provision_phone_number',
    'Provision a real phone number for sending and receiving SMS.',
    {},
    async () => {
        const phone = await commune.phoneNumbers.provision();
        return {
            content: [{ type: 'text', text: `Phone number provisioned: ${phone.number} (ID: ${phone.id})` }],
        };
    }
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

---

## Tips

- Restart the client (Claude Desktop, Cursor) after changing `mcp.json` — MCP servers are loaded at startup
- Set `COMMUNE_API_KEY` in the `env` block, not in your shell — the client passes environment variables to the server process
- Use the MCP inspector (`npx @modelcontextprotocol/inspector commune-mcp`) to debug tool schemas during development
- For production use, prefer the Python or TypeScript SDK — MCP is best for interactive sessions and prototyping

---

[Back to main README](../README.md)
