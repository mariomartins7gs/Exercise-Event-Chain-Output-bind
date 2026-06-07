const STATUS_LABELS = {
  submitted: 'Inviato',
  validating: 'Validazione...',
  sms_sent: 'SMS Inviato',
  pending_confirmation: 'In attesa di conferma',
  confirmed: 'Confermato!',
  processing: 'Elaborazione...',
  completed: 'Completato',
  expired: 'Scaduto',
};

const STATUS_PROGRESS = {
  submitted: 5,
  validating: 15,
  sms_sent: 30,
  pending_confirmation: 50,
  confirmed: 65,
  processing: 80,
  completed: 100,
  expired: 100,
};

const STATUS_ORDER = [
  'submitted', 'validating', 'sms_sent', 'pending_confirmation',
  'confirmed', 'processing', 'completed', 'expired',
];

let pollTimer = null;
let localCountdown = null;
let currentStatus = null;
let localSeconds = 0;

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('order-form');
  form.addEventListener('submit', onFormSubmit);

  document.getElementById('add-item').addEventListener('click', addItemRow);
  document.getElementById('btn-confirm').addEventListener('click', onConfirm);
  document.getElementById('btn-new-order').addEventListener('click', resetToForm);
});

function addItemRow() {
  const container = document.getElementById('items-container');
  const row = document.createElement('div');
  row.className = 'item-row';
  row.innerHTML = `
    <input type="text" class="item-id" placeholder="Codice" required>
    <input type="text" class="item-name" placeholder="Nome articolo" required>
    <input type="number" class="item-qty" placeholder="Qt" min="1" max="999" required>
    <input type="number" class="item-price" placeholder="Prezzo" min="0" step="0.01" required>
    <button type="button" class="btn-remove-item" title="Rimuovi">&times;</button>
  `;
  row.querySelector('.btn-remove-item').addEventListener('click', () => {
    row.remove();
  });
  container.appendChild(row);
}

function collectFormData() {
  const items = [];
  document.querySelectorAll('.item-row').forEach(row => {
    const id = row.querySelector('.item-id').value.trim();
    const name = row.querySelector('.item-name').value.trim();
    const qty = parseInt(row.querySelector('.item-qty').value, 10);
    const price = parseFloat(row.querySelector('.item-price').value);
    if (name && !isNaN(qty) && !isNaN(price)) {
      items.push({ itemId: id || `ITM-${Date.now()}`, name, quantity: qty, unitPrice: price });
    }
  });

  return {
    customerName: document.getElementById('customerName').value.trim(),
    customerPhone: document.getElementById('customerPhone').value.trim(),
    items,
    total: parseFloat(document.getElementById('total').value),
    tax: parseFloat(document.getElementById('tax').value),
    notes: document.getElementById('notes').value.trim() || undefined,
  };
}

function showError(msg) {
  const el = document.getElementById('form-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideError() {
  document.getElementById('form-error').classList.add('hidden');
}

async function onFormSubmit(e) {
  e.preventDefault();
  hideError();

  const data = collectFormData();

  if (!data.customerName || !data.customerPhone || data.items.length === 0) {
    showError('Compila tutti i campi obbligatori.');
    return;
  }

  if (isNaN(data.total) || isNaN(data.tax)) {
    showError('Inserisci totale e IVA.');
    return;
  }

  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.textContent = 'Invio in corso...';

  try {
    const resp = await fetch('/api/submit_order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || `Errore ${resp.status}`);
    }

    const result = await resp.json();
    startDashboard(result);
  } catch (err) {
    showError(err.message || 'Errore di connessione. Riprova.');
    btn.disabled = false;
    btn.textContent = 'Invia Ordine';
  }
}

function startDashboard(result) {
  document.getElementById('form-section').classList.add('hidden');
  document.getElementById('dashboard-section').classList.remove('hidden');
  document.getElementById('footer-status').textContent = 'Ordine: ' + result.displayOrder;

  document.getElementById('dash-order-label').textContent =
    `${result.displayOrder} — ID: ${result.orderId.slice(0, 20)}...`;

  currentStatus = result.status;
  renderStatus(result);

  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => pollStatus(result.orderId), 5000);
  pollStatus(result.orderId);
}

async function pollStatus(orderId) {
  try {
    const resp = await fetch(`/api/status?orderId=${encodeURIComponent(orderId)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    currentStatus = data.status;

    if (data.status === 'pending_confirmation' && data.secondsRemaining != null) {
      localSeconds = data.secondsRemaining;
      if (!localCountdown) startLocalCountdown();
    } else {
      stopLocalCountdown();
    }

    renderStatus(data);

    if (data.status === 'completed' || data.status === 'expired') {
      stopPolling();
    }
  } catch {
    // silent — next poll will retry
  }
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  stopLocalCountdown();
  document.getElementById('btn-new-order').classList.remove('hidden');
}

function startLocalCountdown() {
  stopLocalCountdown();
  localCountdown = setInterval(() => {
    localSeconds = Math.max(0, localSeconds - 1);
    updateTimerDisplay(localSeconds);
  }, 1000);
}

function stopLocalCountdown() {
  if (localCountdown) { clearInterval(localCountdown); localCountdown = null; }
}

function renderStatus(data) {
  const badge = document.getElementById('dash-status-badge');
  badge.textContent = STATUS_LABELS[data.status] || data.status;
  badge.className = 'status-badge status-' + data.status;

  const timerEl = document.getElementById('dash-timer');
  if (data.status === 'pending_confirmation' && data.secondsRemaining != null) {
    timerEl.classList.remove('hidden');
    updateTimerDisplay(data.secondsRemaining);
  } else {
    timerEl.classList.add('hidden');
  }

  const progress = document.getElementById('dash-progress');
  const fill = progress.querySelector('.progress-fill');
  const pct = STATUS_PROGRESS[data.status] || 0;
  fill.style.width = pct + '%';
  if (data.status === 'expired') {
    fill.style.background = 'var(--red)';
  } else {
    fill.style.background = 'var(--azure)';
  }

  renderStepper(data.timeline || [], data.status);

  const confirmBtn = document.getElementById('btn-confirm');
  if (data.status === 'pending_confirmation') {
    confirmBtn.classList.remove('hidden');
    confirmBtn.dataset.instanceId = data.orderId;
  } else {
    confirmBtn.classList.add('hidden');
  }
}

function updateTimerDisplay(seconds) {
  const el = document.getElementById('dash-timer');
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
  el.classList.toggle('urgent', seconds <= 30);
}

function renderStepper(timeline, current) {
  const stepper = document.getElementById('dash-stepper');
  stepper.innerHTML = '';

  const statuses = STATUS_ORDER.slice(0, STATUS_ORDER.indexOf('expired') + 1);
  const currentIdx = statuses.indexOf(current);
  const timelineMap = {};
  (timeline || []).forEach(t => { timelineMap[t.status] = t; });

  statuses.forEach((s, i) => {
    if (s === 'expired' && current !== 'expired') return;

    const li = document.createElement('li');
    const entry = timelineMap[s];

    if (entry) {
      li.className = 'done';
      const time = new Date(entry.timestamp).toLocaleTimeString('it-IT', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
      li.textContent = `${STATUS_LABELS[s]} — ${time}`;
    } else if (i === currentIdx) {
      li.className = 'active';
      li.textContent = STATUS_LABELS[s] + '...';
    } else if (i < currentIdx && !entry) {
      li.className = 'done';
      li.textContent = STATUS_LABELS[s];
    } else {
      li.textContent = STATUS_LABELS[s];
    }

    if (current === 'expired' && s === 'expired') {
      li.className = 'error';
    }

    stepper.appendChild(li);
  });
}

async function onConfirm() {
  const btn = document.getElementById('btn-confirm');
  const instanceId = btn.dataset.instanceId;
  if (!instanceId) return;

  btn.disabled = true;
  btn.textContent = 'Conferma in corso...';

  try {
    const resp = await fetch('/api/confirm_handler', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instance_id: instanceId }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      btn.disabled = false;
      btn.textContent = 'Conferma Ordine';
      showError(text || `Errore ${resp.status}`);
      return;
    }

    btn.textContent = '✅ Ordine Confermato!';
    btn.style.background = 'var(--green)';
    btn.disabled = true;
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Conferma Ordine';
    showError(err.message || 'Errore di connessione.');
  }
}

function resetToForm() {
  document.getElementById('dashboard-section').classList.add('hidden');
  document.getElementById('form-section').classList.remove('hidden');
  document.getElementById('btn-new-order').classList.add('hidden');
  document.getElementById('footer-status').textContent = 'Pronto';

  const btn = document.getElementById('btn-submit');
  btn.disabled = false;
  btn.textContent = 'Invia Ordine';

  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  stopLocalCountdown();
  currentStatus = null;
}
