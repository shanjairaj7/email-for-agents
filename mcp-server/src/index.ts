#!/usr/bin/env node
/**
 * Commune MCP Server
 *
 * Exposes Commune email as MCP tools for Claude Desktop, Cursor,
 * VS Code, and any MCP-compatible AI client.
 *
 * Install:
 *   npm install && npm run build
 *
 * Configure in Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):
 *   {
 *     "mcpServers": {
 *       "commune": {
 *         "command": "node",
 *         "args": ["/path/to/mcp-server/dist/index.js"],
 *         "env": { "COMMUNE_API_KEY": "comm_your_key" }
 *       }
 *     }
 *   }
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { CommuneClient } from 'commune-ai';

const commune = new CommuneClient({
  apiKey: process.env.COMMUNE_API_KEY!,
});

const server = new Server(
  { name: 'commune', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

// ── Tool definitions ───────────────────────────────────────────────────────

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // ── Email tools ──────────────────────────────────────────────────────
    {
      name: 'commune_list_inboxes',
      description: 'List all Commune inboxes and their email addresses.',
      inputSchema: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'commune_create_inbox',
      description:
        'Create a new inbox. Returns the email address (e.g., support@yourdomain.commune.email).',
      inputSchema: {
        type: 'object',
        properties: {
          local_part: {
            type: 'string',
            description: 'Inbox name, e.g. "support", "sales", "agent"',
          },
        },
        required: ['local_part'],
      },
    },
    {
      name: 'commune_list_threads',
      description:
        'List email threads in an inbox. Shows which threads are waiting for a reply.',
      inputSchema: {
        type: 'object',
        properties: {
          inbox_id: {
            type: 'string',
            description: 'Inbox ID (from commune_list_inboxes)',
          },
          limit: {
            type: 'number',
            description: 'Max threads to return (default 20)',
          },
        },
        required: ['inbox_id'],
      },
    },
    {
      name: 'commune_get_thread',
      description: 'Get all messages in an email thread.',
      inputSchema: {
        type: 'object',
        properties: {
          thread_id: { type: 'string', description: 'Thread ID' },
        },
        required: ['thread_id'],
      },
    },
    {
      name: 'commune_send_email',
      description:
        'Send an email. Use thread_id to reply in an existing conversation.',
      inputSchema: {
        type: 'object',
        properties: {
          to: { type: 'string', description: 'Recipient email address' },
          subject: { type: 'string', description: 'Email subject' },
          body: { type: 'string', description: 'Email body (plain text)' },
          inbox_id: { type: 'string', description: 'Sending inbox ID' },
          thread_id: {
            type: 'string',
            description:
              'Thread ID to reply in (optional, keeps conversation threaded)',
          },
        },
        required: ['to', 'subject', 'body', 'inbox_id'],
      },
    },
    {
      name: 'commune_search_emails',
      description:
        'Semantic search across email threads using natural language.',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Natural language search query',
          },
          inbox_id: {
            type: 'string',
            description: 'Inbox to search in (optional)',
          },
          limit: { type: 'number', description: 'Max results (default 5)' },
        },
        required: ['query'],
      },
    },
    {
      name: 'commune_set_thread_status',
      description: 'Update the status of an email thread.',
      inputSchema: {
        type: 'object',
        properties: {
          thread_id: { type: 'string' },
          status: {
            type: 'string',
            enum: ['open', 'needs_reply', 'waiting', 'closed'],
            description: 'New thread status',
          },
        },
        required: ['thread_id', 'status'],
      },
    },
    {
      name: 'commune_tag_thread',
      description: 'Add tags to an email thread for organization.',
      inputSchema: {
        type: 'object',
        properties: {
          thread_id: { type: 'string' },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Tags to add',
          },
        },
        required: ['thread_id', 'tags'],
      },
    },
  ],
}));

// ── Tool execution ─────────────────────────────────────────────────────────

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      // ── Email ──────────────────────────────────────────────────────────

      case 'commune_list_inboxes': {
        const inboxes = await commune.inboxes.list();
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                inboxes.map((i) => ({
                  id: i.id,
                  address: i.address,
                  local_part: i.localPart,
                })),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_create_inbox': {
        const inbox = await commune.inboxes.create({
          localPart: args!.local_part as string,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                { id: inbox.id, address: inbox.address },
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_list_threads': {
        const { data: threads } = await commune.threads.list({
          inbox_id: args!.inbox_id as string,
          limit: (args!.limit as number) || 20,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                threads.map((t) => ({
                  thread_id: t.thread_id,
                  subject: t.subject,
                  waiting_for_reply: t.last_direction === 'inbound',
                  message_count: t.message_count,
                  last_message_at: t.last_message_at,
                })),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_get_thread': {
        const messages = await commune.threads.messages(
          args!.thread_id as string
        );
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                messages.map((m) => ({
                  direction: m.direction,
                  sender: m.participants.find((p) => p.role === 'sender')
                    ?.identity,
                  content: m.content,
                  created_at: m.created_at,
                })),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_send_email': {
        await commune.messages.send({
          to: args!.to as string,
          subject: args!.subject as string,
          text: args!.body as string,
          inboxId: args!.inbox_id as string,
          ...(args!.thread_id
            ? { thread_id: args!.thread_id as string }
            : {}),
        });
        return { content: [{ type: 'text', text: 'Email sent successfully.' }] };
      }

      case 'commune_search_emails': {
        const results = await commune.search.threads({
          query: args!.query as string,
          inboxId: args!.inbox_id as string | undefined,
          limit: (args!.limit as number) || 5,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                results.map((r) => ({
                  thread_id: r.thread_id,
                  subject: r.subject,
                  score: r.score,
                })),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_set_thread_status': {
        await commune.threads.setStatus(
          args!.thread_id as string,
          args!.status as 'open' | 'needs_reply' | 'waiting' | 'closed'
        );
        return {
          content: [
            {
              type: 'text',
              text: `Thread status updated to: ${args!.status}`,
            },
          ],
        };
      }

      case 'commune_tag_thread': {
        await commune.threads.addTags(
          args!.thread_id as string,
          args!.tags as string[]
        );
        return {
          content: [
            {
              type: 'text',
              text: `Tags added: ${(args!.tags as string[]).join(', ')}`,
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error instanceof Error ? error.message : String(error)}`,
        },
      ],
      isError: true,
    };
  }
});

// ── Start server ───────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Commune MCP server running on stdio');
}

main().catch(console.error);
