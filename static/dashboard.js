// ===== Search / Filter =====
function initTableSearch(inputId, tableId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.addEventListener('input', () => {
        const q = input.value.toLowerCase();
        const rows = document.querySelectorAll(`#${tableId} tbody tr`);
        rows.forEach(row => {
            row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
    });
}

// ===== Filter Buttons =====
function initFilterButtons(containerSelector, tableId, columnIndex) {
    const btns = document.querySelectorAll(containerSelector + ' .filter-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const val = btn.dataset.filter;
            const rows = document.querySelectorAll(`#${tableId} tbody tr`);
            rows.forEach(row => {
                if (val === 'all') {
                    row.style.display = '';
                } else {
                    const cell = row.children[columnIndex];
                    const text = cell ? cell.textContent.trim().toLowerCase() : '';
                    row.style.display = text.includes(val.toLowerCase()) ? '' : 'none';
                }
            });
        });
    });
}

// ===== Expand / Collapse =====
function toggleExpand(id) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('open');
}

// ===== Toast =====
function showToast(message, type) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== Settings Save =====
async function saveSettings(formId, endpoint) {
    const form = document.getElementById(formId);
    if (!form) return;
    const data = {};
    const inputs = form.querySelectorAll('input, select');
    inputs.forEach(input => {
        if (input.type === 'checkbox') {
            data[input.name] = input.checked;
        } else {
            data[input.name] = input.value;
        }
    });

    try {
        const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await resp.json();
        if (result.success) {
            showToast('Settings saved successfully!', 'success');
        } else {
            showToast(result.error || 'Failed to save settings.', 'error');
        }
    } catch (err) {
        showToast('Network error. Could not save.', 'error');
    }
}

// ===== Init on page load =====
document.addEventListener('DOMContentLoaded', () => {
    // Auto-init search if elements exist
    initTableSearch('table-search', 'data-table');
    initFilterButtons('.filter-bar', 'data-table', 4);
});
