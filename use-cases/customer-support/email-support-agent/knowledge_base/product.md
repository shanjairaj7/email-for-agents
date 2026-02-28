# Acme SaaS — Product FAQ

## Getting Started

**Q: How do I create my account?**
Go to app.acme.io/signup. Enter your email address and choose a password. You will receive a confirmation email — click the link inside to activate your account. Free plan accounts are ready immediately after confirmation.

**Q: Is there a free trial?**
Yes. Every new account starts on the Free plan at no cost. The Free plan includes up to 3 projects, 1 GB of storage, and 5,000 API calls per month. No credit card is required to sign up.

**Q: What is a "project"?**
A project is the top-level container for your data, settings, and team members. Each project has its own API key, dashboard, and usage quota. You can create multiple projects under one account.

**Q: How do I invite team members?**
Open **Settings → Team** inside your project and click **Invite member**. Enter their email address and choose a role (Admin, Editor, or Viewer). They will receive an invitation email with a link to accept. Pending invitations expire after 7 days.

---

## Using the Product

**Q: Where do I find my API key?**
Go to **Settings → API Keys** inside your project. Click **Generate new key** to create one. Each key is shown once at creation time — copy it immediately and store it somewhere safe. If you lose a key, generate a new one and revoke the old one.

**Q: What are the API rate limits?**
Rate limits depend on your plan:

| Plan       | Requests/minute | Requests/month |
|------------|----------------|----------------|
| Free       | 60              | 5,000          |
| Pro        | 600             | 100,000        |
| Enterprise | Custom          | Custom         |

If you exceed the per-minute limit, the API returns `429 Too Many Requests`. Implement exponential backoff in your client.

**Q: How do I reset my password?**
On the login page, click **Forgot password?**, enter your email, and follow the link in the email you receive. Reset links expire after 1 hour. If you do not receive an email within 5 minutes, check your spam folder.

**Q: Can I export my data?**
Yes. Go to **Settings → Data Export** and click **Request export**. We will prepare a `.zip` file containing all your project data in JSON format and email you a download link within 24 hours. The link is valid for 7 days.

---

## Integrations

**Q: Which integrations are available?**
Acme integrates natively with: Slack (notifications), GitHub (webhook triggers), Zapier (no-code automation), and Webhooks (any HTTP endpoint). Third-party integrations are listed under **Settings → Integrations**.

**Q: How do I connect Slack?**
Go to **Settings → Integrations → Slack** and click **Connect**. Authorise Acme in your Slack workspace, then choose which channel should receive notifications. You can configure which event types trigger a notification (errors, completions, threshold alerts).

**Q: Does Acme have a Zapier integration?**
Yes. Search for "Acme" in the Zapier app directory. We support triggers for new records, updated records, and threshold events, and actions for creating records and sending notifications.

---

## Limits and Storage

**Q: What happens if I exceed my storage limit?**
You will receive an email warning at 80% usage and again at 95%. If you reach 100%, new writes are rejected until you either upgrade your plan or delete existing data. Existing data is not deleted automatically.

**Q: Can I increase my limits without upgrading?**
On Pro, you can purchase additional API call bundles in increments of 50,000 calls for $10 each. Go to **Billing → Add-ons**. Storage add-ons (10 GB for $5/month) are also available. Enterprise customers receive custom limits negotiated at contract time.

**Q: Is there a file size limit for uploads?**
Individual file uploads are capped at 100 MB on Free, 500 MB on Pro, and 5 GB on Enterprise. Total project storage limits apply separately.

---

## Security and Compliance

**Q: Is my data encrypted?**
Yes. Data is encrypted at rest (AES-256) and in transit (TLS 1.2+). API keys are hashed before storage — we cannot recover a key, only revoke it.

**Q: Does Acme support SSO?**
SAML 2.0 SSO is available on the Enterprise plan. Contact sales@acme.io to set it up. We support Okta, Azure AD, Google Workspace, and any SAML-compliant identity provider.
