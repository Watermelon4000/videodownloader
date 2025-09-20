const form = document.getElementById('download-form');
const taskBox = document.getElementById('task');
const taskIdEl = document.getElementById('task-id');
const taskStatusEl = document.getElementById('task-status');
const progressLabelEl = document.getElementById('progress-label');
const progressBarEl = document.getElementById('progress-bar');
const filesEl = document.getElementById('files');
const logEl = document.getElementById('log');
const openDirBtn = document.getElementById('open-dir-btn');
const dirFilesEl = document.getElementById('dir-files');

let pollTimer = null;

// Toggle custom format input visibility
const presetSel = document.getElementById('format_preset');
const customRow = document.getElementById('custom_format_row');
if (presetSel) {
  presetSel.addEventListener('change', () => {
    customRow.style.display = (presetSel.value === '__custom__') ? '' : 'none';
  });
}

if (openDirBtn) {
  openDirBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/open_downloads', { method: 'POST' });
      if (!res.ok) throw new Error('无法打开下载目录');
    } catch (e) {
      alert('打开下载目录失败');
    }
  });
}

// List existing files in download dir
async function refreshDirFiles() {
  try {
    const res = await fetch('/api/list_downloads');
    const data = await res.json();
    if (!res.ok) throw new Error('目录读取失败');
    if (!dirFilesEl) return;
    dirFilesEl.innerHTML = '';
    (data.files || []).forEach((it) => {
      const li = document.createElement('li');
      li.textContent = it.name; // show plain text only (no URL)
      dirFilesEl.appendChild(li);
    });
  } catch (e) {
    // ignore
  }
}
refreshDirFiles();

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearInterval(pollTimer);
  filesEl.innerHTML = '';
  if (progressLabelEl) progressLabelEl.textContent = '';
  if (progressBarEl) progressBarEl.style.width = '0%';
  logEl.textContent = '';

  const preset = document.getElementById('format_preset').value;
  const customFmt = document.getElementById('format').value;
  const chosenFmt = preset === '__custom__' ? customFmt : preset;

  const payload = {
    url: document.getElementById('url').value,
    audio_only: document.getElementById('audio_only').checked,
    format: chosenFmt,
    subtitles: document.getElementById('subtitles').checked,
    embed_thumbnail: document.getElementById('embed_thumbnail').checked,
    mp4_only: document.getElementById('mp4_only')?.checked || false,
  };

  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '启动下载失败');

    const taskId = data.task_id;
    taskIdEl.textContent = taskId;
    taskBox.classList.remove('hidden');
    taskStatusEl.textContent = 'running';

    pollTimer = setInterval(() => pollStatus(taskId), 1000);
  } catch (err) {
    alert(err.message);
  }
});

async function pollStatus(taskId) {
  try {
    const res = await fetch(`/api/status/${taskId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '查询状态失败');
    taskStatusEl.textContent = data.status;

    // Show last progress line
    if (data.last_progress) {
      const lp = data.last_progress;
      const pct = pctText(lp.downloaded_bytes, lp.total_bytes);
      const line = [
        lp.status,
        lp.filename ? `file: ${basename(lp.filename)}` : '',
        pct ? `progress: ${pct}` : '',
        lp.speed ? `speed: ${humanBytes(lp.speed)}/s` : '',
        lp.eta ? `eta: ${lp.eta}s` : '',
      ].filter(Boolean).join(' | ');
      if (progressLabelEl) progressLabelEl.textContent = line;
      if (progressBarEl) {
        const p = pctNumber(lp.downloaded_bytes, lp.total_bytes);
        if (p !== null) progressBarEl.style.width = `${p}%`;
      }
    }

    // Files
    filesEl.innerHTML = '';
    (data.files || []).forEach(f => {
      const li = document.createElement('li');
      // Download link
      const a = document.createElement('a');
      a.href = `/files/${encodeURIComponent(f)}`;
      a.textContent = f;
      a.download = f;
      li.appendChild(a);
      // Reveal button (opens folder in OS)
      const btn = document.createElement('button');
      btn.textContent = '在文件夹中显示';
      btn.style.marginLeft = '8px';
      btn.addEventListener('click', async (ev) => {
        ev.preventDefault();
        await fetch(`/api/reveal/${encodeURIComponent(f)}`, { method: 'POST' });
      });
      li.appendChild(btn);
      filesEl.appendChild(li);
    });

    // Logs
    logEl.textContent = (data.log || []).map(x => `[${x.ts}] ${x.level}: ${x.msg}`).join('\n');

    if (data.status === 'completed' || data.status === 'error') {
      // Ensure visual completion even if last progress lacked totals
      if (data.status === 'completed' && progressBarEl) {
        progressBarEl.style.width = '100%';
      }
      clearInterval(pollTimer);
      // Refresh directory list to include new outputs
      refreshDirFiles();
    }
  } catch (err) {
    console.error(err);
    clearInterval(pollTimer);
  }
}

function humanBytes(b) {
  if (!b && b !== 0) return '';
  const units = ['B','KB','MB','GB','TB'];
  let i = 0;
  let n = b;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(1)} ${units[i]}`;
}

function pctText(done, total) {
  if (!done || !total) return '';
  const pct = (done / total) * 100;
  return `${pct.toFixed(1)}%`;
}

function pctNumber(done, total) {
  if (!done || !total) return null;
  return Math.max(0, Math.min(100, (done / total) * 100));
}

function basename(p) {
  if (!p) return '';
  try { return decodeURIComponent(p.split(/[\\\/]/).pop()); } catch { return p; }
}
