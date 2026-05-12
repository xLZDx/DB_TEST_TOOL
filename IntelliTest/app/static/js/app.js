// IntelliTest - shared JS utilities

// API helpers
const API = {
    async get(path) {
        const r = await fetch(path);
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
    },
    async post(path, body) {
        const r = await fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!r.ok) {
            const txt = await r.text();
            throw new Error(txt || `${r.status} ${r.statusText}`);
        }
        return r.json();
    },
    async delete(path) {
        const r = await fetch(path, { method: 'DELETE' });
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.ok;
    }
};

// Format ISO timestamp → readable date
function formatTimestamp(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return isNaN(d.getTime()) ? ts : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// Truncate string with ellipsis
function truncate(str, max = 80) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '…' : str;
}

// Build status badge HTML
function statusBadge(status) {
    const s = (status || '').toLowerCase();
    const cls = s.includes('done') || s.includes('closed') || s.includes('pass') ? 'badge-success' :
                s.includes('progress') ? 'badge-warning' : 'badge-info';
    return `<span class="badge ${cls}">${escH(status)}</span>`;
}
