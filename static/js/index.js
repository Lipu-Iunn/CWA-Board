let CURRENT_GROUP = "全部";         // 目前選擇的群組（工作表種類）
let AVAILABLE_GROUPS = ["全部"];    // 從後端取得的所有群組名稱（含「全部」）
let LAST_DATA = null;               // 暫存最後一次 /api/data 回傳結果，方便切換群組時重新渲染


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

function renderTableWithGroupFilter(tab) {
    const fs = fieldsFor(tab);
    const rows = sortRowsFor(tab, filterRowsByGroup(LAST_DATA));
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
    const res = await fetch(`/api/data?${params.toString()}`, { cache: 'no-store' });
    const data = await res.json();
    LAST_DATA = data.rows;
    const el = document.getElementById('updatedAt');
    if (el) el.textContent = data.updated_at || '尚未更新';

    if (data.groups && Array.isArray(data.groups)) {
        // CURRENT_GROUP 若尚未設定，就預設 "全部"
        if (!CURRENT_GROUP) {
            CURRENT_GROUP = "全部";
        }
        buildGroupFilter(data.groups);
    }
    
    renderTableWithGroupFilter(currentTab);
}

function buildGroupFilter(groups) {
  // groups: ["全部", "茶葉產區", "咖啡產區", ...]
  AVAILABLE_GROUPS = groups.slice();
  if (!AVAILABLE_GROUPS.includes("全部")) {
    AVAILABLE_GROUPS.unshift("全部");
  }

  const container = document.getElementById("group-filter");
  if (!container) return;

  container.innerHTML = "";

  AVAILABLE_GROUPS.forEach((g) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = g;
    btn.dataset.group = g;
    btn.className = "group-btn";
    if (g === CURRENT_GROUP) {
      btn.classList.add("active");
    }

    btn.addEventListener("click", () => {
      CURRENT_GROUP = g;

      // 更新 active 樣式
      container.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("active", b.dataset.group === CURRENT_GROUP);
      });

      // 只改變前端篩選，不重打 API
      if (LAST_DATA) {
        renderTableWithGroupFilter(LAST_DATA);
      }
    });

    container.appendChild(btn);
  });
}

function filterRowsByGroup(rows) {
  if (!CURRENT_GROUP || CURRENT_GROUP === "全部") {
    return rows;
  }
  return rows.filter((row) => {
    const gs = row.groups || row.group || []; // 保險起見多幾種欄位名
    if (Array.isArray(gs)) {
      return gs.includes(CURRENT_GROUP);
    }
    // 如果後端未來改成單一字串也能相容
    if (typeof gs === "string") {
      return gs === CURRENT_GROUP;
    }
    return false;
  });
}
