# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability in one of these examples — particularly involving:

- Webhook signature bypass
- API key exposure patterns in example code
- Prompt injection in example implementations
- Insecure handling of user-supplied content

Please **do not open a public GitHub issue**. Instead, email **security@commune.email** with:

1. A description of the vulnerability
2. Steps to reproduce
3. The affected file(s) and line numbers
4. Suggested fix (optional but appreciated)

We'll respond within **48 hours** and aim to ship a fix within **7 days** for critical issues.

## Scope

This repo contains educational example code. The primary security considerations are:

### What we care about
- **API key handling** — `.env` files must never be committed. All examples use `.env.example` with placeholder values.
- **Webhook verification** — All inbound webhook examples verify the `x-commune-signature` header before processing.
- **Prompt injection** — Examples that process email content show how to use Commune's built-in prompt injection detection (`security.prompt_injection.risk_level`).

### What is out of scope
- Vulnerabilities in third-party dependencies (report those upstream)
- Issues with the Commune platform itself (report at [commune.email/security](https://commune.email/security))

## Security Best Practices in These Examples

All examples follow these patterns:

1. **Never hardcode credentials** — API keys only via environment variables
2. **Verify webhook signatures** — Every inbound webhook example validates the HMAC-SHA256 signature before processing
3. **Check prompt injection risk** — Examples accessing `extractedData` also check `security.prompt_injection.risk_level`
4. **Validate env at startup** — Each agent raises a clear error at startup if required env vars are missing
