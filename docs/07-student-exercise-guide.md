# 07 — Student Exercise Guide

## Classroom Exercise: Event-Driven Order Processing Pipeline

**Duration**: ~3-4 hours  
**Prerequisites**: Azure for Students subscription, Python basics, Git basics  
**Skills Learned**:
- Azure Functions (HTTP, Event Grid, Durable Functions)
- Cosmos DB with optimistic concurrency (ETag CAS)
- Event Grid + Event-Driven Architecture
- Azure Communication Services SMS
- Managed Identity + RBAC
- Bicep Infrastructure as Code
- CI/CD with GitHub Actions

---

## Part 1: Setup (30 min)

### Step 1.1: Prerequisites
- [ ] Azure for Students subscription activated
- [ ] Python 3.11+ installed
- [ ] VS Code with Azure Functions extension
- [ ] Azure Functions Core Tools v4
- [ ] Azurite (Storage Emulator): `npm install -g azurite`
- [ ] Cosmos DB Emulator (optional for local dev)
- [ ] Git installed

### Step 1.2: Clone repository
```bash
git clone <repo-url> Exercise-Event-Chain-Output-bind
cd Exercise-Event-Chain-Output-bind
```

### Step 1.3: Set up virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Step 1.4: Verify setup
```bash
func --version
azurite --version
python --version
```

---

## Part 2: Explore the Architecture (30 min)

### Step 2.1: Read the docs
- Open `docs/01-architecture-overview.md` and study the Mermaid diagram
- Open `PLAN.md` for the master overview

### Step 2.2: Walk the code
- `src/models.py` — What Pydantic models exist?
- `src/counter.py` — How does the CAS counter work?
- `src/orchestrator.py` — What are the two paths?
- `src/activities.py` — List all 7 activities
- `src/function_app.py` — What triggers exist?

### Step 2.3: Answer comprehension questions
1. Why must the DF orchestrator be deterministic?
2. How does the counter prevent race conditions?
3. What happens if the customer confirms after 3 minutes?
4. Why use Managed Identity instead of connection strings?
5. What triggers the `order_validator` function?

---

## Part 3: Run Locally with Emulators (45 min)

### Step 3.1: Start emulators
```bash
# Terminal 1: Azurite
azurite --silent --location ./azurite-data

# Terminal 2: Cosmos DB Emulator (if installed)
# Or skip — the counter will retry on CosmosResourceNotFoundError
```

### Step 3.2: Start Functions host
```bash
func start
```

### Step 3.3: Submit an order
```bash
curl -X POST http://localhost:7071/api/submit_order \
  -H "Content-Type: application/json" \
  -d '{
    "customerName": "Maria Silva",
    "customerPhone": "+351911234567",
    "items": [
      {"itemId": "ITM-001", "name": "Widget", "quantity": 2, "unitPrice": 15.50}
    ],
    "total": 31.00,
    "tax": 7.13,
    "notes": "Ring doorbell"
  }'
```

Expected response (202):
```json
{
  "orderId": "ORD-0001-abc123",
  "displayId": 1,
  "displayOrder": "ORD-0001",
  "status": "submitted"
}
```

### Step 3.4: Check the pipeline
```bash
# Poll status (replace orderId with your actual)
curl "http://localhost:7071/api/status?orderId=ORD-0001-abc123"

# Check Azurite blob (Azurite Explorer)
# Check function logs in terminal
```

### Step 3.5: Confirm the order
```bash
curl -X POST "http://localhost:7071/api/confirm_handler?instance_id=ORD-0001-abc123"
```

Expected response (200):
```json
{
  "status": "confirmed",
  "orderId": "ORD-0001-abc123"
}
```

### Step 3.6: Verify confirmed order
```bash
# Poll again — status should be "completed"
curl "http://localhost:7071/api/status?orderId=ORD-0001-abc123"
```

### Step 3.7: Test expired flow
- Submit another order
- **Do NOT confirm**
- Wait 3 minutes (or reduce `CONFIRMATION_TIMEOUT_SECONDS` to 10s in `local.settings.json`)
- Poll status — should show "expired"
- Check `ExpiredOrders` table in Azurite

---

## Part 4: Deploy to Azure (45 min)

### Step 4.1: Login to Azure CLI
```bash
az login
az account set --subscription "<your-subscription-id>"
```

### Step 4.2: Create service principal (for GitHub Actions)
```bash
az ad sp create-for-rbac --name "sp-order-processing" --role Contributor \
  --scopes /subscriptions/<subscription-id> \
  --sdk-auth
```
Save the JSON output — you'll add it as a GitHub secret.

### Step 4.3: Set up GitHub secrets
In your GitHub repo → Settings → Secrets and variables → Actions:
- `AZURE_CLIENT_ID` (from SP JSON)
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

### Step 4.4: Deploy with Bicep (or GitHub Actions)
```bash
# Create resource group
az group create --name rg-orderprocessing-001 --location westeurope

# Deploy Bicep
az deployment group create \
  --resource-group rg-orderprocessing-001 \
  --template-file infra/main.bicep \
  --parameters suffix=001 location=westeurope
```

### Step 4.5: Deploy function code
```bash
func azure functionapp publish func-order-001 --python
```

### Step 4.6: Deploy webapp
```bash
az storage blob upload-batch \
  --account-name storder001 \
  --auth-mode login \
  --destination '$web' \
  --source webapp/
```

### Step 4.7: Test live endpoint
```bash
curl -X POST "https://func-order-001.azurewebsites.net/api/submit_order" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

---

## Part 5: Extension Exercises (60 min)

### Choose ONE option:

#### Option A: Add Email Notification
Add an `send_email` activity that sends confirmation via Azure Communication Email.
- **New**: activity function, ACS Email setup
- **Modified**: `orchestrator.py` (add activity call), Bicep (ACS config)
- **Teaches**: Multi-channel notifications, parallel activities

#### Option B: Add Order Cancellation
Add a second external event ("Cancelled") that customers can trigger before confirmation.
- **New**: `task_any` with 3 tasks (timer, confirm, cancel)
- **Modified**: `orchestrator.py`, `confirm_handler` → `cancel_handler`
- **Teaches**: Multiple external events, more complex state machine

#### Option C: Admin Dashboard
Create a TimerTrigger (runs daily) that generates an order summary report.
- **New**: `admin_summary` TimerTrigger function
- **Storage**: Writes summary JSON to a `reports` blob container
- **Teaches**: TimerTrigger, aggregation queries, scheduled jobs

#### Option D: Add Authentication
Protect HTTP endpoints with function keys or Entra ID authentication.
- **Modified**: `auth_level` in HTTP triggers, CORS configuration
- **Teaches**: Security, function keys, authentication middleware

---

## Part 6: Clean Up (10 min)

```bash
# Delete resource group — removes ALL resources
az group delete --name rg-orderprocessing-001 --yes --no-wait

# Verify deletion
az group list --query "[?name=='rg-orderprocessing-001']"

# Document what you learned (reflection)
```

## Grading Rubric

| Criteria | Points | Description |
|---|---|---|
| Part 2 — Comprehension | 20 | Correct answers to architecture questions |
| Part 3 — Local run | 30 | Successfully ran pipeline locally (confirmed + expired) |
| Part 4 — Deploy | 25 | Successfully deployed to Azure, tested live endpoint |
| Part 5 — Extension | 20 | Working extension feature with explanation |
| Part 6 — Cleanup | 5 | Resources deleted, reflection submitted |
| **Total** | **100** | |

## Reflection Questions (submit with cleanup)

1. What was the most challenging part of this exercise?
2. How does Durable Functions differ from a simple queue-based workflow?
3. Why is optimistic concurrency necessary for the counter? What would break with `counter += 1`?
4. How would you scale this pipeline for production (1000x more orders)?
5. What other real-world scenarios could use this human-in-the-loop pattern?
