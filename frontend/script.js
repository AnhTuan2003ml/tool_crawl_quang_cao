const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const backendRunBtn = document.getElementById('backendRunBtn');
const runMinutesInput = document.getElementById('runMinutes');
const intervalInput = document.getElementById('interval');
const tbody = document.querySelector('#listTable tbody');
const emptyState = document.getElementById('emptyState');
const rowCount = document.getElementById('rowCount');
const statusDot = document.getElementById('statusDot');
const backendStatus = document.getElementById('backendStatus');

const API_BASE = 'http://localhost:8000';

let counter = 1;
let timerId = null;
let initialLoaded = false;

stopBtn.disabled = true;

function updateRowCount() {
  const count = tbody.children.length;
  rowCount.textContent = count;
}

function setScanning(isOn) {
  startBtn.disabled = isOn;
  const startBtnText = startBtn.querySelector('span:last-child');
  startBtnText.textContent = isOn ? 'Đang quét...' : 'Bắt đầu quét';
  stopBtn.disabled = !isOn;
  backendRunBtn.disabled = isOn;
}

function appendRow({ id, type, time }) {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${id}</td><td>${type}</td><td>${time}</td>`;
  tr.style.opacity = '0';
  tr.style.transform = 'translateY(-10px)';
  tbody.appendChild(tr);

  // Animation
  setTimeout(() => {
    tr.style.transition = 'all 0.3s ease';
    tr.style.opacity = '1';
    tr.style.transform = 'translateY(0)';
  }, 10);

  emptyState.classList.remove('show');
  updateRowCount();
}

function addGeneratedRow() {
  appendRow({
    id: counter++,
    type: 'scan',
    time: new Date().toLocaleTimeString('vi-VN'),
  });
}

async function loadInitialData() {
  if (initialLoaded) return;
  try {
    const res = await fetch('data.json');
    if (!res.ok) throw new Error('Fetch failed');
    const rows = await res.json();
    rows.forEach((row) => {
      appendRow(row);
      counter = Math.max(counter, Number(row.id) + 1);
    });
    initialLoaded = true;
  } catch (err) {
    console.error('Không tải được data.json', err);
  }

  // Show empty state if no rows
  if (tbody.children.length === 0) {
    emptyState.classList.add('show');
  }
}

startBtn.addEventListener(
  'click',
  async () => {
    await loadInitialData();
    const started = await triggerBackendRun();
    if (!started) {
      return;
    }
    addGeneratedRow();
    const minutes = Number(intervalInput.value) || 1;
    timerId = setInterval(addGeneratedRow, minutes * 60 * 1000);
    setScanning(true);
  }
);

stopBtn.addEventListener('click', () => {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
  setScanning(false);
  sendStopSignal();
});

// Xuất file Excel
const exportExcelBtn = document.getElementById('exportExcelBtn');

function exportToExcel() {
  const table = document.getElementById('listTable');
  const rows = table.querySelectorAll('tr');

  if (rows.length <= 1) {
    alert('Không có dữ liệu để xuất!');
    return;
  }

  // Tạo dữ liệu cho Excel
  const data = [];

  // Thêm header
  const headerRow = [];
  table.querySelectorAll('thead th').forEach(th => {
    headerRow.push(th.textContent);
  });
  data.push(headerRow);

  // Thêm dữ liệu
  table.querySelectorAll('tbody tr').forEach(tr => {
    const row = [];
    tr.querySelectorAll('td').forEach(td => {
      row.push(td.textContent);
    });
    data.push(row);
  });

  // Tạo workbook và worksheet
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(data);

  // Đặt độ rộng cột
  ws['!cols'] = [
    { wch: 10 }, // ID
    { wch: 15 }, // Type
    { wch: 20 }  // Time
  ];

  // Thêm worksheet vào workbook
  XLSX.utils.book_append_sheet(wb, ws, 'Danh sách quét');

  // Tạo tên file với timestamp
  const now = new Date();
  const timestamp = now.toISOString().slice(0, 19).replace(/:/g, '-');
  const filename = `danh_sach_quet_${timestamp}.xlsx`;

  // Xuất file
  XLSX.writeFile(wb, filename);

  // Hiển thị thông báo
  const btnText = exportExcelBtn.querySelector('span:last-child');
  const originalText = btnText.textContent;
  btnText.textContent = 'Đã xuất!';
  exportExcelBtn.disabled = true;

  setTimeout(() => {
    btnText.textContent = originalText;
    exportExcelBtn.disabled = false;
  }, 2000);
}

exportExcelBtn.addEventListener('click', exportToExcel);

// ==== FastAPI integration ====

function setBackendStatus(message, isOnline = false) {
  backendStatus.textContent = message;
  statusDot.classList.toggle('online', isOnline);
}

async function callBackend(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    // ignore parse errors, will throw below if not ok
  }

  if (!res.ok) {
    const detail = data.detail || res.statusText || 'Request failed';
    throw new Error(detail);
  }

  return data;
}

async function triggerBackendRun() {
  setBackendStatus('Đang gửi lệnh chạy...', false);
  backendRunBtn.disabled = true;
  try {
    const runMinutes = Number(runMinutesInput.value);
    // Dùng luôn "Thời gian lặp lại (phút)" làm thời gian nghỉ giữa phiên
    const restMinutes = Number(intervalInput.value);
    const payload = {};
    if (Number.isFinite(runMinutes) && runMinutes > 0) {
      payload.run_minutes = runMinutes;
    }
    if (Number.isFinite(restMinutes) && restMinutes > 0) {
      payload.rest_minutes = restMinutes;
    }

    const data = await callBackend('/run', {
      body: JSON.stringify(payload),
    });
    const pidText = data.pid ? ` (PID ${data.pid})` : '';
    setBackendStatus(`Đã kích hoạt backend${pidText}`, true);
    return true;
  } catch (err) {
    console.error(err);
    alert('Không gọi được backend. Hãy kiểm tra FastAPI đã chạy chưa.');
    setBackendStatus('Backend lỗi hoặc chưa khởi động', false);
    return false;
  } finally {
    backendRunBtn.disabled = false;
  }
}

async function sendStopSignal() {
  try {
    await callBackend('/stop');
    setBackendStatus('Đã gửi lệnh dừng backend', false);
  } catch (err) {
    console.warn('Không dừng được backend:', err);
    setBackendStatus('Backend có thể vẫn đang chạy', false);
  }
}

backendRunBtn.addEventListener('click', triggerBackendRun);

// Thử kiểm tra trạng thái backend khi tải trang
fetch(`${API_BASE}/status`)
  .then((res) => res.json())
  .then((data) => {
    const running = Boolean(data.running);
    setBackendStatus(running ? 'Backend đang chạy' : 'Backend chưa chạy', running);
  })
  .catch(() => {
    setBackendStatus('Không kết nối được FastAPI', false);
  });