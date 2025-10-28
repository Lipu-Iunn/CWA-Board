function parseNum(x) {
    const v = parseFloat(x);
    return Number.isFinite(v) ? v : null;
}

function fmtNum(x) {
    return x == null ? '—' : Number(x).toFixed(1);
}

function fieldsFor(tab) {
    switch (tab) {
        case 'avg-wind':
            return { sp: 'speed', dir: 'dir', t: 'time' };
        case 'gust':
            return { sp: 'gust_speed', dir: 'gust_dir', t: 'time' };
        default:
            return { sp: 'speed', dir: 'dir', t: 'time' };
    }
}

function sortRowsFor(tab, rows) {
    const { sp } = fieldsFor(tab);
    return rows.slice().sort((a, b) => {
        const av = parseNum(a[sp]);
        const bv = parseNum(b[sp]);
        if (av == null && bv == null) {
            return 0;
        } else if (av == null) {
            return 1;
        } else if (bv == null) {
            return -1;
        }
        return bv-av;
    });
}

function renderTable(tab) {
    const fs = fieldsFor(tab);
    const rows = sortRowsFor(tab, cache.rows);
    const tbody = document.querySelector('#board tbody');
    tbody.innerHTML = '';
    rows.forEach((r, i) => {
        const sp   = r[fs.sp];
        const dir  = r[fs.dir];
        const time = r[fs.t];
        const deg  = parseNum(dir);
        const toDeg = deg==null || deg===0 ? null : (deg+180)%360;   // 風的去向
        const arrowTd = toDeg == null
            ? '<td class="dir-arrow">—</td>'
            : `<td class="dir-arrow"><img src="/static/images/arrow.webp" alt="dir"
                style="transform:rotate(${toDeg}deg);" /></td>`;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${i+1}</td>
            <td>${r.name}</td>
            <td class="muted">${r.station_id}</td>
            <td>${fmtNum(sp)}</td>
            <td>${dir ?? '—'}</td>
            ${arrowTd}
            <td class="muted">${time ?? '—'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function labelOfWindow(w) {
    switch (w) {
        case 'now':
            return '現在';
        case '1h':
            return '過去 1 小時';
        case '24h':
            return '過去 24 小時';
        case 'today':
            return '今日';
        default:
            return '現在';
    }
}

async function fetchAndRender() {
    const params = new URLSearchParams({ window: currentWindow, tab: currentTab });
    const res = await fetch('/api/data?' + params.toString(), { cache: 'no-store' });
    const data = await res.json();
    cache.rows = data.rows || [];
    const el = document.getElementById('updatedAt');
    if (el) el.textContent = data.updated_at || '尚未更新';
    renderTable(currentTab);
}
