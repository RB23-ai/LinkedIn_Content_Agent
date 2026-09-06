# LinkedIn AI Strategist — Multi-Tenant SaaS

A multi-company (multi-workspace) AI agent system for LinkedIn content:
research → strategy → writing → editing → hashtags/image suggestions,
plus competitor benchmarking, lead capture, and internal sharing.

## 1. Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in your keys
streamlit run app.py
```

## 2. Getting your API keys

| Service | Why | Link |
|---|---|---|
| Groq | Fast, free-tier LLM for the agents | https://groq.com |
| Tavily (optional) | Web search for the research agent | https://tavily.com |
| LinkedIn Developer app | Publish posts + read your own profile | https://www.linkedin.com/developers |
| Unsplash (optional) | Stock image suggestions | https://unsplash.com/developers |

### LinkedIn app setup (important — read this)
1. Create an app at the LinkedIn Developer Portal.
2. Add the **"Share on LinkedIn"** product (lets you publish) and
   **"Sign In with LinkedIn using OpenID Connect"** (lets you read the
   authenticated user's profile via `/v2/userinfo`).
3. Under **Auth**, generate a 3-legged OAuth token with scopes:
   `openid profile email w_member_social`.
4. Put that token in `.env` as `LINKEDIN_ACCESS_TOKEN`.

**What this app can and can't do with a standard app approval:**
- ✅ Publish a post as the logged-in member.
- ✅ Read that member's own profile and their own recent posts.
- ❌ Fetch posts from an arbitrary competitor's profile or page you don't
  administer — LinkedIn restricts that to its Marketing Developer
  Platform partners (a separate, manually-approved partnership, not a
  normal OAuth scope). This project handles competitor benchmarking by
  letting you **paste in** competitor post text/stats through the
  Competitors page instead of scraping them — see `utils/linkedin_publisher.py`'s
  docstring for the full explanation.

## 3. Project structure

```
linkedin-agent-system/
├── app.py                        # Streamlit UI (all pages)
├── config/agents.yaml            # Reference copy of agent personas
├── agents/                       # One file per CrewAI agent
├── tasks/definitions.py          # CrewAI task factory functions
├── utils/
│   ├── database.py                # Multi-tenant SQLite (workspace_id isolation)
│   ├── vector_store.py            # Per-workspace ChromaDB collections
│   ├── linkedin_publisher.py      # LinkedIn REST API wrapper
│   ├── crew_runner.py             # Composes the agent pipeline
│   ├── sharing_utils.py           # WhatsApp link / Slack webhook
│   ├── lead_capture.py            # Keyword + optional LLM lead detection
│   └── scheduler.py               # Daily auto-publish of scheduled posts
├── models/schemas.py              # Pydantic models
└── requirements.txt
```

## 4. How data isolation works

- **SQLite**: every table (`ideas`, `posts`, `competitors`, `leads`) has a
  `workspace_id` foreign key, and every query in `database.py` filters by
  it — including updates (`WHERE id = ? AND workspace_id = ?`), so a
  leaked/guessed row id from another company can't be edited.
- **Vector store**: each workspace gets its own Chroma **collection**
  (not just a metadata filter), so there's no code path that could
  accidentally return another company's embeddings.

## 5. Running the daily scheduler

`utils/scheduler.py` starts an APScheduler background job (default
08:00 UTC) that publishes any post whose `scheduled_date` has arrived,
for every workspace that has a LinkedIn token configured. It's started
once per app process in `app.py` via a `st.session_state` guard so
Streamlit's reruns don't register duplicate jobs.

⚠️ On Streamlit Community Cloud / most serverless hosts, background
processes can be killed when the app is idle. For reliable scheduled
publishing in production, run the scheduler as a **separate process**
(e.g. a cron job or a small worker dyno) that imports and calls
`utils.scheduler._publish_due_posts()` directly, rather than relying on
it living inside the Streamlit process.

## 6. Deployment

- **Streamlit Community Cloud**: connect your GitHub repo, add your
  `.env` values as "Secrets," done.
- **Self-hosted**: any VPS with Docker; expose port 8501.
- For the scheduler caveat above, add a second lightweight process
  (systemd timer / cron / separate worker) for reliable publishing.

## 7. Making it sellable — next steps

- **Billing**: gate workspace creation behind a Stripe subscription
  check (`workspace count <= plan limit`).
- **Auth**: add a real login (e.g. `streamlit-authenticator` or a
  proper OAuth login) — right now anyone who opens the app can switch
  between all workspaces, which is fine for internal use but not for a
  multi-customer SaaS. Add a `users` table mapping login → allowed
  `workspace_id`s and filter the sidebar's workspace list by it.
- **Per-workspace LinkedIn tokens**: the Settings page already lets you
  store a token per workspace so each company can connect their own
  LinkedIn account rather than sharing one.
- **Rate limiting**: LinkedIn and Groq both have rate limits — add
  basic backoff/retry around `LinkedInAPI` and `crew_runner.generate_post`.
- **Swap SQLite → Postgres** once you have concurrent multi-customer
  traffic; the `Database` class's method signatures are written to make
  that swap straightforward.
