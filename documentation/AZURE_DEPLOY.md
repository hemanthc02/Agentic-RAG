# Deploying VeritasRAG to Azure App Service

A beginner-friendly, copy-paste guide for **your** resources. It uses Azure
App Service (online / Claude mode) plus your three managed services:

| Purpose | Your resource | App setting |
|---|---|---|
| PDF storage | Storage account `hemanthaistorage`, container `documents` | `STORAGE_BACKEND=azure_blob` |
| Vector store | AI Search `hemanth-ai-search` (free) | `SEARCH_BACKEND=azure_search` |
| Metadata DB | Azure SQL `free-sql-db-1845311` on `hemanth-admin` | `DB_BACKEND=azure_sql` |
| Answers (LLM) | Anthropic Claude (cloud API) | `ANTHROPIC_API_KEY` |

> **Offline mode now works via your Ollama VM.** You are hosting Ollama +
> `phi4-mini:latest` on an Azure VM (`http://52.188.148.214:11434`), so the app's
> "Offline" toggle can route to it. Keep the toggle visible (build normally in
> step 4) and set the `OLLAMA_*` App Settings (step 6).
>
> ⚠️ **Two caveats.** (1) "Offline" is no longer *on-device / private* — the
> question and retrieved passages travel to the VM over **plain HTTP**. Reframe
> it in your report as *"a self-hosted open-source model on our own Azure VM"*,
> not "private, nothing leaves the device". (2) The VM's Ollama port is currently
> open to the whole internet with no auth — see the security note below.

---

## 0. Two things that will bite you if you skip them

1. **Pick App Service plan B2 (or bigger).** VeritasRAG loads two ML models in
   memory — MiniLM (embeddings) and the DeBERTa NLI verifier (the whole point of
   the project). B1/Free (1.75 GB) will crash with out-of-memory. **B2 = 3.5 GB**
   is the realistic minimum.
2. **Your secrets are in `.env` locally only.** Never commit `.env` or put keys
   in the deploy zip. On Azure they go in **App Settings** (step 6), which is the
   cloud equivalent of `.env`.

---

## 1. Get the connection details you don't have yet

**Azure AI Search admin key** (you gave me the endpoint but not the key):
Portal → your search service `hemanth-ai-search` → **Settings → Keys** →
copy the **Primary admin key**. Put it in `.env` as `AZURE_SEARCH_KEY=...`.

**Storage connection string** (already in your `.env`): Portal → storage account
`hemanthaistorage` → **Security + networking → Access keys** → *Connection string*.

**SQL** — server `hemanth-admin.database.windows.net`, database
`free-sql-db-1845311`, user `hemanth-admin`, and your password. Already assembled
into `AZURE_SQL_CONNECTION_STRING` in `.env`.

---

## 2. Open the SQL firewall (so the app can connect)

Portal → SQL server `hemanth-admin` → **Networking**:
- Turn ON **"Allow Azure services and resources to access this server"** (lets
  App Service reach it).
- To test from your laptop first, click **"Add your client IPv4 address"**.
- Save.

Azure SQL free tier is **serverless and auto-pauses** when idle — the first query
after a pause takes 30–60 s to wake. That's normal.

---

## 3. Validate the Azure services locally first (recommended)

You can prove each service works from your laptop before deploying. In `.env`:

```
STORAGE_BACKEND=azure_blob      # already verified working ✓
SEARCH_BACKEND=azure_search     # after you paste AZURE_SEARCH_KEY
DB_BACKEND=azure_sql            # needs an ODBC driver (below)
```

- **Blob**: already tested end-to-end — uploads land in your `documents` container.
- **AI Search**: paste the admin key, set `SEARCH_BACKEND=azure_search`, restart,
  upload a PDF, ask a question. The index `veritasrag-chunks` is created
  automatically on first use.
- **SQL**: install the **ODBC Driver 18 for SQL Server** (Windows: search
  "Microsoft ODBC Driver 18 for SQL Server", download, install), then set
  `DB_BACKEND=azure_sql` and restart. Tables are created automatically.

Run locally with:
```bash
cd multi-agent-rag
.venv\Scripts\python -m app.backend.main
```

---

## 4. Build the frontend

Because Offline works via your Ollama VM, build **normally** so both toggles work:
```bash
cd multi-agent-rag/app/frontend
npm run build
```
(Only if you ever want an online-only build with the Offline toggle hidden, set
`VITE_CLOUD_ONLY=1` before `npm run build`.)

---

## 5. Create the App Service (one-time)

Install the Azure CLI, then:
```bash
az login
az group create -n hemanth-ai-learning -l southindia   # reuse your RG/region

az appservice plan create -g hemanth-ai-learning -n veritas-plan --is-linux --sku B2

az webapp create -g hemanth-ai-learning -p veritas-plan -n veritasrag-hemanth \
  --runtime "PYTHON:3.11"
```
Your app URL will be `https://veritasrag-hemanth.azurewebsites.net` (the name
must be globally unique — change it if taken).

---

## 6. Set the App Settings (secrets + config)

Replace the placeholder values with the real ones from your `.env`:
```bash
az webapp config appsettings set -g hemanth-ai-learning -n veritasrag-hemanth --settings \
  APP_ENV=production \
  DATA_DIR=/home/data \
  JWT_SECRET="<paste a long random string>" \
  ANTHROPIC_API_KEY="<your sk-ant key>" \
  ANTHROPIC_MODEL=claude-sonnet-5 \
  STORAGE_BACKEND=azure_blob \
  AZURE_STORAGE_CONNECTION_STRING="<your storage connection string>" \
  AZURE_BLOB_CONTAINER=documents \
  SEARCH_BACKEND=azure_search \
  AZURE_SEARCH_ENDPOINT=https://hemanth-ai-search.search.windows.net \
  AZURE_SEARCH_KEY="<primary admin key>" \
  AZURE_SEARCH_INDEX=veritasrag-chunks \
  DB_BACKEND=azure_sql \
  AZURE_SQL_CONNECTION_STRING="Driver={ODBC Driver 18 for SQL Server};Server=tcp:hemanth-admin.database.windows.net,1433;Database=free-sql-db-1845311;Uid=hemanth-admin;Pwd=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;" \
  OLLAMA_HOST=http://52.188.148.214:11434 \
  OLLAMA_BASE_URL=http://52.188.148.214:11434 \
  OLLAMA_MODEL=phi4-mini:latest \
  SCM_DO_BUILD_DURING_DEPLOYMENT=1 \
  WEBSITES_CONTAINER_START_TIME_LIMIT=1800

# Startup command — bind the platform port; the app reads $PORT automatically.
az webapp config set -g hemanth-ai-learning -n veritasrag-hemanth \
  --startup-file "python -m app.backend.main"
```

- `DATA_DIR=/home/data` puts the (now small) writable data on Azure's persistent
  `/home` so it survives restarts and redeploys.
- `SCM_DO_BUILD_DURING_DEPLOYMENT=1` makes Azure run `pip install -r
  requirements.txt` during deploy.
- The ML models (~260 MB) download from Hugging Face on first startup into the
  `/home` cache; the first boot is slow, later ones are fast.

**ODBC driver note:** modern App Service Python images ship the Microsoft ODBC
Driver 18. If the logs show *"Can't open lib 'ODBC Driver 18 for SQL Server'"*,
change `Driver={ODBC Driver 18 for SQL Server}` to `Driver={ODBC Driver 17 for
SQL Server}` in the connection string.

---

## 7. Deploy the code

From the `multi-agent-rag` folder (with the cloud-only `dist/` built in step 4):
```bash
cd multi-agent-rag
az webapp up -g hemanth-ai-learning -n veritasrag-hemanth --runtime "PYTHON:3.11" --sku B2
```
Or zip-deploy: create a zip of the `multi-agent-rag` contents **excluding**
`.venv`, `data/`, `app/frontend/node_modules`, `app/frontend/src`, and `.env`,
then:
```bash
az webapp deploy -g hemanth-ai-learning -n veritasrag-hemanth --type zip --src-path deploy.zip
```

Watch the logs while it starts:
```bash
az webapp log tail -g hemanth-ai-learning -n veritasrag-hemanth
```

---

## 8. Verify

1. Open `https://veritasrag-hemanth.azurewebsites.net` → register an account.
2. Create a library, upload a PDF → confirm it appears in the Blob `documents`
   container (Portal → Storage browser).
3. Ask a question → you should get a verified answer with citations, and the
   Offline toggle should be gone.
4. Restart the app → your account and library are still there (SQL + Blob
   persistence working).

---

## 8a. Secure the Ollama VM (important)

Right now `http://52.188.148.214:11434` is open to the entire internet with no
authentication — anyone can run models on your VM (your compute, your bill) or
feed it prompts. Lock it down:

- Portal → the VM → **Networking / NSG** → the inbound rule for port **11434**:
  change **Source** from `Any` to the **App Service outbound IP addresses**
  (Portal → your web app → **Networking → Outbound addresses**). Add your own IP
  too if you want to test directly.
- The VM bills **hourly, 24/7** — more than the App Service. **Deallocate it**
  when you're not demoing: `az vm deallocate -g <rg> -n <vm>` (and start it again
  before a demo). phi4-mini on CPU is slow, so Offline answers will take a while.

## 9. Cost / housekeeping (free credits)

- Set a **budget alert**: Portal → Cost Management → Budgets.
- B2 App Service is the only real ongoing cost (~₹1/hr-ish on credits). **Stop
  the App Service** when you're not demoing: `az webapp stop -g hemanth-ai-learning -n veritasrag-hemanth`.
- AI Search free tier and SQL free tier don't bill, but stay within their limits
  (AI Search free = 3 indexes / 50 MB — plenty for a demo corpus).
- **Rotate the keys** you pasted into chat once the demo is done.
