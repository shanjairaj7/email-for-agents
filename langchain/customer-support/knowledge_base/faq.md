# Frequently Asked Questions

Answers to the most common questions about Beacon — the SaaS platform for team analytics.

---

## General

### What is Beacon?

Beacon is a team analytics and productivity platform that helps engineering and product teams understand how their work flows — from planning through deployment. It connects to your issue tracker, code repository, and calendar to surface bottlenecks, cycle time metrics, and team health insights.

### Is Beacon suitable for small teams?

Yes. Beacon works well for teams of any size. Our Starter plan is designed for teams of up to 10 people, while Growth and Enterprise plans support unlimited members. Many solo engineers and two-person teams use Beacon to track their own throughput.

### What integrations does Beacon support?

Beacon currently integrates with:
- **Issue trackers**: Jira, Linear, GitHub Issues, Asana
- **Code hosts**: GitHub, GitLab, Bitbucket
- **Calendars**: Google Calendar, Outlook
- **Communication**: Slack (for alerts and digests)
- **CI/CD**: GitHub Actions, CircleCI, BuildKite

We add new integrations regularly. If you need something specific, email support or vote on our public roadmap.

### Does Beacon work with monorepos?

Yes. You can configure multiple projects within a single repository. Each project can have its own metrics dashboard, labels, and cycle time targets.

---

## Account Management

### How do I invite team members?

Go to **Settings → Team → Invite Members**. Enter one or more email addresses and choose a role (Admin, Member, or Viewer). Invitees receive an email with a signup link that is valid for 7 days.

### What is the difference between Admin, Member, and Viewer roles?

- **Admin** — full access to settings, billing, integrations, and all dashboards. Can invite and remove members.
- **Member** — can view and interact with all dashboards, create custom reports, and configure personal notifications. Cannot access billing or invite others.
- **Viewer** — read-only access to shared dashboards. Cannot create reports or modify any settings. Free on all plans.

### How do I change the email address on my account?

Go to **Settings → Profile → Email Address**. We'll send a confirmation link to the new address before the change takes effect. If you've lost access to your original email, contact support with proof of ownership.

### How do I reset my password?

Click **Forgot password** on the login page and enter your account email. You'll receive a reset link within a few minutes. Reset links expire after 1 hour.

### Can I have multiple workspaces?

Yes. Each workspace is independent with its own integrations, team members, and billing. You can switch between workspaces from the top-left workspace switcher. A single user account can belong to multiple workspaces.

---

## Features & Usage

### How is "cycle time" calculated?

Cycle time measures the time from when work is started (first moved to an "In Progress" state) to when it is merged or marked done. Beacon calculates this automatically from your issue tracker and code host. You can customize which states count as "started" and "done" in **Settings → Metrics**.

### Can I create custom dashboards?

Yes. From any dashboard, click **New Dashboard** in the sidebar. You can add, resize, and reorder widgets including cycle time charts, throughput histograms, team heatmaps, and custom SQL-powered data tables (Growth and Enterprise plans).

### How far back does historical data go?

When you first connect an integration, Beacon imports up to 12 months of historical data. On Enterprise plans, the historical import limit is extended to 36 months.

### Is there a mobile app?

Not yet. Beacon is optimised for desktop browsers. A mobile-friendly view for read-only dashboards is on our roadmap for later this year.

### How do I export data?

Go to any dashboard and click **Export** (top right). You can export as CSV, PNG (chart snapshot), or PDF (full report). Programmatic access is available via our REST API on Growth and Enterprise plans.

---

## Support & SLA

### What support channels are available?

- **Email** — all plans, typically responded to within 1 business day
- **Live chat** — Growth and Enterprise plans, available Monday–Friday 9am–6pm ET
- **Dedicated Slack channel** — Enterprise plans only
- **Phone** — Enterprise plans only

### Do you offer a service level agreement (SLA)?

SLAs are available on Enterprise plans. Our standard uptime target is 99.9% monthly. You can view real-time status and historical uptime at **status.beacon.app**.
