 const API = 'http://127.0.0.1:5000';
  let currentColumns = [];

  // ─── NAVIGATION ───
  function showPanel(name) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('panel-' + name).classList.add('active');
    event.currentTarget.classList.add('active');
  }

  function loading(show) {
    document.getElementById('loadingOverlay').classList.toggle('show', show);
  }

  // ─── FILE UPLOAD ───
  function handleDrop(e) {
    e.preventDefault();
    document.getElementById('uploadZone').classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }

  async function handleFileUpload(file) {
    if (!file || (!file.name.endsWith('.csv') && !file.name.endsWith('.zip'))) {
      alert('Please upload a .csv or .zip file');
      return;
    }

    loading(true);
    const fd = new FormData();
    fd.append('file', file);

    try {
      const res = await fetch(`${API}/upload`, { method: 'POST', body: fd });
      const data = await res.json();

      if (data.error) { alert(data.error); return; }

      currentColumns = data.columns;
      updateColList(currentColumns);
      updateAllPanelCols(currentColumns);

      // Stats
      const stats = document.getElementById('uploadStats');
      stats.style.display = 'grid';
      stats.innerHTML = `
        <div class="stat-card"><div class="val" style="color:var(--accent)">${data.total_rows}</div><div class="label">Total Rows</div></div>
        <div class="stat-card"><div class="val" style="color:var(--accent2)">${data.total_cols}</div><div class="label">Columns</div></div>
        <div class="stat-card"><div class="val" style="color:var(--accent3)">${data.missing_info.length}</div><div class="label">Cols with Nulls</div></div>
        <div class="stat-card"><div class="val" style="color:var(--accent4)">${file.name}</div><div class="label">File Name</div></div>
      `;

      // Missing info pills
      if (data.missing_info.length > 0) {
        const pillBox = document.getElementById('uploadMissing');
        pillBox.style.display = 'block';
        pillBox.innerHTML = `<div style="font-size:12px; color:var(--muted); margin-bottom:8px;">Missing value summary:</div>
          <div class="missing-pills">
            ${data.missing_info.map(m => {
              const cls = m.missing_pct < 5 ? 'missing-low' : m.missing_pct <= 30 ? 'missing-mid' : 'missing-high';
              return `<span class="missing-pill ${cls}">${m.column}: ${m.missing_pct}%</span>`;
            }).join('')}
          </div>`;
      }

      // Table
      renderTable('uploadTable', data.full_data, 'Preview (first 20 rows)');

    } catch(e) {
      alert('Error connecting to server. Is Flask running on port 5000?');
    } finally {
      loading(false);
    }
  }

  // ─── MISSING VALUES ───
  async function handleMissing() {
    loading(true);
    try {
      const pref = document.getElementById('missingPref').value;
      const res = await fetch(`${API}/handle-missing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preference: pref })
      });
      const data = await res.json();
      if (data.error) { showResult('missingResult', false, data.error, []); return; }

      showResult('missingResult', true,
        `Done — ${data.shape[0]} rows × ${data.shape[1]} cols remaining`,
        data.changes
      );
      renderTable('missingTable', data.full_data, 'Result after handling missing values');
      autoDownload();
    } catch(e) { alert('Server error'); }
    finally { loading(false); }
  }

  // ─── DUPLICATES ───
  async function removeDuplicates() {
    loading(true);
    try {
      const res = await fetch(`${API}/remove-duplicates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (data.error) { showResult('dupResult', false, data.error, []); return; }

      showResult('dupResult', true,
        `Removed ${data.removed} duplicate rows. Dataset: ${data.shape[0]} × ${data.shape[1]}`,
        [`Duplicate rows removed: ${data.removed}`]
      );
      renderTable('dupTable', data.full_data, 'Result after removing duplicates');
      autoDownload();
    } catch(e) { alert('Server error'); }
    finally { loading(false); }
  }

  // ─── OUTLIERS ───
  async function removeOutliers() {
    const col = document.getElementById('outlierCol').value.trim();
    if (!col) { alert('Please enter a column name'); return; }
    loading(true);
    try {
      const res = await fetch(`${API}/remove-outliers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ column: col })
      });
      const data = await res.json();
      if (data.error) { showResult('outlierResult', false, data.error, []); return; }

      showResult('outlierResult', true,
        `Removed ${data.removed} outlier rows from '${data.column}'`,
        [
          `Q1: ${data.Q1}`, `Q3: ${data.Q3}`, `IQR: ${data.IQR}`,
          `Lower bound: ${data.lower_bound}`, `Upper bound: ${data.upper_bound}`,
          `Rows removed: ${data.removed}`, `Remaining: ${data.shape[0]} rows`
        ]
      );
      renderTable('outlierTable', data.full_data, `Result after outlier removal on '${col}'`);
      autoDownload();
    } catch(e) { alert('Server error'); }
    finally { loading(false); }
  }

  // ─── NORMALIZE ───
  async function normalizeColumn() {
    const col = document.getElementById('normCol').value.trim();
    if (!col) { alert('Please enter a column name'); return; }
    loading(true);
    try {
      const res = await fetch(`${API}/normalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ column: col })
      });
      const data = await res.json();
      if (data.error) { showResult('normResult', false, data.error, []); return; }

      showResult('normResult', true,
        `Min-Max normalization applied to '${data.column}'`,
        [
          `Original min: ${data.original_min}`,
          `Original max: ${data.original_max}`,
          `Column now scaled to [0, 1]`
        ]
      );
      renderTable('normTable', data.full_data, `Result after normalizing '${col}'`);
      autoDownload();
    } catch(e) { alert('Server error'); }
    finally { loading(false); }
  }

  // ─── PREPROCESS ALL ───
  async function preprocessAll() {
    loading(true);
    try {
      const pref = document.getElementById('allMissingPref').value;
      const outlierCols = [...document.querySelectorAll('#allOutlierCols input:checked')].map(c => c.value);
      const normCols = [...document.querySelectorAll('#allNormCols input:checked')].map(c => c.value);

      const res = await fetch(`${API}/preprocess-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preference: pref, outlier_columns: outlierCols, normalize_columns: normCols })
      });
      const data = await res.json();
      if (data.error) { showResult('allResult', false, data.error, []); return; }

      showResult('allResult', true,
        `Pipeline complete! Final dataset: ${data.shape[0]} rows × ${data.shape[1]} cols`,
        data.log
      );
      renderTable('allTable', data.full_data, 'Final preprocessed dataset');
      autoDownload();
    } catch(e) { alert('Server error'); }
    finally { loading(false); }
  }

  // ─── HELPERS ───
  function showResult(id, success, title, items) {
    const box = document.getElementById(id);
    box.className = `result-box show ${success ? 'success' : 'error'}`;
    box.innerHTML = `
      <div class="result-title">${success ? '✓' : '✗'} ${title}</div>
      ${items.length ? `<ul class="change-list">${items.map(i => `<li>${i}</li>`).join('')}</ul>` : ''}
    `;
  }

  function renderTable(containerId, tableData, title) {
    const container = document.getElementById(containerId);
    if (!tableData || !tableData.columns) return;

    const displayData = tableData.data.slice(0, 50);
    container.style.display = 'block';
    container.innerHTML = `
      <div class="table-header">
        <h3>${title}</h3>
        <span class="table-meta">Showing ${displayData.length} of ${tableData.shape[0]} rows · ${tableData.shape[1]} columns</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>${tableData.columns.map(c => `<th>${c}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${displayData.map(row =>
              `<tr>${row.map(cell =>
                cell === null || cell === undefined || cell === ''
                  ? `<td class="null-cell">null</td>`
                  : `<td>${typeof cell === 'number' ? (Number.isInteger(cell) ? cell : cell.toFixed(4)) : cell}</td>`
              ).join('')}</tr>`
            ).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  function updateColList(cols) {
    const dl = document.getElementById('colList');
    dl.innerHTML = cols.map(c => `<option value="${c}">`).join('');
  }

  function updateAllPanelCols(cols) {
    const numericHint = '(select numeric columns)';

    ['allOutlierCols', 'allNormCols'].forEach(id => {
      const container = document.getElementById(id);
      container.innerHTML = cols.map(col => `
        <label class="checkbox-item">
          <input type="checkbox" value="${col}"/>
          <span>${col}</span>
        </label>
      `).join('');
    });
  }

  async function autoDownload() {
    try {
      const res = await fetch(`${API}/download`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'preprocessed_data.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch(e) {
      console.error('Auto-download failed:', e);
    }
  }