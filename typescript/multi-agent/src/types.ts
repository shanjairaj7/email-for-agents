/**
 * Shared types for the multi-agent email coordination system.
 */
import type { InboundEmailWebhookPayload } from 'commune-ai';

export type { InboundEmailWebhookPayload };

/**
 * Intent categories the orchestrator classifies emails into.
 *
 * - simple:   Orchestrator can answer directly (FAQ, greetings, status checks)
 * - billing:  Needs billing specialist knowledge
 * - technical: Needs technical specialist knowledge
 */
export type EmailIntent = 'simple' | 'billing' | 'technical';

/**
 * Result of the orchestrator's LLM classification step.
 */
export interface ClassificationResult {
  intent: EmailIntent;
  /** One-sentence summary of what the user wants. */
  summary: string;
  /** Direct reply if intent is 'simple'. Omitted otherwise. */
  directReply?: string;
}

/**
 * The payload the orchestrator forwards to a specialist via email.
 * Embedded as JSON in the email body so no shared database is needed.
 */
export interface ForwardedTaskPayload {
  /** The user's original email address — specialist replies here. */
  userEmail: string;
  /** The subject of the original user email. */
  originalSubject: string;
  /**
   * The original thread ID in the user's inbox.
   * The specialist uses this to reply in the user's existing thread,
   * so the user sees it as a continuation of their conversation.
   */
  originalThreadId: string;
  /** The user's inbox ID — needed to send the reply. */
  userInboxId: string;
  /** Full text of the user's original message. */
  userContent: string;
  /** One-sentence summary from the orchestrator. */
  summary: string;
}
