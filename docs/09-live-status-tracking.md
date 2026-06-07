# 09 — Live Status Tracking Design

## Problem

After a student submits an order, they need **real-time visibility** into the pipeline:
- What stage is my order at?
- How much time is left to confirm?
- Did it succeed or expire?

## Solution: Polling + Cosmos DB Timeline

```
[Webapp] ──POST /api/submit_order──▶ [submit_order HTTP]
    ▲                                    │
    │  poll every 5s                     │ writes initial status doc
    │  GET /api/status?orderId=X         │ to Cosmos DB "OrderStatus"
    │                                    ▼
    │                         [Pipeline continues via Event Grid]
    │                                    │
    │                         Each activity writes status update
    │                         to same Cosmos DB document
    │
    └── GET /api/status?orderId=X ──▶ [get_order_status HTTP]
        (returns current status,       reads from Cosmos DB
         timeline, remaining seconds)   calculates countdown
```

## Status State Machine

```
submitted ──▶ validating ──▶ sms_sent ──▶ pending_confirmation
                                               │           │
                                          [confirm]    [timeout]
                                               │           │
                                           confirmed    expired
                                               │
                                           processing
                                               │
                                           completed
```

## Cosmos DB Status Document Shape

```json
{
    "id": "ORD-0042-a1b2c3d4",
    "orderId": "ORD-0042-a1b2c3d4",
    "displayId": 42,
    "displayOrder": "ORD-0042",
    "status": "pending_confirmation",
    "expiresAt": "2026-06-06T12:03:00Z",
    "lastUpdatedAt": "2026-06-06T12:00:05Z",
    "timeline": [
        {
            "status": "submitted",
            "timestamp": "2026-06-06T12:00:01Z",
            "details": "Order submitted via web form"
        },
        {
            "status": "validating",
            "timestamp": "2026-06-06T12:00:02Z",
            "details": "Order validation complete"
        },
        {
            "status": "sms_sent",
            "timestamp": "2026-06-06T12:00:05Z",
            "details": "SMS sent via ACS"
        },
        {
            "status": "pending_confirmation",
            "timestamp": "2026-06-06T12:00:05Z",
            "details": "Waiting for confirmation (expires at 2026-06-06T12:03:00Z)"
        }
    ]
}
```

## Status API Response (`GET /api/status?orderId=X`)

```json
{
    "orderId": "ORD-0042-a1b2c3d4",
    "displayId": 42,
    "displayOrder": "ORD-0042",
    "status": "pending_confirmation",
    "secondsRemaining": 137,
    "expiresAt": "2026-06-06T12:03:00Z",
    "lastUpdatedAt": "2026-06-06T12:00:05Z",
    "timeline": [
        {"status": "submitted", "timestamp": "12:00:01", "details": "..."},
        {"status": "validating", "timestamp": "12:00:02", "details": "..."},
        {"status": "sms_sent", "timestamp": "12:00:05", "details": "..."},
        {"status": "pending_confirmation", "timestamp": "12:00:05", "details": "..."}
    ]
}
```

## Webapp UI — Order Tracking Dashboard

### States and Rendering

| Status | Badge Color | Progress Bar | User Message |
|---|---|---|---|
| `submitted` | Blue | Indeterminate | ✅ Order received |
| `validating` | Blue | Indeterminate | 🔍 Validating order data... |
| `sms_sent` | Orange | 100% (waiting) | 📱 SMS sent! Check your phone |
| `pending_confirmation` | Orange | Countdown timer | ⏳ Waiting for confirmation... |
| `confirmed` | Green | 100% | ✅ Order confirmed! |
| `processing` | Green | Indeterminate | ⚙️ Processing your order... |
| `completed` | Green | 100% | 🎉 Done! Order completed |
| `expired` | Red | 100% (stuck) | ❌ Confirmation timeout — order NOT processed |

### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  📋 Order #ORD-0042                                 │
│                                                     │
│  Status: ⏳ Pending Confirmation                     │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  ████████████████████████░░░░░  76%         │    │
│  │  ⏱️  Time remaining:  2:17                  │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  Timeline:                                          │
│  ● ✅ 12:00:01 — Order received                     │
│  ● 🔍 12:00:02 — Payload validated                  │
│  ● 📱 12:00:05 — SMS sent                           │
│  ● ⏳ 12:00:05 — Awaiting confirmation...           │
│  ● ◯ — (next step)                                  │
│                                                     │
│  [✅ Confirm Order Now]                             │
│                                                     │
│  📱 Check your phone for the SMS confirmation link! │
└─────────────────────────────────────────────────────┘
```

## JavaScript Polling Logic

```javascript
// app.js — simplified
const POLL_INTERVAL_MS = 5000;
let pollInterval = null;

async function submitOrder(formData) {
    const response = await fetch('/api/submit_order', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData)
    });
    const data = await response.json();
    
    // Hide form, show dashboard
    document.getElementById('order-form-section').classList.add('hidden');
    document.getElementById('status-dashboard').classList.remove('hidden');
    
    // Start polling
    startPolling(data.orderId);
}

function startPolling(orderId) {
    // Initial fetch immediately
    fetchStatus(orderId);
    
    // Then every 5 seconds
    pollInterval = setInterval(() => fetchStatus(orderId), POLL_INTERVAL_MS);
}

async function fetchStatus(orderId) {
    const response = await fetch(`/api/status?orderId=${orderId}`);
    const data = await response.json();
    
    renderTimeline(data.timeline);
    renderStatusBadge(data.status);
    renderProgressBar(data.status, data.secondsRemaining);
    renderCountdown(data.secondsRemaining);
    
    // Stop polling on terminal states
    if (['completed', 'expired'].includes(data.status)) {
        stopPolling();
    }
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function renderTimeline(timeline) {
    const container = document.getElementById('timeline');
    container.innerHTML = timeline.map(entry => `
        <div class="timeline-entry status-${entry.status}">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
                <span class="timeline-time">${entry.timestamp}</span>
                <span class="timeline-status">${statusIcon(entry.status)} ${entry.details}</span>
            </div>
        </div>
    `).join('');
}

function renderCountdown(seconds) {
    if (seconds === null || seconds === undefined) {
        document.getElementById('countdown-timer').textContent = '—';
        return;
    }
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    document.getElementById('countdown-timer').textContent = 
        `${mins}:${secs.toString().padStart(2, '0')}`;
}

function statusIcon(status) {
    const icons = {
        submitted: '✅',
        validating: '🔍',
        sms_sent: '📱',
        pending_confirmation: '⏳',
        confirmed: '✅',
        processing: '⚙️',
        completed: '🎉',
        expired: '❌'
    };
    return icons[status] || '◯';
}
```

## Error Handling

| Scenario | Webapp Behavior |
|---|---|
| Network error (poll fails) | Show "Connection lost — retrying..." banner, continue polling |
| API returns 404 | Show "Order not found" — stop polling |
| API returns 500 | Show "Server error — retrying..." continue polling |
| Counter exhausted | Show service unavailable message on submit |
| Confirmation after expiry | API returns 410 Gone — show "Order already expired" |
| Duplicate confirmation | API returns 200 — idempotent, no error shown |

## Countdown Timer Math

```python
# Server-side in get_order_status
if doc.get("status") == "pending_confirmation" and doc.get("expiresAt"):
    try:
        expires = datetime.fromisoformat(doc["expiresAt"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        seconds_remaining = max(0, int((expires - now).total_seconds()))
    except:
        seconds_remaining = None
```

The `secondsRemaining` is calculated server-side (not client-side) to avoid clock drift issues.
