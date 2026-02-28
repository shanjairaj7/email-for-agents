#!/usr/bin/env node
/**
 * Commune MCP Server
 *
 * Exposes Commune email & SMS as MCP tools for Claude Desktop, Cursor,
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
    // ── SMS tools ────────────────────────────────────────────────────────
    {
      name: 'commune_list_phone_numbers',
      description: 'List provisioned phone numbers for SMS.',
      inputSchema: { type: 'object', properties: {}, required: [] },
    },
    {
      name: 'commune_send_sms',
      description: 'Send an SMS message.',
      inputSchema: {
        type: 'object',
        properties: {
          to: {
            type: 'string',
            description:
              'Recipient phone number in E.164 format (+14155551234)',
          },
          body: { type: 'string', description: 'SMS message text' },
          phone_number_id: {
            type: 'string',
            description: 'Your Commune phone number ID',
          },
        },
        required: ['to', 'body', 'phone_number_id'],
      },
    },
    {
      name: 'commune_list_sms_conversations',
      description: 'List SMS conversations.',
      inputSchema: {
        type: 'object',
        properties: {
          phone_number_id: {
            type: 'string',
            description: 'Phone number ID to list conversations for',
          },
        },
        required: ['phone_number_id'],
      },
    },
    {
      name: 'commune_get_sms_thread',
      description: 'Get all SMS messages with a specific phone number.',
      inputSchema: {
        type: 'object',
        properties: {
          remote_number: {
            type: 'string',
            description: 'The other party phone number (E.164)',
          },
          phone_number_id: {
            type: 'string',
            description: 'Your Commune phone number ID',
          },
        },
        required: ['remote_number', 'phone_number_id'],
      },
    },
    {
      name: 'commune_search_sms',
      description: 'Semantic search across SMS messages.',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Natural language search query',
          },
          phone_number_id: { type: 'string' },
          limit: { type: 'number' },
        },
        required: ['query'],
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

      // ── SMS ────────────────────────────────────────────────────────────

      case 'commune_list_phone_numbers': {
        const numbers = await commune.phoneNumbers.list();
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                numbers.map((n) => ({
                  id: n.id,
                  number: n.number,
                  type: n.numberType,
                  sms: n.capabilities.sms,
                  voice: n.capabilities.voice,
                })),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_send_sms': {
        const result = await commune.sms.send({
          to: args!.to as string,
          body: args!.body as string,
          phone_number_id: args!.phone_number_id as string,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                status: result.status,
                message_id: result.message_id,
              }),
            },
          ],
        };
      }

      case 'commune_list_sms_conversations': {
        const convos = await commune.sms.conversations({
          phone_number_id: args!.phone_number_id as string,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                convos.map((c) => ({
                  thread_id: c.thread_id,
                  remote_number: c.remote_number,
                  message_count: c.message_count,
                  last_message: c.last_message_preview,
                })),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'commune_get_sms_thread': {
        const messages = await commune.sms.thread(
          args!.remote_number as string,
          args!.phone_number_id as string
        );
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                messages.map((m) => ({
                  direction: m.direction,
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

      case 'commune_search_sms': {
        const results = await commune.sms.search({
          q: args!.query as string,
          phone_number_id: args!.phone_number_id as string | undefined,
          limit: (args!.limit as number) || 5,
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                results.map((m) => ({
                  message_id: m.message_id,
                  content: m.content,
                  direction: m.direction,
                })),
                null,
                2
              ),
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
