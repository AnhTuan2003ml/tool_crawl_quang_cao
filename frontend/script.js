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
// Tabs & view cho danh sách quét / quản lý post
const tabScanList = document.getElementById('tabScanList');
const tabPostManager = document.getElementById('tabPostManager');
const scanView = document.getElementById('scanView');
const postView = document.getElementById('postView');
// Bảng quản lý post
const postTableBody = document.querySelector('#postTable tbody');
const postEmptyState = document.getElementById('postEmptyState');

const API_BASE = 'http://localhost:8000';

let counter = 1;
let timerId = null;
let initialLoaded = false;
let dataCheckInterval = null; // Interval để kiểm tra dữ liệu mới
let loadedPostIds = new Set(); // Lưu các post_id đã load để tránh trùng lặp
let postsLoaded = false; // Đã load dữ liệu quản lý post hay chưa

stopBtn.disabled = true;

function updateRowCount() {
  const count = tbody.children.length;
  rowCount.textContent = count;
}

// Load dữ liệu quản lý post từ file post_ids
async function loadPostsForManager() {
  if (postsLoaded || !postTableBody) return;
  try {
    const res = await fetch('../backend/data/post_ids/031ca13d-e8fa-400c-a603-df57a2806788.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) {
      postEmptyState && postEmptyState.classList.add('show');
      postsLoaded = true;
      return;
    }

    data.forEach((post) => appendPostRow(post));
    postEmptyState && postEmptyState.classList.remove('show');
    postsLoaded = true;
  } catch (err) {
    console.error('Không tải được dữ liệu post_ids:', err);
    postEmptyState && postEmptyState.classList.add('show');
  }
}

function setScanning(isOn) {
  startBtn.disabled = isOn;
  const startBtnText = startBtn.querySelector('span:last-child');
  startBtnText.textContent = isOn ? 'Đang quét...' : 'Bắt đầu quét';
  stopBtn.disabled = !isOn;
  backendRunBtn.disabled = isOn;
}

function getTypeColorClass(type) {
  const typeLower = String(type).toLowerCase().trim();
  
  // Xanh cho: scan, success, ok, completed
  if (typeLower === 'type1' || typeLower === 'success' || typeLower === 'ok' || typeLower === 'completed') {
    return 'type-green';
  }
  
  // Vàng cho: retry, warning, pending, processing
  if (typeLower === 'type2' || typeLower === 'warning' || typeLower === 'pending' || typeLower === 'processing') {
    return 'type-yellow';
  }
  
  // Đỏ cho: error, fail, failed, cancel
  if (typeLower === 'type3' || typeLower === 'fail' || typeLower === 'failed' || typeLower === 'cancel') {
    return 'type-red';
  }
  
  // Mặc định: xanh
  return 'type-green';
}

// Map flag -> type cho quản lý post
function mapFlagToType(flag) {
  const f = String(flag || '').toLowerCase();
  if (f === 'xanh') return 'type1';
  if (f === 'vàng' || f === 'vang') return 'type2';
  if (f === 'đỏ' || f === 'do') return 'type3';
  return 'type1';
}

function appendRow({ id, userId, name, react, comment, time, type }) {
  const tr = document.createElement('tr');
  const typeColorClass = getTypeColorClass(type);
  // React: hiển thị dấu tích nếu có, không thì để trống
  const reactDisplay = react ? '✓' : '';
  // Link cho ID Bài Post và ID User
  const postIdDisplay = id
    ? `<a href="https://fb.com/${id}" target="_blank" rel="noopener noreferrer" class="id-link">${id}</a>`
    : '';
  const userIdDisplay = userId
    ? `<a href="https://fb.com/${userId}" target="_blank" rel="noopener noreferrer" class="id-link">${userId}</a>`
    : '';
  // Comment: nếu có comment thì hiển thị icon con mắt, click mới xem nội dung
  const hasComment = !!comment;
  const commentDisplay = hasComment ? '<button class="comment-eye-btn" type="button" title="Xem comment">👁</button>' : '';
  tr.innerHTML = `
    <td>${postIdDisplay}</td>
    <td>${userIdDisplay}</td>
    <td>${name || ''}</td>
    <td>${reactDisplay}</td>
    <td>${commentDisplay}</td>
    <td>${time || ''}</td>
    <td class="type-cell ${typeColorClass}">${type || ''}</td>
  `;
  tr.style.opacity = '0';
  tr.style.transform = 'translateY(-10px)';
  tbody.appendChild(tr);

  // Gắn dữ liệu comment và sự kiện click cho icon con mắt
  if (hasComment) {
    const commentCell = tr.children[4]; // cột Comment
    commentCell.dataset.comment = comment;
    const eyeBtn = commentCell.querySelector('.comment-eye-btn');
    if (eyeBtn) {
      eyeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const text = commentCell.dataset.comment || '';
        if (!text) return;

        // Khi click lần đầu: thay icon bằng nội dung comment
        // Nếu muốn cho phép thu gọn lại, có thể toggle, nhưng hiện tại chỉ hiển thị ra luôn
        commentCell.textContent = text;
      });
    }
  }

  // Animation
  setTimeout(() => {
    tr.style.transition = 'all 0.3s ease';
    tr.style.opacity = '1';
    tr.style.transform = 'translateY(0)';
  }, 10);

  emptyState.classList.remove('show');
  updateRowCount();
}

// Thêm dòng cho bảng Quản lý post
function appendPostRow(post) {
  if (!postTableBody) return;
  const type = mapFlagToType(post.flag);
  const typeClass = getTypeColorClass(type);
  const tr = document.createElement('tr');
  const postId = post.id || '';
  const text = post.text || '';

  const postLink = postId
    ? `<a href="https://fb.com/${postId}" target="_blank" rel="noopener noreferrer" class="id-link">${postId}</a>`
    : '';

  tr.innerHTML = `
    <td>${postLink}</td>
    <td>${text}</td>
    <td class="type-cell ${typeClass}">${type}</td>
  `;

  postTableBody.appendChild(tr);
}

function addGeneratedRow() {
  // Tạo type ngẫu nhiên để có màu sắc đa dạng
  const types = ['type1', 'type2', 'type3'];
  const randomType = types[Math.floor(Math.random() * types.length)];
  const names = ['Nguyễn Văn A', 'Trần Thị B', 'Lê Văn C', 'Phạm Thị D', 'Hoàng Văn E'];
  const randomName = names[Math.floor(Math.random() * names.length)];
  const comments = ['Rất hay!', 'Cảm ơn bạn', 'Tuyệt vời', 'Đồng ý', ''];
  const randomComment = comments[Math.floor(Math.random() * comments.length)];
  
  appendRow({
    id: counter++,
    userId: `user_${Math.floor(Math.random() * 1000000)}`,
    name: randomName,
    react: Math.random() > 0.3, // 70% có react
    comment: randomComment,
    time: new Date().toLocaleTimeString('vi-VN'),
    type: randomType,
  });
}

// Hàm kiểm tra và thêm dữ liệu mới
async function checkForNewData() {
  try {
    const res = await fetch('../backend/data/results/all_results_summary.json');
    if (!res.ok) throw new Error('Fetch failed');
    const data = await res.json();
    
    // Lấy tất cả posts từ results_by_file
    const allPosts = [];
    Object.values(data.results_by_file || {}).forEach(filePosts => {
      if (Array.isArray(filePosts)) {
        allPosts.push(...filePosts);
      }
    });
    
    let newCount = 0;
    // Chỉ thêm những user mới (gộp cả react & comment)
    allPosts.forEach((post) => {
      const postId = post.post_id || '';
      if (!postId) return;

      // Map flag thành type
      let type = 'type1';
      const flag = (post.flag || '').toLowerCase();
      if (flag === 'xanh') {
        type = 'type1';
      } else if (flag === 'vàng' || flag === 'vang') {
        type = 'type2';
      } else if (flag === 'đỏ' || flag === 'do') {
        type = 'type3';
      }

      // Thời gian mặc định: comment mới nhất của bài (nếu có)
      let defaultTime = new Date().toLocaleTimeString('vi-VN');
      if (post.comments && post.comments.length > 0) {
        const sortedAllComments = [...post.comments].sort((a, b) => {
          const timeA = new Date(a.created_time_vn || 0);
          const timeB = new Date(b.created_time_vn || 0);
          return timeB - timeA;
        });
        if (sortedAllComments[0] && sortedAllComments[0].created_time_vn) {
          defaultTime = sortedAllComments[0].created_time_vn;
        }
      }

      // Gom reactions theo userId
      const reactionsByUser = new Map();
      if (post.reactions && post.reactions.length > 0) {
        post.reactions.forEach((r) => {
          const uid = r && r.id ? String(r.id) : '';
          if (!uid) return;
          reactionsByUser.set(uid, r);
        });
      }

      // Gom comments theo userId (lấy comment mới nhất của từng user)
      const commentsByUser = new Map();
      if (post.comments && post.comments.length > 0) {
        post.comments.forEach((c) => {
          const uid = c && c.id ? String(c.id) : '';
          if (!uid) return;
          const prev = commentsByUser.get(uid);
          if (!prev) {
            commentsByUser.set(uid, c);
          } else {
            const prevTime = new Date(prev.created_time_vn || 0);
            const curTime = new Date(c.created_time_vn || 0);
            if (curTime > prevTime) {
              commentsByUser.set(uid, c);
            }
          }
        });
      }

      // Tập tất cả user xuất hiện ở react hoặc comment
      const allUserIds = new Set([
        ...reactionsByUser.keys(),
        ...commentsByUser.keys(),
      ]);

      allUserIds.forEach((uid) => {
        const reaction = reactionsByUser.get(uid);
        const comment = commentsByUser.get(uid);

        const userId = uid;
        const name =
          (reaction && reaction.name) ||
          (comment && comment.name) ||
          '';

        const hasReact = !!reaction;
        const commentText = comment && comment.text ? comment.text : '';
        const time =
          (comment && comment.created_time_vn) ? comment.created_time_vn : defaultTime;

        const uniqueKey = `${postId}_${userId}`;
        if (uniqueKey && !loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: userId,
            name: name,
            react: hasReact,        // chỉ tick nếu có trong reactions
            comment: commentText,   // chỉ có text nếu user có comment
            time: time,
            type: type,
          });

          loadedPostIds.add(uniqueKey);
          newCount++;
        }
      });
    });
    
    if (newCount > 0) {
      console.log(`Đã thêm ${newCount} dòng dữ liệu mới`);
    }
  } catch (err) {
    console.error('Không kiểm tra được dữ liệu mới:', err);
  }
}

async function loadInitialData() {
  // Reset để có thể load lại khi click
  initialLoaded = false;
  // Xóa dữ liệu cũ trước khi load mới
  tbody.innerHTML = '';
  counter = 1;
  loadedPostIds.clear(); // Xóa danh sách post_id đã load
  
  try {
    // Đọc từ all_results_summary.json
    const res = await fetch('../backend/data/results/all_results_summary.json');
    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }
    const data = await res.json();
    console.log('Đã load file JSON thành công, tổng số files:', data.total_files);
    
    // Lấy tất cả posts từ results_by_file
    const allPosts = [];
    Object.values(data.results_by_file || {}).forEach(filePosts => {
      if (Array.isArray(filePosts)) {
        allPosts.push(...filePosts);
      }
    });
    
    console.log(`Tổng số posts cần hiển thị: ${allPosts.length}`);
    
    // Chuyển đổi dữ liệu sang format của bảng
    let displayedCount = 0;
    allPosts.forEach((post) => {
      const postId = post.post_id || '';
      if (!postId) return; // Bỏ qua nếu không có post_id

      // Map flag thành type (xanh -> type1, vàng -> type2, đỏ -> type3)
      let type = 'type1'; // mặc định
      const flag = (post.flag || '').toLowerCase();
      if (flag === 'xanh') {
        type = 'type1';
      } else if (flag === 'vàng' || flag === 'vang') {
        type = 'type2';
      } else if (flag === 'đỏ' || flag === 'do') {
        type = 'type3';
      }

      // Thời gian mặc định: comment mới nhất của bài (nếu có)
      let defaultTime = new Date().toLocaleTimeString('vi-VN');
      if (post.comments && post.comments.length > 0) {
        const sortedAllComments = [...post.comments].sort((a, b) => {
          const timeA = new Date(a.created_time_vn || 0);
          const timeB = new Date(b.created_time_vn || 0);
          return timeB - timeA;
        });
        if (sortedAllComments[0] && sortedAllComments[0].created_time_vn) {
          defaultTime = sortedAllComments[0].created_time_vn;
        }
      }

      // Gom reactions theo userId
      const reactionsByUser = new Map();
      if (post.reactions && post.reactions.length > 0) {
        post.reactions.forEach((r) => {
          const uid = r && r.id ? String(r.id) : '';
          if (!uid) return;
          reactionsByUser.set(uid, r);
        });
      }

      // Gom comments theo userId (lấy comment mới nhất của từng user)
      const commentsByUser = new Map();
      if (post.comments && post.comments.length > 0) {
        post.comments.forEach((c) => {
          const uid = c && c.id ? String(c.id) : '';
          if (!uid) return;
          const prev = commentsByUser.get(uid);
          if (!prev) {
            commentsByUser.set(uid, c);
          } else {
            const prevTime = new Date(prev.created_time_vn || 0);
            const curTime = new Date(c.created_time_vn || 0);
            if (curTime > prevTime) {
              commentsByUser.set(uid, c);
            }
          }
        });
      }

      // Tập tất cả user xuất hiện ở react hoặc comment
      const allUserIds = new Set([
        ...reactionsByUser.keys(),
        ...commentsByUser.keys(),
      ]);

      allUserIds.forEach((uid) => {
        const reaction = reactionsByUser.get(uid);
        const comment = commentsByUser.get(uid);

        const userId = uid;
        const name =
          (reaction && reaction.name) ||
          (comment && comment.name) ||
          '';

        const hasReact = !!reaction;
        const commentText = comment && comment.text ? comment.text : '';
        const time =
          (comment && comment.created_time_vn) ? comment.created_time_vn : defaultTime;

        const uniqueKey = `${postId}_${userId}`; // Tạo key duy nhất cho mỗi cặp post-user
        if (uniqueKey && !loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: userId,
            name: name,
            react: hasReact,        // chỉ tích nếu user có react
            comment: commentText,   // chỉ có text nếu user có comment
            time: time,
            type: type,
          });

          // Đánh dấu đã load
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      });
    });
    
    console.log(`Đã hiển thị ${displayedCount} dòng dữ liệu`);
    initialLoaded = true;
  } catch (err) {
    console.error('Không tải được all_results_summary.json', err);
    // Fallback: thử load data.json cũ
    try {
      const res = await fetch('data.json');
      if (res.ok) {
        const rows = await res.json();
        rows.forEach((row) => {
          appendRow(row);
          counter = Math.max(counter, Number(row.id) + 1);
        });
        initialLoaded = true;
      }
    } catch (fallbackErr) {
      console.error('Không tải được data.json', fallbackErr);
    }
  }

  // Show empty state if no rows
  if (tbody.children.length === 0) {
    emptyState.classList.add('show');
  }
}

startBtn.addEventListener(
  'click',
  async () => {
    // Load và hiển thị tất cả dữ liệu từ all_results_summary.json ngay lập tức
    // Không cần chờ backend, hiển thị dữ liệu trước
    await loadInitialData();
    
    // Sau đó mới chạy backend (nếu cần) - nhưng không block việc hiển thị dữ liệu
    triggerBackendRun().catch(err => {
      console.warn('Backend không chạy được, nhưng vẫn hiển thị dữ liệu:', err);
    });
    
    // Tự động kiểm tra dữ liệu mới mỗi 5 giây để cập nhật khi có dữ liệu mới
    const checkInterval = 5000; // 5 giây
    dataCheckInterval = setInterval(checkForNewData, checkInterval);
    
    setScanning(true);
  }
);

stopBtn.addEventListener('click', () => {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
  // Dừng kiểm tra dữ liệu mới
  if (dataCheckInterval) {
    clearInterval(dataCheckInterval);
    dataCheckInterval = null;
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
    { wch: 18 }, // ID Bài Post
    { wch: 18 }, // ID User
    { wch: 20 }, // Name
    { wch: 12 }, // React
    { wch: 12 }, // Comment
    { wch: 20 }, // Time
    { wch: 15 }  // Type
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

// ==== Thêm data nhóm - Mở file từ máy tính ====

const addGroupDataBtn = document.getElementById('addGroupDataBtn');

// Hàm xử lý nút Thêm data nhóm - chỉ mở dialog chọn file
function handleAddGroupData() {
  // Tạo input file ẩn
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = '.json,.xlsx,.xls,.txt,.csv';
  fileInput.style.display = 'none';
  
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      console.log('File đã chọn:', file.name);
      // Chỉ mở file, không xử lý gì thêm
    }
    // Xóa input để có thể chọn lại file cùng tên
    fileInput.value = '';
  });
  
  // Trigger click để mở dialog chọn file
  document.body.appendChild(fileInput);
  fileInput.click();
  document.body.removeChild(fileInput);
}

addGroupDataBtn.addEventListener('click', handleAddGroupData);

// ==== Help Button với Tooltip ====

const helpBtn = document.getElementById('helpBtn');
const helpTooltip = document.getElementById('helpTooltip');
const tooltipClose = document.querySelector('.tooltip-close');

function toggleHelpTooltip() {
  helpTooltip.classList.toggle('show');
}

function closeHelpTooltip() {
  helpTooltip.classList.remove('show');
}

helpBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  toggleHelpTooltip();
});

tooltipClose.addEventListener('click', closeHelpTooltip);

// Đóng tooltip khi click ra ngoài
document.addEventListener('click', (e) => {
  if (!helpBtn.contains(e.target) && !helpTooltip.contains(e.target)) {
    closeHelpTooltip();
  }
});
// ==== Bộ lọc màu sắc ====

const filterButtons = document.querySelectorAll('.filter-btn');
let currentFilter = 'all';

function applyFilter(filterType) {
  currentFilter = filterType;
  const rows = tbody.querySelectorAll('tr');
  
  rows.forEach((row) => {
    const typeCell = row.querySelector('.type-cell');
    if (!typeCell) {
      row.classList.remove('filtered-out');
      return;
    }
    
    if (filterType === 'all') {
      row.classList.remove('filtered-out');
    } else {
      // Kiểm tra xem cell có class tương ứng với filter không
      if (typeCell.classList.contains(filterType)) {
        row.classList.remove('filtered-out');
      } else {
        row.classList.add('filtered-out');
      }
    }
  });
  
  // Cập nhật trạng thái active của các nút
  filterButtons.forEach((btn) => {
    if (btn.dataset.filter === filterType) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Kiểm tra empty state
  const visibleRows = Array.from(rows).filter(row => !row.classList.contains('filtered-out'));
  if (visibleRows.length === 0 && rows.length > 0) {
    emptyState.classList.add('show');
  } else {
    emptyState.classList.remove('show');
  }
}

// Thêm event listener cho các nút filter
filterButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const filterType = btn.dataset.filter;
    applyFilter(filterType);
  });
});

// ==== Tabs: Danh sách quét / Quản lý post ====
if (tabScanList && tabPostManager && scanView && postView) {
  tabScanList.addEventListener('click', () => {
    tabScanList.classList.add('active');
    tabPostManager.classList.remove('active');
    scanView.style.display = 'block';
    postView.style.display = 'none';
  });

  tabPostManager.addEventListener('click', async () => {
    tabPostManager.classList.add('active');
    tabScanList.classList.remove('active');
    scanView.style.display = 'none';
    postView.style.display = 'block';
    await loadPostsForManager();
  });
}
