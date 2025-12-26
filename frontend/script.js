// Splash Screen
const splashScreen = document.getElementById('splashScreen');
const splashStartBtn = document.getElementById('splashStartBtn');

// Thêm class splash-active khi trang load để ẩn container
if (splashScreen) {
  document.body.classList.add('splash-active');
}

// Ẩn splash screen khi click nút "Bắt đầu"
if (splashStartBtn) {
  splashStartBtn.addEventListener('click', () => {
    if (splashScreen) {
      splashScreen.classList.add('hidden');
      // Cho phép hiển thị container và scroll sau khi ẩn splash
      setTimeout(() => {
        document.body.classList.remove('splash-active');
      }, 600); // Đợi animation hoàn thành
    }
  });
}

// startBtn và stopBtn đã bị xóa khỏi left-panel
const runMinutesInput = document.getElementById('runMinutes');
const intervalInput = document.getElementById('interval');
const stopAllBtn = document.getElementById('stopAllBtn');
const pauseAllBtn = document.getElementById('pauseAllBtn');
const tbody = document.querySelector('#listTable tbody');
const emptyState = document.getElementById('emptyState');
const rowCount = document.getElementById('rowCount');
const statusDot = document.getElementById('statusDot');
const backendStatus = document.getElementById('backendStatus');
// Tabs & view cho danh sách quét / quản lý post
const tabScanList = document.getElementById('tabScanList');
const tabPostManager = document.getElementById('tabPostManager');
const tabSettings = document.getElementById('tabSettings');
const scanView = document.getElementById('scanView');
const postView = document.getElementById('postView');
const settingsView = document.getElementById('settingsView');
// Bảng quản lý post
const postTableBody = document.querySelector('#postTable tbody');
const postEmptyState = document.getElementById('postEmptyState');
// Setting profile elements
const settingApiKeyInput = document.getElementById('settingApiKey');
const saveApiKeyBtn = document.getElementById('saveApiKeyBtn');
const profileList = document.getElementById('profileList');
// (Preview settings.json đã bị bỏ khỏi UI)
const addProfileRowBtn = document.getElementById('addProfileRowBtn');
const autoJoinGroupBtn = document.getElementById('autoJoinGroupBtn');
const stopAllSettingBtn = document.getElementById('stopAllSettingBtn');
const stopSelectedProfilesBtn = document.getElementById('stopSelectedProfilesBtn');
const pauseSelectedProfilesBtn = document.getElementById('pauseSelectedProfilesBtn');
const feedAccountSettingBtn = document.getElementById('feedAccountSettingBtn');
const scanPostsSettingBtn = document.getElementById('scanPostsSettingBtn');
const scanGroupSettingBtn = document.getElementById('scanGroupSettingBtn');
const runAllInfoBtn = document.getElementById('runAllInfoBtn');
const runSelectedInfoBtn = document.getElementById('runSelectedInfoBtn');
const feedConfigPanel = document.getElementById('feedConfigPanel');
const scanConfigPanel = document.getElementById('scanConfigPanel');
const groupScanPanel = document.getElementById('groupScanPanel');
const groupScanPostCountInput = document.getElementById('groupScanPostCountInput');
const groupScanStartDateInput = document.getElementById('groupScanStartDateInput');
const groupScanEndDateInput = document.getElementById('groupScanEndDateInput');
const groupScanStartBtn = document.getElementById('groupScanStartBtn');
const groupScanCancelBtn = document.getElementById('groupScanCancelBtn');
const scanTextInput = document.getElementById('scanTextInput');
const scanRunMinutesInput = document.getElementById('scanRunMinutesInput');
const scanRestMinutesInput = document.getElementById('scanRestMinutesInput');
const scanStartBtn = document.getElementById('scanStartBtn');
const scanCancelBtn = document.getElementById('scanCancelBtn');
const feedTextInput = document.getElementById('feedTextInput');
const feedRunMinutesInput = document.getElementById('feedRunMinutesInput');
const feedRestMinutesInput = document.getElementById('feedRestMinutesInput');
const feedStartBtn = document.getElementById('feedStartBtn');
const feedCancelBtn = document.getElementById('feedCancelBtn');

const API_BASE = 'http://localhost:8000';
const SETTINGS_STORAGE_KEY = 'profileSettings';
const toastContainer = document.getElementById('toastContainer');

let counter = 1;
let timerId = null;
let initialLoaded = false;
let dataCheckInterval = null; // Interval để kiểm tra dữ liệu mới
let loadedPostIds = new Set(); // Lưu các post_id đã load để tránh trùng lặp
let postsLoaded = false; // Đã load dữ liệu quản lý post hay chưa
let profileState = {
  apiKey: '',
  profiles: {}, // { [profileId]: { cookie: '', access_token: '', fb_dtsg: '', lsd: '', spin_r: '', spin_t: '', groups: string[] } }
  selected: {}, // { [profileId]: true/false } (frontend-only)
};
let addRowEl = null; // Row tạm để nhập profile mới
let joinGroupPollTimer = null;
let feedPollTimer = null;
let scanBackendPollTimer = null; // Poll trạng thái bot runner để sync UI sau F5
let isScanning = false; // Trạng thái đang quét
let isPausedAll = false; // Trạng thái pause all (UI)
let lastJobsStatus = null; // cache /jobs/status để badge không bị sai khi mới mở trang

function setPauseAllButtonLabel(paused) {
  if (!pauseAllBtn) return;
  const isPaused = !!paused;
  // Support cả 2 kiểu: button có span icon/text hoặc button text thuần
  const icon = pauseAllBtn.querySelector ? pauseAllBtn.querySelector('span.btn-icon') : null;
  const textSpan = pauseAllBtn.querySelector ? pauseAllBtn.querySelector('span:last-child') : null;
  if (icon || textSpan) {
    if (icon) icon.textContent = isPaused ? '▶️' : '⏸️';
    if (textSpan) textSpan.textContent = isPaused ? 'Tiếp tục tất cả' : 'Tạm dừng tất cả';
  } else {
    pauseAllBtn.textContent = isPaused ? 'Tiếp tục tất cả' : 'Tạm dừng tất cả';
  }
}

// stopBtn đã bị xóa khỏi left-panel, các nút stop được xử lý trong settings tab
// Nút dừng luôn enable để có thể dừng bất cứ lúc nào
try {
  if (pauseAllBtn) pauseAllBtn.disabled = true;
  // stopAllSettingBtn luôn enable
  if (stopAllSettingBtn) stopAllSettingBtn.disabled = false;
  if (stopSelectedProfilesBtn) stopSelectedProfilesBtn.disabled = true;
  if (pauseSelectedProfilesBtn) pauseSelectedProfilesBtn.disabled = true;
} catch (_) { }

function updateRowCount() {
  const count = tbody.children.length;
  rowCount.textContent = count;
}

// Load dữ liệu quản lý post từ file post_ids
async function loadPostsForManager() {
  if (postsLoaded || !postTableBody) return;
  try {
    // Gọi API để lấy danh sách post IDs
    const res = await callBackend('/data/post-ids', { method: 'GET' });
    const data = res;

    if (!data.files || data.files.length === 0) {
      postEmptyState && postEmptyState.classList.add('show');
      postsLoaded = true;
      return;
    }

    // Hiển thị từng post
    data.files.forEach((item) => appendPostRow(item));
    postEmptyState && postEmptyState.classList.remove('show');
    postsLoaded = true;
  } catch (err) {
    console.error('Không tải được dữ liệu post_ids:', err);
    postEmptyState && postEmptyState.classList.add('show');
  }
}

function setScanning(isOn) {
  isScanning = isOn;
  // startBtn và stopBtn đã bị xóa khỏi left-panel
  // Logic quét được xử lý bởi các nút trong settings tab
  
  // Disable/enable các nút quét khác khi đang quét
  if (scanStartBtn) {
    scanStartBtn.disabled = isOn;
  }
  if (scanPostsSettingBtn) {
    scanPostsSettingBtn.disabled = isOn;
  }

  // Khi dừng quét: gỡ hết trạng thái loading/spinner ở các nút liên quan
  // (tránh trường hợp backend stop chậm làm UI bị kẹt, không bấm lại được)
  if (!isOn) {
    setButtonLoading(scanStartBtn, false);
    setButtonLoading(scanPostsSettingBtn, false);
    // Dừng poll số bài đã quét được
    if (scanStatsInterval) {
      clearInterval(scanStatsInterval);
      scanStatsInterval = null;
    }
    // Ẩn toast số bài đã quét
    const scanToast = document.getElementById('scanStatsToast');
    const progressToast = document.getElementById('progressToast');
    if (scanToast) scanToast.style.display = 'none';
    // Ẩn progressToast nếu cả 2 toast đều ẩn
    const infoToast = document.getElementById('infoProgressToast');
    if (progressToast && (!infoToast || infoToast.style.display === 'none')) {
      progressToast.style.display = 'none';
    }
  }
  // startBtn đã bị xóa khỏi left-panel, loading được xử lý bởi các nút trong settings
}

function syncRunningLabelsWithPauseState() {
  // Khi PAUSE ALL bật, đổi text các nút đang "loading" để user biết đang tạm dừng,
  // tránh hiểu nhầm vẫn "đang quét/đang chạy".
  try {
    if (isScanning) {
      // startBtn đã bị xóa, chỉ cập nhật các nút trong settings

      if (scanStartBtn && scanStartBtn.classList.contains('btn-loading')) {
        scanStartBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang chạy...';
      }
      if (scanPostsSettingBtn && scanPostsSettingBtn.classList.contains('btn-loading')) {
        scanPostsSettingBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang quét...';
      }
    }

    if (feedPollTimer) {
      if (feedStartBtn && feedStartBtn.classList.contains('btn-loading')) {
        feedStartBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang chạy...';
      }
      if (feedAccountSettingBtn && feedAccountSettingBtn.classList.contains('btn-loading')) {
        feedAccountSettingBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang nuôi acc...';
      }
    }

    if (joinGroupPollTimer) {
      if (autoJoinGroupBtn && autoJoinGroupBtn.classList.contains('btn-loading')) {
        autoJoinGroupBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang auto join...';
      }
    }
  } catch (_) { }
}

function applyControlStateToProfileRows(st) {
  // Đồng bộ badge trạng thái cho mọi profile row
  const pausedAll = Boolean(st && st.global_pause);
  const pausedProfiles = new Set(Array.isArray(st && st.paused_profiles) ? st.paused_profiles.map((x) => String(x)) : []);
  const profileStates = (st && typeof st.profile_states === 'object' && st.profile_states) ? st.profile_states : {};
  const jobs = lastJobsStatus || {};
  const botRunning = Boolean(jobs && jobs.bot_running);
  const botProfileIds = new Set(Array.isArray(jobs && jobs.bot_profile_ids) ? jobs.bot_profile_ids.map((x) => String(x)) : []);
  const joinRunning = new Set(Array.isArray(jobs && jobs.join_groups_running) ? jobs.join_groups_running.map((x) => String(x)) : []);
  const feedRunning = new Set(Array.isArray(jobs && jobs.feed_running) ? jobs.feed_running.map((x) => String(x)) : []);
  const sessionRunning = Boolean(
    botRunning
    || joinRunning.size > 0
    || feedRunning.size > 0
  );

  const rows = document.querySelectorAll('.profile-row-wrap');
  rows.forEach((wrap) => {
    const pid = String(wrap.dataset.profileId || '').trim();
    if (!pid) return;
    const badge = wrap.querySelector('.profile-state-badge');

    // --- Effective state ---
    // Default: READY (mới vào / chưa có job)
    let eff = 'READY';
    // Nếu không có session nào chạy -> luôn READY
    if (sessionRunning) {
      // Nếu đang pause (global hoặc profile) -> PAUSED
      if (pausedAll || pausedProfiles.has(pid)) {
        eff = 'PAUSED';
      } else {
        // RUNNING nếu profile đang có feed/join hoặc runner đang chạy và profile_state RUNNING
        if (feedRunning.has(pid) || joinRunning.has(pid)) {
          eff = 'RUNNING';
        } else if (botRunning) {
          const ps = String(profileStates[pid] || '').toUpperCase();
          // Ưu tiên list từ backend: bot_profile_ids
          const inBot = botProfileIds.size > 0 ? botProfileIds.has(pid) : false;
          eff = (ps === 'RUNNING' || inBot) ? 'RUNNING' : 'READY';
        } else {
          eff = 'READY';
        }
      }
    }

    if (badge) {
      badge.classList.remove('state-running', 'state-paused', 'state-ready', 'state-idle', 'state-unknown', 'state-stopping', 'state-stopped', 'state-error');
      if (eff === 'PAUSED') badge.classList.add('state-paused');
      else if (eff === 'RUNNING') badge.classList.add('state-running');
      else badge.classList.add('state-ready');
      badge.textContent = (eff === 'READY') ? 'SẴN SÀNG' : (eff === 'RUNNING') ? 'ĐANG CHẠY' : 'ĐANG TẠM DỪNG';
    }
  });
}

/**
 * Central function để quản lý button states cho pause/stop
 * Đảm bảo logic nhất quán và tránh race conditions
 */
function updateStopPauseButtonsByJobs() {
  const jobs = lastJobsStatus || {};
  const botHasProfiles = Array.isArray(jobs && jobs.bot_profile_ids) && jobs.bot_profile_ids.length > 0;
  const sessionRunning = Boolean(
    (jobs && jobs.bot_running && botHasProfiles)
    || (Array.isArray(jobs && jobs.join_groups_running) && jobs.join_groups_running.length > 0)
    || (Array.isArray(jobs && jobs.feed_running) && jobs.feed_running.length > 0)
  );
  const hasSelected = getSelectedProfileIds().length > 0;
  
  // Kiểm tra info collector đang chạy từ backend
  let infoCollectorRunning = false;
  try {
    // Check từ progress API để đảm bảo chính xác
    // Note: Không dùng isInfoCollectorRunning vì có thể bị out of sync
    // Sẽ check async trong updateInfoProgress
  } catch (_) { }
  
  // Nếu đang chạy info collector (local flag) hoặc có session running thì enable buttons
  const shouldEnableButtons = sessionRunning || isInfoCollectorRunning;

  /**
   * Helper function để set button state một cách nhất quán
   */
  function setButtonState(btn, enabled, skipIfLoading = true) {
    if (!btn) return;
    if (skipIfLoading && btn.classList && btn.classList.contains('btn-loading')) {
      return; // Giữ nguyên state nếu đang loading
    }
    
    btn.disabled = !enabled;
    if (enabled) {
      btn.style.opacity = '1';
      btn.style.pointerEvents = 'auto';
      btn.style.cursor = 'pointer';
    } else {
      btn.style.opacity = '0.5';
      btn.style.pointerEvents = 'none';
      btn.style.cursor = 'not-allowed';
    }
  }

  // stopBtn đã bị xóa khỏi left-panel, chỉ còn stopAllSettingBtn
  // Nút dừng luôn enable để có thể dừng bất cứ lúc nào
  setButtonState(stopAllSettingBtn, true);

  // PAUSE ALL button
  setButtonState(pauseAllBtn, shouldEnableButtons);

  // Selected profiles buttons (cần cả hasSelected)
  setButtonState(pauseSelectedProfilesBtn, shouldEnableButtons && hasSelected);
  setButtonState(stopSelectedProfilesBtn, shouldEnableButtons && hasSelected);
}

// ==== Settings (frontend-only) ====
async function tryLoadProfileStateFromBackend() {
  try {
    const raw = await callBackendNoAlert('/settings', { method: 'GET' });
    if (!raw) return false;

    const apiKey = raw.API_KEY || raw.api_key || '';
    const profileIds = raw.PROFILE_IDS || raw.profile_ids || {};

    profileState.apiKey = String(apiKey || '').trim();

    // PROFILE_IDS có thể là list/string/dict; normalize về dict
    const nextProfiles = {};
    if (Array.isArray(profileIds)) {
      profileIds.forEach((pid) => {
        const key = String(pid || '').trim();
        if (key) nextProfiles[key] = { 
          cookie: '', 
          access_token: '', 
          fb_dtsg: '', 
          lsd: '', 
          spin_r: '', 
          spin_t: '',
          groups: []
        };
      });
    } else if (typeof profileIds === 'string') {
      profileIds.split(',').map((s) => s.trim()).filter(Boolean).forEach((pid) => {
        nextProfiles[pid] = { 
          cookie: '', 
          access_token: '', 
          fb_dtsg: '', 
          lsd: '', 
          spin_r: '', 
          spin_t: '',
          groups: []
        };
      });
    } else if (profileIds && typeof profileIds === 'object') {
      Object.entries(profileIds).forEach(([pid, cfg]) => {
        const key = String(pid || '').trim();
        if (!key) return;
        nextProfiles[key] = {
          cookie: (cfg && cfg.cookie) ? String(cfg.cookie) : '',
          access_token: (cfg && (cfg.access_token || cfg.accessToken)) ? String(cfg.access_token || cfg.accessToken) : '',
          fb_dtsg: (cfg && cfg.fb_dtsg) ? String(cfg.fb_dtsg) : '',
          lsd: (cfg && cfg.lsd) ? String(cfg.lsd) : '',
          spin_r: (cfg && cfg.spin_r) ? String(cfg.spin_r) : '',
          spin_t: (cfg && cfg.spin_t) ? String(cfg.spin_t) : '',
          groups: (cfg && Array.isArray(cfg.groups)) ? cfg.groups.map((x) => String(x || '').trim()).filter(Boolean) : [],
        };
      });
    }

    profileState.profiles = nextProfiles;
    // giữ selected nếu có
    if (!profileState.selected || typeof profileState.selected !== 'object') profileState.selected = {};
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(profileState));
    return true;
  } catch (err) {
    return false;
  }
}

async function loadProfileState() {
  // Ưu tiên lấy từ backend nếu có
  const loadedFromBackend = await tryLoadProfileStateFromBackend();
  if (loadedFromBackend) {
    if (settingApiKeyInput) settingApiKeyInput.value = profileState.apiKey || '';
    renderProfileList();
    updateSettingsActionButtons();
    return;
  }

  try {
    const stored = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      profileState = {
        apiKey: parsed.apiKey || '',
        profiles: parsed.profiles || {},
        selected: parsed.selected || {},
      };
    }
  } catch (err) {
    console.warn('Không đọc được dữ liệu settings từ localStorage', err);
  }

  if (settingApiKeyInput) settingApiKeyInput.value = profileState.apiKey || '';
  renderProfileList();
  updateSettingsActionButtons();
}

function saveProfileState() {
  localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(profileState));
}

function getSelectedProfileIds() {
  return Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
}

function updateSettingsActionButtons() {
  const selected = getSelectedProfileIds();
  const hasSelected = selected.length > 0;

  // Các nút "hành động" ở Setting profile: yêu cầu tick ít nhất 1 profile
  const needSelectedBtns = [
    scanPostsSettingBtn,
    scanGroupSettingBtn,
    autoJoinGroupBtn,
    feedAccountSettingBtn,
    stopSelectedProfilesBtn,
    pauseSelectedProfilesBtn,
    runSelectedInfoBtn,
  ].filter(Boolean);

  needSelectedBtns.forEach((b) => {
    // nếu đang loading thì giữ nguyên trạng thái disabled
    if (b.classList && b.classList.contains('btn-loading')) return;
    b.disabled = !hasSelected;
  });

  // Các nút ALL (không phụ thuộc tick)
  // Lưu ý: stop/pause ALL sẽ được enable/disable theo /jobs/status (updateStopPauseButtonsByJobs)
  // nên không set ở đây để tránh ghi đè logic.

  // Các nút "Chạy" trong các panel cũng yêu cầu tick profile
  const runBtns = [feedStartBtn, scanStartBtn, groupScanStartBtn].filter(Boolean);
  runBtns.forEach((b) => {
    if (b.classList && b.classList.contains('btn-loading')) return;
    b.disabled = !hasSelected;
  });

  // Nếu không có selection thì auto đóng panel để tránh người dùng nhập rồi mới biết không chạy được
  if (!hasSelected) {
    if (feedConfigPanel) feedConfigPanel.style.display = 'none';
    if (scanConfigPanel) scanConfigPanel.style.display = 'none';
    if (groupScanPanel) groupScanPanel.style.display = 'none';
  }

  // Đồng bộ enable/disable cho STOP/PAUSE theo trạng thái backend (sessionRunning)
  try { updateStopPauseButtonsByJobs(); } catch (_) { }
}

function showToast(message, type = 'success', ms = 1600) {
  if (!toastContainer) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  toastContainer.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 220);
  }, ms);
}

function setButtonLoading(btn, isLoading, loadingText) {
  if (!btn) return;
  if (isLoading) {
    // Lưu HTML gốc nếu chưa có (bao gồm cả icon)
    if (!btn.dataset.origHTML) {
      btn.dataset.origHTML = btn.innerHTML || btn.textContent || '';
    }
    if (!btn.dataset.origText) {
      btn.dataset.origText = btn.textContent || '';
    }
    btn.disabled = true;
    btn.classList.add('btn-loading');
    // Giữ nguyên cấu trúc HTML nếu có, chỉ thêm spinner
    if (loadingText) {
      // Nếu button có icon, giữ icon và thêm spinner
      const hasIcon = btn.querySelector('.btn-icon');
      if (hasIcon) {
        btn.innerHTML = `<span class="btn-icon">${hasIcon.textContent}</span><span>${loadingText}</span>`;
      } else {
        btn.textContent = loadingText;
      }
    }
  } else {
    btn.disabled = false;
    btn.classList.remove('btn-loading');
    // Khôi phục HTML gốc (bao gồm cả icon)
    if (btn.dataset.origHTML) {
      btn.innerHTML = btn.dataset.origHTML;
      delete btn.dataset.origHTML;
    } else if (btn.dataset.origText) {
      btn.textContent = btn.dataset.origText;
      delete btn.dataset.origText;
    }
  }
}

// (Preview settings.json đã bị bỏ khỏi UI)

function createPill(text) {
  const pill = document.createElement('span');
  pill.className = 'pill';
  pill.textContent = text;
  return pill;
}

function setProfileListEmptyStateIfNeeded() {
  if (!profileList) return;
  const hasRow = Boolean(profileList.querySelector('.profile-row:not(.add-profile-form)'));
  if (hasRow) {
    profileList.classList.remove('empty-state-box');
    const p = profileList.querySelector('p.muted');
    if (p && p.textContent && p.textContent.includes('Chưa có profile')) {
      // nếu đang là empty placeholder thì xóa
      profileList.innerHTML = '';
    }
    return;
  }
  profileList.classList.add('empty-state-box');
  profileList.innerHTML = '<p class="muted">Chưa có profile nào</p>';
}

function buildProfileRow(initialPid, initialInfo, isNew = false) {
  let currentPid = initialPid;
  const wrap = document.createElement('div');
  wrap.className = 'profile-row-wrap';
  wrap.dataset.profileId = String(currentPid || '').trim();

  const row = document.createElement('div');
  row.className = 'profile-row';

  const selectWrap = document.createElement('div');
  selectWrap.className = 'profile-select';

  const selectCb = document.createElement('input');
  selectCb.type = 'checkbox';
  selectCb.className = 'profile-select-cb';
  selectCb.title = 'Chọn profile';
  selectCb.checked = Boolean(profileState.selected && profileState.selected[currentPid]);

  const pidInput = document.createElement('input');
  pidInput.className = 'profile-id-input';
  pidInput.type = 'text';
  pidInput.value = currentPid;
  pidInput.addEventListener('change', () => {
    wrap.dataset.profileId = String(pidInput.value || '').trim();
  });

  const actions = document.createElement('div');
  actions.className = 'profile-actions';

  const saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  saveBtn.className = 'btn-success';
  saveBtn.textContent = 'Lưu';

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'btn-danger';
  removeBtn.textContent = 'Xóa';

  const groupBtn = document.createElement('button');
  groupBtn.type = 'button';
  groupBtn.className = 'btn-primary';
  groupBtn.textContent = 'Thêm Groups';

  // Badge hiển thị trạng thái profile (RUNNING/PAUSED/STOPPED)
  const stateBadge = document.createElement('span');
  stateBadge.className = isNew ? 'profile-state-badge state-ready' : 'profile-state-badge state-idle';
  stateBadge.textContent = isNew ? 'SẴN SÀNG' : 'IDLE';

  // ===== Group editor panel (div) =====
  const groupPanel = document.createElement('div');
  groupPanel.className = 'group-panel';
  groupPanel.style.display = 'none';

  const groupPanelHeader = document.createElement('div');
  groupPanelHeader.className = 'group-panel-header';
  groupPanelHeader.textContent = 'Danh sách group (mỗi dòng 1 group)';

  const groupTextarea = document.createElement('textarea');
  groupTextarea.className = 'group-textarea';
  groupTextarea.placeholder = 'Dán group ở đây...\nVD:\nhttps://www.facebook.com/groups/tuyendungkisuIT\n3013041542259942';

  const groupPanelActions = document.createElement('div');
  groupPanelActions.className = 'group-panel-actions';

  const groupSaveBtn = document.createElement('button');
  groupSaveBtn.type = 'button';
  groupSaveBtn.className = 'btn-success';
  groupSaveBtn.textContent = 'Lưu groups';

  const groupCloseBtn = document.createElement('button');
  groupCloseBtn.type = 'button';
  groupCloseBtn.className = 'btn-secondary';
  groupCloseBtn.textContent = 'Đóng';

  groupPanelActions.appendChild(groupSaveBtn);
  groupPanelActions.appendChild(groupCloseBtn);
  groupPanel.appendChild(groupPanelHeader);
  groupPanel.appendChild(groupTextarea);
  groupPanel.appendChild(groupPanelActions);

  // ===== Token editor panel (div) =====
  const tokenPanel = document.createElement('div');
  tokenPanel.className = 'group-panel';
  tokenPanel.style.display = 'none';

  const tokenPanelHeader = document.createElement('div');
  tokenPanelHeader.className = 'group-panel-header';
  tokenPanelHeader.textContent = 'Nhập thông tin token cho profile';

  const tokenForm = document.createElement('div');
  tokenForm.style.cssText = 'display: flex; flex-direction: column; gap: 12px; padding: 0; margin-bottom: 0;';

  // Tạo 5 input fields
  const createTokenInput = (label, fieldName, placeholder) => {
    const container = document.createElement('div');
    container.style.cssText = 'display: flex; flex-direction: column; gap: 4px; padding: 0 0 8px 0;';
    
    const labelEl = document.createElement('label');
    labelEl.textContent = label;
    labelEl.style.cssText = 'font-weight: 600; color: #2d3748; font-size: 14px;';
    
    const input = document.createElement('input');
    input.type = 'text';
    input.name = fieldName;
    input.placeholder = placeholder;
    input.style.cssText = 'padding: 8px 12px; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 14px; width: 100%; box-sizing: border-box;';
    
    container.appendChild(labelEl);
    container.appendChild(input);
    return { container, input };
  };

  const accessTokenInput = createTokenInput('Access Token', 'access_token', 'Nhập access_token...');
  const fbDtsgInput = createTokenInput('FB DTSG', 'fb_dtsg', 'Nhập fb_dtsg...');
  const lsdInput = createTokenInput('LSD', 'lsd', 'Nhập lsd...');
  const spinRInput = createTokenInput('Spin R', 'spin_r', 'Nhập spin_r...');
  const spinTInput = createTokenInput('Spin T', 'spin_t', 'Nhập spin_t...');

  tokenForm.appendChild(accessTokenInput.container);
  tokenForm.appendChild(fbDtsgInput.container);
  tokenForm.appendChild(lsdInput.container);
  tokenForm.appendChild(spinRInput.container);
  tokenForm.appendChild(spinTInput.container);

  const tokenPanelActions = document.createElement('div');
  tokenPanelActions.className = 'group-panel-actions';

  const tokenSaveBtn = document.createElement('button');
  tokenSaveBtn.type = 'button';
  tokenSaveBtn.className = 'btn-success';
  tokenSaveBtn.textContent = 'Lưu token';

  const tokenCloseBtn = document.createElement('button');
  tokenCloseBtn.type = 'button';
  tokenCloseBtn.className = 'btn-secondary';
  tokenCloseBtn.textContent = 'Đóng';

  tokenPanelActions.appendChild(tokenSaveBtn);
  tokenPanelActions.appendChild(tokenCloseBtn);
  tokenPanel.appendChild(tokenPanelHeader);
  tokenPanel.appendChild(tokenForm);
  tokenPanel.appendChild(tokenPanelActions);

  function getLocalGroups(pid) {
    const info = profileState.profiles[pid] || {};
    const gs = info.groups;
    if (Array.isArray(gs)) return gs.map((x) => String(x || '').trim()).filter(Boolean);
    return [];
  }

  function setLocalGroups(pid, groups) {
    if (!profileState.profiles[pid]) {
      profileState.profiles[pid] = { 
        cookie: '', 
        access_token: '', 
        fb_dtsg: '', 
        lsd: '', 
        spin_r: '', 
        spin_t: '',
        groups: [] 
      };
    }
    profileState.profiles[pid].groups = Array.isArray(groups) ? groups : [];
  }

  function updateGroupBtnLabel() {
    const count = getLocalGroups(currentPid).length;
    groupBtn.textContent = count > 0 ? `Groups (${count})` : 'Groups';
  }
  // init label from initialInfo/profileState
  if (initialInfo && Array.isArray(initialInfo.groups)) {
    setLocalGroups(currentPid, initialInfo.groups);
  } else if (!profileState.profiles[currentPid]?.groups) {
    // ensure field exists
    setLocalGroups(currentPid, getLocalGroups(currentPid));
  }
  updateGroupBtnLabel();

  selectCb.addEventListener('change', () => {
    if (!profileState.selected || typeof profileState.selected !== 'object') profileState.selected = {};
    if (selectCb.checked) profileState.selected[currentPid] = true;
    else delete profileState.selected[currentPid];
    saveProfileState();
    updateSettingsActionButtons();
  });

  const cookieBtn = document.createElement('button');
  cookieBtn.type = 'button';
  cookieBtn.className = 'btn-primary';
  cookieBtn.textContent = 'Cập nhật cookie';

  const tokenBtn = document.createElement('button');
  tokenBtn.type = 'button';
  tokenBtn.className = 'btn-success';
  tokenBtn.textContent = 'Cập nhật token' ;

  groupBtn.addEventListener('click', async () => {
    const isOpen = groupPanel.style.display !== 'none';
    if (isOpen) {
      groupPanel.style.display = 'none';
      return;
    }

    // mở panel + load groups từ backend để textarea đúng dữ liệu hiện tại
    groupBtn.disabled = true;
    try {
      const settings = await callBackendNoAlert('/settings', { method: 'GET' });
      const profiles = (settings && (settings.PROFILE_IDS || settings.profile_ids)) || {};
      const cfg = (profiles && typeof profiles === 'object') ? profiles[currentPid] : null;
      const rawGroups = cfg && typeof cfg === 'object' ? cfg.groups : null;
      const groups = Array.isArray(rawGroups) ? rawGroups.map((x) => String(x || '').trim()).filter(Boolean) : [];
      setLocalGroups(currentPid, groups);
      saveProfileState();
      updateGroupBtnLabel();
      groupTextarea.value = groups.join('\n');
      groupPanel.style.display = 'block';
      groupTextarea.focus();
    } catch (e) {
      // fallback: hiện theo local nếu backend lỗi
      const groups = getLocalGroups(currentPid);
      groupTextarea.value = groups.join('\n');
      groupPanel.style.display = 'block';
      showToast('Không load được groups từ backend, đang dùng dữ liệu local.', 'error');
    } finally {
      groupBtn.disabled = false;
    }
  });

  groupCloseBtn.addEventListener('click', () => {
    groupPanel.style.display = 'none';
  });

  groupSaveBtn.addEventListener('click', async () => {
    const nextGroups = String(groupTextarea.value || '')
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);

    groupSaveBtn.disabled = true;
    try {
      // replace (đè lên cái cũ)
      const res = await callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}/groups`, {
        method: 'PUT',
        body: JSON.stringify({ groups: nextGroups }),
      });
      const saved = (res && Array.isArray(res.groups)) ? res.groups : nextGroups;
      setLocalGroups(currentPid, saved);
      saveProfileState();
      updateGroupBtnLabel();
      showToast(`Đã lưu groups: ${saved.length}`, 'success');
      // Lưu xong thì đóng textarea panel
      groupPanel.style.display = 'none';
    } catch (e) {
      showToast('Không lưu được groups (kiểm tra FastAPI).', 'error');
    } finally {
      groupSaveBtn.disabled = false;
    }
  });

  saveBtn.addEventListener('click', async () => {
    const nextPid = (pidInput.value || '').replace(/\s+/g, '').trim();
    if (!nextPid) {
      showToast('profile_id không được để trống', 'error');
      pidInput.value = currentPid;
      pidInput.focus();
      return;
    }
    // normalize hiển thị để tránh dính space
    if (pidInput.value !== nextPid) pidInput.value = nextPid;

    const cur = profileState.profiles[currentPid] || { 
      cookie: '', 
      access_token: '', 
      fb_dtsg: '', 
      lsd: '', 
      spin_r: '', 
      spin_t: '',
      groups: [] 
    };
    saveBtn.disabled = true;
    try {
      if (nextPid !== currentPid) {
        // rename = add new -> copy data -> delete old
        await callBackend('/settings/profiles', {
          method: 'POST',
          body: JSON.stringify({ profile_id: nextPid }),
        });
        await callBackend(`/settings/profiles/${encodeURIComponent(nextPid)}`, {
          method: 'PUT',
          body: JSON.stringify({
            cookie: cur.cookie || '',
            access_token: cur.access_token || '',
            fb_dtsg: cur.fb_dtsg || '',
            lsd: cur.lsd || '',
            spin_r: cur.spin_r || '',
            spin_t: cur.spin_t || '',
          }),
        });
        // copy groups sang profile mới (tránh mất)
        await callBackend(`/settings/profiles/${encodeURIComponent(nextPid)}/groups`, {
          method: 'PUT',
          body: JSON.stringify({ groups: Array.isArray(cur.groups) ? cur.groups : [] }),
        });
        await callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}`, { method: 'DELETE' });

        delete profileState.profiles[currentPid];
        profileState.profiles[nextPid] = { ...cur };
        // chuyển checkbox selection sang key mới
        if (profileState.selected && profileState.selected[currentPid]) {
          delete profileState.selected[currentPid];
          profileState.selected[nextPid] = true;
        }
        currentPid = nextPid;
        pidInput.value = currentPid;
        selectCb.checked = Boolean(profileState.selected && profileState.selected[currentPid]);
        updateGroupBtnLabel();
      } else {
        await callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}`, {
          method: 'PUT',
          body: JSON.stringify({
            cookie: cur.cookie || '',
            access_token: cur.access_token || '',
            fb_dtsg: cur.fb_dtsg || '',
            lsd: cur.lsd || '',
            spin_r: cur.spin_r || '',
            spin_t: cur.spin_t || '',
          }),
        });
      }

      saveProfileState();
      tokenBtn.textContent = (profileState.profiles[currentPid]?.access_token) ? 'Cập nhật token' : 'Lấy access_token';
      showToast('Đã lưu', 'success');
    } catch (e) {
      showToast('Không lưu được (kiểm tra FastAPI).', 'error');
      pidInput.value = currentPid;
    } finally {
      saveBtn.disabled = false;
    }
  });

  removeBtn.addEventListener('click', () => {
    if (!confirm(`Xóa profile ${currentPid}?`)) return;
    removeBtn.disabled = true;
    callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}`, { method: 'DELETE' })
      .then(() => {
        delete profileState.profiles[currentPid];
        saveProfileState();
        row.remove();
        setProfileListEmptyStateIfNeeded();
        showToast('Đã xóa', 'success');
      })
      .catch(() => showToast('Không xóa được (kiểm tra FastAPI).', 'error'))
      .finally(() => (removeBtn.disabled = false));
  });

  cookieBtn.addEventListener('click', () => {
    cookieBtn.disabled = true;
    showToast('Đang bật NST & lấy cookie...', 'success', 900);
    const safePid = String(currentPid || '').replace(/\s+/g, '');
    callBackend(`/settings/profiles/${encodeURIComponent(safePid)}/cookie/fetch`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
      .then(() => {
        // Cookie đã được backend lưu vào backend/config/settings.json, frontend không lưu/không hiển thị
        showToast('Đã lưu cookie vào settings.json', 'success');
      })
      .catch(() => showToast('Không lấy được cookie (kiểm tra FastAPI / đăng nhập NST).', 'error'))
      .finally(() => (cookieBtn.disabled = false));
  });

  tokenBtn.addEventListener('click', async () => {
    const isOpen = tokenPanel.style.display !== 'none';
    if (isOpen) {
      tokenPanel.style.display = 'none';
      return;
    }

    // Mở panel + load token data từ backend
    tokenBtn.disabled = true;
    try {
      const settings = await callBackendNoAlert('/settings', { method: 'GET' });
      const profiles = (settings && (settings.PROFILE_IDS || settings.profile_ids)) || {};
      const cfg = (profiles && typeof profiles === 'object') ? profiles[currentPid] : null;
      
      // Load giá trị hiện tại vào inputs
      accessTokenInput.input.value = (cfg && cfg.access_token) ? String(cfg.access_token) : '';
      fbDtsgInput.input.value = (cfg && cfg.fb_dtsg) ? String(cfg.fb_dtsg) : '';
      lsdInput.input.value = (cfg && cfg.lsd) ? String(cfg.lsd) : '';
      spinRInput.input.value = (cfg && cfg.spin_r) ? String(cfg.spin_r) : '';
      spinTInput.input.value = (cfg && cfg.spin_t) ? String(cfg.spin_t) : '';
      
      tokenPanel.style.display = 'block';
      accessTokenInput.input.focus();
    } catch (e) {
      // Fallback: load từ local state
      const info = profileState.profiles[currentPid] || {};
      accessTokenInput.input.value = info.access_token || '';
      fbDtsgInput.input.value = info.fb_dtsg || '';
      lsdInput.input.value = info.lsd || '';
      spinRInput.input.value = info.spin_r || '';
      spinTInput.input.value = info.spin_t || '';
      tokenPanel.style.display = 'block';
      accessTokenInput.input.focus();
      showToast('Không load được token từ backend, đang dùng dữ liệu local.', 'error');
    } finally {
      tokenBtn.disabled = false;
    }
  });

  tokenCloseBtn.addEventListener('click', () => {
    tokenPanel.style.display = 'none';
  });

  tokenSaveBtn.addEventListener('click', async () => {
    const accessToken = accessTokenInput.input.value.trim();
    const fbDtsg = fbDtsgInput.input.value.trim();
    const lsd = lsdInput.input.value.trim();
    const spinR = spinRInput.input.value.trim();
    const spinT = spinTInput.input.value.trim();

    tokenSaveBtn.disabled = true;
    try {
      await callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}`, {
        method: 'PUT',
        body: JSON.stringify({
          access_token: accessToken,
          fb_dtsg: fbDtsg,
          lsd: lsd,
          spin_r: spinR,
          spin_t: spinT,
        }),
      });
      
      // Update local state
      if (!profileState.profiles[currentPid]) {
        profileState.profiles[currentPid] = { 
          cookie: '', 
          access_token: '', 
          fb_dtsg: '', 
          lsd: '', 
          spin_r: '', 
          spin_t: '',
          groups: [] 
        };
      }
      profileState.profiles[currentPid].access_token = accessToken;
      profileState.profiles[currentPid].fb_dtsg = fbDtsg;
      profileState.profiles[currentPid].lsd = lsd;
      profileState.profiles[currentPid].spin_r = spinR;
      profileState.profiles[currentPid].spin_t = spinT;
      saveProfileState();
      
      tokenBtn.textContent = accessToken ? 'Cập nhật token' : 'Lấy access_token';
      showToast('Đã lưu token', 'success');
      tokenPanel.style.display = 'none';
    } catch (e) {
      showToast('Không lưu token (kiểm tra FastAPI).', 'error');
    } finally {
      tokenSaveBtn.disabled = false;
    }
  });

  actions.appendChild(stateBadge);
  actions.appendChild(saveBtn);
  actions.appendChild(removeBtn);
  actions.appendChild(groupBtn);
  actions.appendChild(cookieBtn);
  actions.appendChild(tokenBtn);

  selectWrap.appendChild(selectCb);
  row.appendChild(selectWrap);
  row.appendChild(pidInput);
  row.appendChild(actions);
  wrap.appendChild(row);
  wrap.appendChild(groupPanel);
  wrap.appendChild(tokenPanel);
  // init label
  try { updatePauseBtnLabel(); } catch (_) { }
  return wrap;
}

function renderProfileList() {
  if (!profileList) return;
  // nếu đang có row thêm mới, bỏ trước khi render lại
  if (addRowEl && addRowEl.parentNode) {
    addRowEl.parentNode.removeChild(addRowEl);
    addRowEl = null;
  }
  profileList.innerHTML = '';
  const ids = Object.keys(profileState.profiles || {});
  if (ids.length === 0) {
    profileList.classList.add('empty-state-box');
    profileList.innerHTML = '<p class="muted">Chưa có profile nào</p>';
    return;
  }

  profileList.classList.remove('empty-state-box');
  ids.forEach((pid) => {
    const info = profileState.profiles[pid] || {};
    profileList.appendChild(buildProfileRow(pid, info));
  });
  updateSettingsActionButtons();
}

function showAddProfileRow() {
  if (!profileList) return;
  if (addRowEl && addRowEl.parentNode) return;

  addRowEl = document.createElement('div');
  addRowEl.className = 'profile-row add-profile-form';

  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Nhập profile_id (UUID)';

  const saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  saveBtn.className = 'btn-success';
  saveBtn.textContent = 'Lưu';
  saveBtn.addEventListener('click', () => {
    const value = (input.value || '').trim();
    if (!value) {
      showToast('Vui lòng nhập profile_id', 'error');
      return;
    }
    callBackend('/settings/profiles', {
      method: 'POST',
      body: JSON.stringify({ profile_id: value }),
    })
      .then(() => {
        if (!profileState.profiles[value]) {
          profileState.profiles[value] = { 
            cookie: '', 
            access_token: '', 
            fb_dtsg: '', 
            lsd: '', 
            spin_r: '', 
            spin_t: '',
            groups: [] 
          };
        }
        saveProfileState();
        // Thêm row mới mà không render lại toàn bộ (tránh nháy)
        if (profileList.classList.contains('empty-state-box')) {
          profileList.classList.remove('empty-state-box');
          profileList.innerHTML = '';
        }
        const newRow = buildProfileRow(value, profileState.profiles[value], true); // true = isNew
        // insert trước addRowEl để form vẫn ở cuối
        profileList.insertBefore(newRow, addRowEl);
        // remove form add
        addRowEl.remove();
        addRowEl = null;
      })
      .catch(() => showToast('Không thêm được profile (kiểm tra FastAPI).', 'error'));
  });

  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'btn-secondary';
  cancelBtn.textContent = 'Hủy';
  cancelBtn.addEventListener('click', () => {
    if (addRowEl && addRowEl.parentNode) {
      addRowEl.parentNode.removeChild(addRowEl);
      addRowEl = null;
    }
  });

  addRowEl.appendChild(input);
  addRowEl.appendChild(saveBtn);
  addRowEl.appendChild(cancelBtn);
  // luôn để form ở cuối list
  if (profileList.classList.contains('empty-state-box')) {
    profileList.classList.remove('empty-state-box');
    profileList.innerHTML = '';
  }
  profileList.appendChild(addRowEl);
  input.focus();
}

if (saveApiKeyBtn) {
  saveApiKeyBtn.addEventListener('click', () => {
    profileState.apiKey = (settingApiKeyInput?.value || '').trim();
    // Lưu local trước để không mất dữ liệu nếu backend lỗi
    saveProfileState();

    callBackend('/settings/api-key', {
      method: 'PUT',
      body: JSON.stringify({ api_key: profileState.apiKey }),
    })
      .then(() => showToast('Đã lưu API Key', 'success'))
      .catch(() => {
        showToast('Không lưu được API Key (kiểm tra FastAPI).', 'error');
      });
  });
}

// Cleanup files button
const cleanupFilesBtn = document.getElementById('cleanupFilesBtn');
const cleanupStatus = document.getElementById('cleanupStatus');

if (cleanupFilesBtn) {
  cleanupFilesBtn.addEventListener('click', async () => {
    if (!cleanupStatus) return;

    // Disable button và hiển thị loading
    cleanupFilesBtn.disabled = true;
    cleanupFilesBtn.textContent = 'Đang dọn dẹp...';
    cleanupStatus.style.display = 'block';
    cleanupStatus.className = 'cleanup-status';
    cleanupStatus.textContent = 'Đang dọn dẹp file cũ...';

    try {
      const response = await callBackend('/cleanup/old-files', {
        method: 'POST',
        body: JSON.stringify({ max_days: 3 })
      });

      // Hiển thị kết quả
      cleanupStatus.className = 'cleanup-status success';
      cleanupStatus.textContent = `✅ ${response.message}`;

      // Hiển thị danh sách file đã xóa nếu có
      if (response.deleted_files && response.deleted_files.length > 0) {
        cleanupStatus.innerHTML += '<br><small>Files đã xóa:</small><ul>';
        response.deleted_files.forEach(filename => {
          cleanupStatus.innerHTML += `<li>${filename}</li>`;
        });
        cleanupStatus.innerHTML += '</ul>';
      }

      showToast(`Đã dọn dẹp ${response.deleted_count} file cũ`, 'success');

    } catch (error) {
      console.error('Lỗi khi dọn dẹp file:', error);
      cleanupStatus.className = 'cleanup-status error';
      cleanupStatus.textContent = '❌ Lỗi khi dọn dẹp file cũ';
      showToast('Lỗi khi dọn dẹp file cũ', 'error');
    } finally {
      // Reset button
      cleanupFilesBtn.disabled = false;
      cleanupFilesBtn.innerHTML = '🗑️ Dọn dẹp ngay';
    }
  });
}

if (addProfileRowBtn) {
  addProfileRowBtn.addEventListener('click', showAddProfileRow);
}

if (feedAccountSettingBtn) {
  feedAccountSettingBtn.addEventListener('click', () => {
    const selected = getSelectedProfileIds();
    if (selected.length === 0) {
      showToast('Hãy tick ít nhất 1 profile trước.', 'error');
      try { switchTab('settings'); } catch (_) { }
      return;
    }
    if (!feedConfigPanel) {
      showToast('Thiếu UI feedConfigPanel.', 'error');
      return;
    }
    // Nếu panel quét bài viết đang mở thì tắt đi để khỏi chồng UI
    if (scanConfigPanel) scanConfigPanel.style.display = 'none';
    // Nếu panel quét theo group đang mở thì tắt đi để khỏi chồng UI
    if (groupScanPanel) groupScanPanel.style.display = 'none';
    feedConfigPanel.style.display = (feedConfigPanel.style.display === 'none' || !feedConfigPanel.style.display) ? 'block' : 'none';
  });
}

if (feedCancelBtn && feedConfigPanel) {
  feedCancelBtn.addEventListener('click', () => {
    feedConfigPanel.style.display = 'none';
  });
}

if (feedStartBtn) {
  feedStartBtn.addEventListener('click', async () => {
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile để nuôi acc.', 'error');
      return;
    }

    const modeEl = document.querySelector('input[name="feedMode"]:checked');
    const mode = modeEl ? String(modeEl.value || 'feed') : 'feed';
    const text = String(feedTextInput?.value || '').trim();
    const runMinutes = parseInt(String(feedRunMinutesInput?.value || '30').trim(), 10);
    const restMinutes = parseInt(String(feedRestMinutesInput?.value || '0').trim(), 10);

    // Feed: cho phép text rỗng (quét theo keyword mặc định). Search: bắt buộc có text.
    if (!text && mode === 'search') {
      showToast('Search cần nhập text.', 'error');
      return;
    }
    if (!runMinutes || runMinutes <= 0) {
      showToast('Chạy (phút) không hợp lệ.', 'error');
      return;
    }
    if (!Number.isFinite(restMinutes) || restMinutes < 0) {
      showToast('Nghỉ (phút) không hợp lệ.', 'error');
      return;
    }

    setButtonLoading(feedStartBtn, true, 'Đang chạy...');
    setButtonLoading(feedAccountSettingBtn, true, 'Đang nuôi acc...');
    try {
      const res = await callBackend('/feed/start', {
        method: 'POST',
        body: JSON.stringify({
          profile_ids: selected,
          mode,
          text,
          run_minutes: runMinutes,
          rest_minutes: restMinutes,
        }),
      });
      const started = res && Array.isArray(res.started) ? res.started.length : 0;
      const skipped = res && Array.isArray(res.skipped) ? res.skipped.length : 0;
      const loopText = (restMinutes > 0) ? ` (loop: ${runMinutes}p / nghỉ ${restMinutes}p)` : '';
      showToast(`Đã chạy nuôi acc (${mode})${loopText}: started=${started}, skipped=${skipped}`, 'success', 2600);
      if (feedConfigPanel) feedConfigPanel.style.display = 'none';

      // Nếu chạy vòng lặp (restMinutes > 0) thì coi như chạy liên tục -> không poll "hoàn thành"
      if (restMinutes <= 0) {
        if (feedPollTimer) clearInterval(feedPollTimer);
        feedPollTimer = setInterval(async () => {
          try {
            const st = await callBackendNoAlert('/feed/status', { method: 'GET' });
            const running = (st && Array.isArray(st.running)) ? st.running : [];
            const still = selected.filter((pid) => running.includes(pid));
            if (still.length === 0) {
              clearInterval(feedPollTimer);
              feedPollTimer = null;
              setButtonLoading(feedStartBtn, false);
              setButtonLoading(feedAccountSettingBtn, false);
              showToast('✅ Nuôi acc: Hoàn thành', 'success', 2000);
            }
          } catch (e) {
            clearInterval(feedPollTimer);
            feedPollTimer = null;
            setButtonLoading(feedStartBtn, false);
            setButtonLoading(feedAccountSettingBtn, false);
            showToast('Không lấy được trạng thái nuôi acc (kiểm tra FastAPI).', 'error');
          }
        }, 4000);
      }
    } catch (e) {
      setButtonLoading(feedStartBtn, false);
      setButtonLoading(feedAccountSettingBtn, false);
      showToast('Không chạy được nuôi acc (kiểm tra FastAPI).', 'error');
    }
  });
}

if (autoJoinGroupBtn) {
  autoJoinGroupBtn.addEventListener('click', async () => {
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile để auto join group.', 'error');
      return;
    }

    // Spinner + thông báo
    setButtonLoading(autoJoinGroupBtn, true, 'Đang auto join...');
    try {
      const res = await callBackend('/groups/join', {
        method: 'POST',
        body: JSON.stringify({ profile_ids: selected }),
      });
      const started = res && Array.isArray(res.started) ? res.started.length : 0;
      const skipped = res && Array.isArray(res.skipped) ? res.skipped.length : 0;
      showToast(`Đã chạy auto join group: started=${started}, skipped=${skipped}`, 'success', 2200);

      // Poll đến khi hoàn tất (running không còn các profile đã chọn)
      if (joinGroupPollTimer) clearInterval(joinGroupPollTimer);
      joinGroupPollTimer = setInterval(async () => {
        try {
          const st = await callBackendNoAlert('/groups/join/status', { method: 'GET' });
          const running = (st && Array.isArray(st.running)) ? st.running : [];
          const still = selected.filter((pid) => running.includes(pid));
          if (still.length === 0) {
            clearInterval(joinGroupPollTimer);
            joinGroupPollTimer = null;
            setButtonLoading(autoJoinGroupBtn, false);
            showToast('✅ Auto join group: Hoàn thành', 'success', 2000);
          }
        } catch (e) {
          // Nếu lỗi poll thì dừng poll để không spam
          clearInterval(joinGroupPollTimer);
          joinGroupPollTimer = null;
          setButtonLoading(autoJoinGroupBtn, false);
          showToast('Không lấy được trạng thái auto join (kiểm tra FastAPI).', 'error');
        }
      }, 4000);
    } catch (e) {
      showToast('Không chạy được auto join group (kiểm tra FastAPI).', 'error');
      setButtonLoading(autoJoinGroupBtn, false);
    }
  });
}

// Nút "Quét bài viết" trong tab Setting profile
if (scanPostsSettingBtn) {
  scanPostsSettingBtn.addEventListener('click', () => {
    const selected = getSelectedProfileIds();
    if (selected.length === 0) {
      showToast('Hãy tick ít nhất 1 profile trước.', 'error');
      try { switchTab('settings'); } catch (_) { }
      return;
    }
    if (!scanConfigPanel) {
      showToast('Thiếu UI scanConfigPanel.', 'error');
      return;
    }
    // Đóng panel nuôi acc nếu đang mở để khỏi rối
    if (feedConfigPanel) feedConfigPanel.style.display = 'none';
    // Đóng panel quét theo group nếu đang mở
    if (groupScanPanel) groupScanPanel.style.display = 'none';
    const isOpen = scanConfigPanel.style.display !== 'none';
    scanConfigPanel.style.display = isOpen ? 'none' : 'block';
  });
}

if (scanCancelBtn && scanConfigPanel) {
  scanCancelBtn.addEventListener('click', () => {
    scanConfigPanel.style.display = 'none';
  });
}

// Nút "Quét theo group" (UI only)
if (scanGroupSettingBtn) {
  scanGroupSettingBtn.addEventListener('click', () => {
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile trước.', 'error');
      try { switchTab('settings'); } catch (_) { }
      return;
    }
    if (!groupScanPanel) {
      showToast('Thiếu UI groupScanPanel.', 'error');
      return;
    }
    // Đóng các panel khác để khỏi chồng UI
    if (feedConfigPanel) feedConfigPanel.style.display = 'none';
    if (scanConfigPanel) scanConfigPanel.style.display = 'none';

    const isOpen = groupScanPanel.style.display !== 'none';
    groupScanPanel.style.display = isOpen ? 'none' : 'block';
  });
}

if (groupScanCancelBtn && groupScanPanel) {
  groupScanCancelBtn.addEventListener('click', () => {
    groupScanPanel.style.display = 'none';
  });
}

// UI only: bấm "Chạy" thì chỉ validate + toast (chưa gọi API)
if (groupScanStartBtn) {
  groupScanStartBtn.addEventListener('click', async () => {
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile trước.', 'error');
      return;
    }
    const postCount = parseInt(String(groupScanPostCountInput?.value || '0').trim(), 10);
    const startDate = String(groupScanStartDateInput?.value || '').trim();
    const endDate = String(groupScanEndDateInput?.value || '').trim();
    
    if (!Number.isFinite(postCount) || postCount <= 0) {
      showToast('Số bài viết theo dõi phải lớn hơn 0.', 'error');
      return;
    }
    if (!startDate || !endDate) {
      showToast('Nhập đủ ngày bắt đầu và ngày kết thúc.', 'error');
      return;
    }
    
    // Parse date (YYYY-MM-DD format)
    const startTs = Date.parse(startDate + 'T00:00:00');
    const endTs = Date.parse(endDate + 'T23:59:59');
    if (!Number.isFinite(startTs) || !Number.isFinite(endTs)) {
      showToast('Ngày không hợp lệ.', 'error');
      return;
    }
    if (startTs > endTs) {
      showToast('Ngày bắt đầu phải ≤ ngày kết thúc.', 'error');
      return;
    }

    // Disable button và hiển thị loading với spinner
    setButtonLoading(groupScanStartBtn, true, 'Đang xử lý...');
    
    try {
      const response = await fetch('http://localhost:8000/scan-groups', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          profile_ids: selected,
          post_count: postCount,
          start_date: startDate,
          end_date: endDate
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Lỗi không xác định');
      }

      showToast(
        `✅ Đã thêm ${selected.length} profile vào hàng chờ quét group. Số bài: ${postCount}, từ ${startDate} đến ${endDate}`,
        'success',
        4000
      );
      
      // Đóng panel sau khi thành công
      if (groupScanPanel) {
        groupScanPanel.style.display = 'none';
      }
      
    } catch (error) {
      console.error('Lỗi khi quét group:', error);
      showToast(`❌ Lỗi: ${error.message}`, 'error', 4000);
    } finally {
      // Restore button
      setButtonLoading(groupScanStartBtn, false);
    }
  });
}

if (scanStartBtn) {
  scanStartBtn.addEventListener('click', async () => {
    // Nếu đang quét thì không cho bấm lại
    if (isScanning) {
      showToast('Đang quét, vui lòng đợi hoặc bấm dừng trước', 'warning');
      return;
    }
    
    // Nếu nút đang loading thì không cho bấm lại
    if (scanStartBtn.classList.contains('btn-loading')) {
      return;
    }
    
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile để quét bài viết.', 'error');
      try { switchTab('settings'); } catch (_) { }
      return;
    }

    const runMinutes = parseInt(String(scanRunMinutesInput?.value || '0').trim(), 10);
    const restMinutes = parseInt(String(scanRestMinutesInput?.value || '0').trim(), 10);
    const text = String(scanTextInput?.value || '').trim();
    const mode = String(document.querySelector('input[name="scanMode"]:checked')?.value || 'feed').trim().toLowerCase();

    if (mode === 'search' && !text) {
      showToast('Search cần nhập text để search.', 'error');
      return;
    }

    setButtonLoading(scanStartBtn, true, 'Đang chạy...');
    setButtonLoading(scanPostsSettingBtn, true, 'Đang quét...');
    try {
      await startScanFlow({ runMinutes, restMinutes, text, mode });
      // đóng panel sau khi chạy
      if (scanConfigPanel) scanConfigPanel.style.display = 'none';
    } catch (e) {
      showToast('Không chạy được quét bài viết (kiểm tra FastAPI).', 'error');
      setButtonLoading(scanStartBtn, false);
      setButtonLoading(scanPostsSettingBtn, false);
      setScanning(false);
    }
    // Không reset loading ở đây vì setScanning(true) sẽ giữ trạng thái
  });
}

/**
 * Helper function để reset info collector state
 */
function resetInfoCollectorState() {
  isInfoCollectorRunning = false;
  // Reset loading của các nút info collector
  if (runAllInfoBtn) setButtonLoading(runAllInfoBtn, false);
  if (runSelectedInfoBtn) setButtonLoading(runSelectedInfoBtn, false);
  // Dừng poll tiến trình
  if (infoProgressInterval) {
    clearInterval(infoProgressInterval);
    infoProgressInterval = null;
  }
  // Ẩn toast tiến trình
  const infoToast = document.getElementById('infoProgressToast');
  const progressToast = document.getElementById('progressToast');
  if (infoToast) infoToast.style.display = 'none';
  // Ẩn progressToast nếu cả 2 toast đều ẩn
  const scanToast = document.getElementById('scanStatsToast');
  if (progressToast && (!scanToast || scanToast.style.display === 'none')) {
    progressToast.style.display = 'none';
  }
}

async function handleStopAll() {
  console.log('[UI] STOP ALL triggered');
  
  // Reset info collector state ngay lập tức
  resetInfoCollectorState();
  
  // stop-all có thể bấm từ left panel hoặc từ setting header
  const btns = [stopAllBtn, stopAllSettingBtn].filter(Boolean);
  btns.forEach((b) => setButtonLoading(b, true, 'Đang dừng tất cả...'));
  
  try {
    // Ưu tiên endpoint mới theo spec, fallback endpoint cũ để khỏi vỡ UI
    let res = null;
    try {
      res = await callBackend('/control/stop-all', { method: 'POST' });
    } catch (_) {
      res = await callBackend('/jobs/stop-all', { method: 'POST' }); // backward-compat
    }
    const botStopped = res && res.stopped ? Boolean(res.stopped.bot) : false;
    const joinStopped = res && res.stopped && Array.isArray(res.stopped.join_groups) ? res.stopped.join_groups.length : 0;
    const nstOk = res && Array.isArray(res.nst_stop_ok) ? res.nst_stop_ok.length : 0;
    const nstAttempted = res && Array.isArray(res.nst_stop_attempted) ? res.nst_stop_attempted.length : 0;
    const nstAll = res && typeof res.nst_stop_all_ok === 'boolean' ? res.nst_stop_all_ok : false;
    showToast(`Đã dừng tất cả: bot=${botStopped ? 'OK' : 'NO'}, join_groups=${joinStopped}, NST=${nstOk}/${nstAttempted}${nstAll ? ' +ALL' : ''}`, 'success', 2800);
  } catch (e) {
    showToast('Không dừng được tất cả (kiểm tra FastAPI).', 'error');
  } finally {
    // Reset UI quét (tránh kẹt spinner nếu user dừng bằng stop-all)
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    if (dataCheckInterval) {
      clearInterval(dataCheckInterval);
      dataCheckInterval = null;
    }
    setScanning(false);
    setButtonLoading(scanStartBtn, false);
    setButtonLoading(scanPostsSettingBtn, false);
    // stopBtn đã bị xóa khỏi left-panel

    btns.forEach((b) => setButtonLoading(b, false));
    if (joinGroupPollTimer) {
      clearInterval(joinGroupPollTimer);
      joinGroupPollTimer = null;
    }
    if (feedPollTimer) {
      clearInterval(feedPollTimer);
      feedPollTimer = null;
    }
    setButtonLoading(autoJoinGroupBtn, false);
    setButtonLoading(feedAccountSettingBtn, false);
    setButtonLoading(feedStartBtn, false);
    if (feedConfigPanel) feedConfigPanel.style.display = 'none';
    
    // Refresh state và update buttons
    try {
      const jobs = await callBackendNoAlert('/jobs/status', { method: 'GET' });
      if (jobs) lastJobsStatus = jobs;
    } catch (_) { }
    try { await refreshControlState(); } catch (_) { }
    updateStopPauseButtonsByJobs(); // Update buttons sau khi reset state
  }
}

async function handleStopSelectedProfiles() {
  const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
  if (selected.length === 0) {
    showToast('Chọn (tick) ít nhất 1 profile để dừng.', 'error');
    return;
  }
  if (!stopSelectedProfilesBtn) return;
  if (stopSelectedProfilesBtn.classList.contains('btn-loading')) return;

  // Reset info collector state nếu đang chạy (có thể stop info collector)
  resetInfoCollectorState();
  
  console.log(`[UI] STOP selected profiles=${selected.join(',')}`);
  setButtonLoading(stopSelectedProfilesBtn, true, 'Đang dừng...');

  try {
    const res = await callBackend('/control/stop-profiles', {
      method: 'POST',
      body: JSON.stringify({ profile_ids: selected }),
    });

    const okCount = res && Array.isArray(res.nst_ok) ? res.nst_ok.length : 0;
    const failCount = res && Array.isArray(res.nst_fail) ? res.nst_fail.length : 0;
    showToast(`Đã dừng ${selected.length} profile (NST ok=${okCount}, fail=${failCount})`, 'success', 2400);

    // Refresh state để badge về SẴN SÀNG ngay
    try {
      const jobs = await callBackendNoAlert('/jobs/status', { method: 'GET' });
      if (jobs) lastJobsStatus = jobs;
    } catch (_) { }
    try { await refreshControlState(); } catch (_) { }
    updateStopPauseButtonsByJobs(); // Update buttons sau khi refresh state
    // Nếu không còn bot_profile_ids thì UI quét phải về "Sẵn sàng"
    try {
      const botHasProfiles = Array.isArray(lastJobsStatus && lastJobsStatus.bot_profile_ids) && lastJobsStatus.bot_profile_ids.length > 0;
      if (!botHasProfiles) {
        if (dataCheckInterval) { clearInterval(dataCheckInterval); dataCheckInterval = null; }
        setScanning(false);
        setButtonLoading(scanStartBtn, false);
        setButtonLoading(scanPostsSettingBtn, false);
      }
    } catch (_) { }
  } catch (e) {
    showToast('Không dừng được profile đã chọn (kiểm tra FastAPI).', 'error');
  } finally {
    setButtonLoading(stopSelectedProfilesBtn, false);
    updateStopPauseButtonsByJobs(); // Update buttons sau khi hoàn thành
  }
}

if (stopSelectedProfilesBtn) {
  stopSelectedProfilesBtn.addEventListener('click', handleStopSelectedProfiles);
}

async function handlePauseSelectedProfiles() {
  const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
  if (selected.length === 0) {
    showToast('Chọn (tick) ít nhất 1 profile để pause.', 'error');
    return;
  }
  if (!pauseSelectedProfilesBtn) return;
  if (pauseSelectedProfilesBtn.classList.contains('btn-loading')) return;

  // Toggle: nếu có ít nhất 1 profile đang paused -> RESUME, ngược lại -> PAUSE
  const st0 = await callBackendNoAlert('/control/state', { method: 'GET' });
  const pausedSet = new Set(Array.isArray(st0 && st0.paused_profiles) ? st0.paused_profiles.map((x) => String(x)) : []);
  const anyPaused = selected.some((pid) => pausedSet.has(String(pid)));
  const action = anyPaused ? 'RESUME' : 'PAUSE';
  console.log(`[UI] ${action} selected profiles=${selected.join(',')}`);
  setButtonLoading(pauseSelectedProfilesBtn, true, anyPaused ? 'Đang tiếp tục...' : 'Đang tạm dừng...');
  try {
    const endpoint = anyPaused ? '/control/resume-profiles' : '/control/pause-profiles';
    await callBackend(endpoint, { method: 'POST', body: JSON.stringify({ profile_ids: selected }) });
    showToast(anyPaused ? `Đã tiếp tục ${selected.length} profile` : `Đã tạm dừng ${selected.length} profile`, 'success', 2200);
  } catch (e) {
    showToast('Không pause được profile đã tick (kiểm tra FastAPI).', 'error');
  } finally {
    setButtonLoading(pauseSelectedProfilesBtn, false);
    try { 
      await refreshControlState(); 
      updateStopPauseButtonsByJobs(); // Update buttons sau khi refresh state
    } catch (_) { }
  }
}

if (pauseSelectedProfilesBtn) {
  pauseSelectedProfilesBtn.addEventListener('click', handlePauseSelectedProfiles);
}

async function refreshControlState() {
  try {
    const st = await callBackendNoAlert('/control/state', { method: 'GET' });
    if (!st) return;
    isPausedAll = Boolean(st.global_pause);
    try { updateSettingsActionButtons(); } catch (_) { }
    try { syncRunningLabelsWithPauseState(); } catch (_) { }
    setPauseAllButtonLabel(isPausedAll);
    try { applyControlStateToProfileRows(st); } catch (_) { }
    try { updateStopPauseButtonsByJobs(); } catch (_) { }
    // Update label của nút pause-selected theo trạng thái paused_profiles
    try {
      if (pauseSelectedProfilesBtn && !pauseSelectedProfilesBtn.classList.contains('btn-loading')) {
        const selected = getSelectedProfileIds();
        const pausedSet = new Set(Array.isArray(st.paused_profiles) ? st.paused_profiles.map((x) => String(x)) : []);
        const anyPaused = selected.some((pid) => pausedSet.has(String(pid)));
        pauseSelectedProfilesBtn.textContent = anyPaused ? 'Tiếp tục profile đã chọn' : 'Tạm dừng profile đã chọn';
      }
    } catch (_) { }
  } catch (_) { }
}

function _clearIntervalSafe(kind) {
  try {
    if (kind === 'scan' && scanBackendPollTimer) clearInterval(scanBackendPollTimer);
    if (kind === 'join' && joinGroupPollTimer) clearInterval(joinGroupPollTimer);
    if (kind === 'feed' && feedPollTimer) clearInterval(feedPollTimer);
  } catch (_) { }
  if (kind === 'scan') scanBackendPollTimer = null;
  if (kind === 'join') joinGroupPollTimer = null;
  if (kind === 'feed') feedPollTimer = null;
}

function startScanBackendPoll({ silent = true } = {}) {
  _clearIntervalSafe('scan');
  scanBackendPollTimer = setInterval(async () => {
    const st = await callBackendNoAlert('/jobs/status', { method: 'GET' });
    if (st) lastJobsStatus = st;
    updateStopPauseButtonsByJobs();
    const botHasProfiles = Array.isArray(st && st.bot_profile_ids) && st.bot_profile_ids.length > 0;
    const running = !!(st && st.bot_running && botHasProfiles);
    if (!running) {
      _clearIntervalSafe('scan');
      if (dataCheckInterval) {
        clearInterval(dataCheckInterval);
        dataCheckInterval = null;
      }
      setScanning(false);
      setButtonLoading(scanStartBtn, false);
      setButtonLoading(scanPostsSettingBtn, false);
      if (!silent) showToast('✅ Quét: Hoàn thành', 'success', 1800);
    } else {
      syncRunningLabelsWithPauseState();
      try { refreshControlState(); } catch (_) { }
    }
  }, 4000);
}

function startJoinBackendPoll({ silent = true } = {}) {
  _clearIntervalSafe('join');
  joinGroupPollTimer = setInterval(async () => {
    const st = await callBackendNoAlert('/jobs/status', { method: 'GET' });
    if (st) lastJobsStatus = st;
    updateStopPauseButtonsByJobs();
    const running = (st && Array.isArray(st.join_groups_running)) ? st.join_groups_running : [];
    if (running.length === 0) {
      _clearIntervalSafe('join');
      setButtonLoading(autoJoinGroupBtn, false);
      if (!silent) showToast('✅ Auto join group: Hoàn thành', 'success', 1800);
    } else {
      syncRunningLabelsWithPauseState();
      try { refreshControlState(); } catch (_) { }
    }
  }, 4000);
}

function startFeedBackendPoll({ silent = true } = {}) {
  _clearIntervalSafe('feed');
  feedPollTimer = setInterval(async () => {
    const st = await callBackendNoAlert('/jobs/status', { method: 'GET' });
    if (st) lastJobsStatus = st;
    updateStopPauseButtonsByJobs();
    const running = (st && Array.isArray(st.feed_running)) ? st.feed_running : [];
    if (running.length === 0) {
      _clearIntervalSafe('feed');
      setButtonLoading(feedStartBtn, false);
      setButtonLoading(feedAccountSettingBtn, false);
      if (!silent) showToast('✅ Nuôi acc: Hoàn thành', 'success', 1800);
    } else {
      syncRunningLabelsWithPauseState();
      try { refreshControlState(); } catch (_) { }
    }
  }, 4000);
}

async function resyncUiFromBackendAfterReload() {
  // Sync pause state trước để label chuẩn
  await refreshControlState();

  const jobs = await callBackendNoAlert('/jobs/status', { method: 'GET' });
  if (!jobs) return;
  lastJobsStatus = jobs;
  updateStopPauseButtonsByJobs();

  // --- Scan (AppRunner) ---
  if (jobs.bot_running) {
    setScanning(true);
    setButtonLoading(scanStartBtn, true, isPausedAll ? 'Đang tạm dừng...' : 'Đang chạy...');
    setButtonLoading(scanPostsSettingBtn, true, isPausedAll ? 'Đang tạm dừng...' : 'Đang quét...');
    if (!dataCheckInterval) dataCheckInterval = setInterval(checkForNewData, 5000);
    startScanBackendPoll({ silent: true });
  } else {
    setScanning(false);
    setButtonLoading(scanStartBtn, false);
    setButtonLoading(scanPostsSettingBtn, false);
    _clearIntervalSafe('scan');
  }

  // --- Join groups ---
  const joinRunning = Array.isArray(jobs.join_groups_running) ? jobs.join_groups_running : [];
  if (joinRunning.length > 0) {
    setButtonLoading(autoJoinGroupBtn, true, isPausedAll ? 'Đang tạm dừng...' : 'Đang auto join...');
    startJoinBackendPoll({ silent: true });
  } else {
    setButtonLoading(autoJoinGroupBtn, false);
    _clearIntervalSafe('join');
  }

  // --- Feed ---
  const feedRunning = Array.isArray(jobs.feed_running) ? jobs.feed_running : [];
  if (feedRunning.length > 0) {
    setButtonLoading(feedStartBtn, true, isPausedAll ? 'Đang tạm dừng...' : 'Đang chạy...');
    setButtonLoading(feedAccountSettingBtn, true, isPausedAll ? 'Đang tạm dừng...' : 'Đang nuôi acc...');
    startFeedBackendPoll({ silent: true });
  } else {
    setButtonLoading(feedStartBtn, false);
    setButtonLoading(feedAccountSettingBtn, false);
    _clearIntervalSafe('feed');
  }

  syncRunningLabelsWithPauseState();
  // Re-apply control state sau khi đã có lastJobsStatus để badge không bị sai lúc vừa vào trang
  try { await refreshControlState(); } catch (_) { }
}

async function handlePauseAllToggle() {
  if (!pauseAllBtn) return;
  if (pauseAllBtn.classList.contains('btn-loading')) return;
  
  const wasPaused = isPausedAll;
  
  try {
    if (!wasPaused) {
      console.log('[UI] PAUSE ALL triggered');
      setButtonLoading(pauseAllBtn, true, 'Đang tạm dừng...');
      // update UI ngay để tránh user thấy "đang quét" khi đã pause
      isPausedAll = true;
      syncRunningLabelsWithPauseState();
      await callBackend('/control/pause-all', { method: 'POST' });
      showToast('Đã tạm dừng tất cả', 'success');
    } else {
      console.log('[UI] RESUME ALL triggered');
      setButtonLoading(pauseAllBtn, true, 'Đang tiếp tục...');
      isPausedAll = false;
      syncRunningLabelsWithPauseState();
      await callBackend('/control/resume-all', { method: 'POST' });
      showToast('Đã tiếp tục tất cả', 'success');
    }
  } catch (e) {
    // Rollback UI state nếu có lỗi
    isPausedAll = wasPaused;
    syncRunningLabelsWithPauseState();
    showToast('Không pause/resume được (kiểm tra FastAPI).', 'error');
  } finally {
    setButtonLoading(pauseAllBtn, false);
    await refreshControlState();
    updateStopPauseButtonsByJobs(); // Update buttons sau khi refresh state
  }
}

if (pauseAllBtn) {
  pauseAllBtn.addEventListener('click', handlePauseAllToggle);
}

if (stopAllBtn) {
  stopAllBtn.addEventListener('click', handleStopAll);
}

if (stopAllSettingBtn) {
  stopAllSettingBtn.addEventListener('click', handleStopAll);
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

  // Lưu timestamp để sắp xếp
  const timestamp = parseTime(time || '');
  tr.dataset.timestamp = timestamp;
  tr.dataset.hasReact = react ? 'true' : 'false';
  tr.dataset.hasComment = hasComment ? 'true' : 'false';

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
    commentCell.dataset.showingText = 'false'; // Trạng thái: false = đang hiển thị icon, true = đang hiển thị text

    const eyeBtn = commentCell.querySelector('.comment-eye-btn');
    if (eyeBtn) {
      // Hàm toggle giữa icon và text
      const toggleComment = (e) => {
        if (e) e.stopPropagation();
        const text = commentCell.dataset.comment || '';
        if (!text) return;

        const isShowingText = commentCell.dataset.showingText === 'true';

        if (isShowingText) {
          // Đang hiển thị text → chuyển về icon
          commentCell.innerHTML = '<button class="comment-eye-btn" type="button" title="Xem comment">👁</button>';
          commentCell.dataset.showingText = 'false';
          // Gắn lại event listener cho icon mới
          const newEyeBtn = commentCell.querySelector('.comment-eye-btn');
          if (newEyeBtn) {
            newEyeBtn.addEventListener('click', toggleComment);
          }
        } else {
          // Đang hiển thị icon → chuyển sang text
          commentCell.innerHTML = `<span class="comment-text" style="cursor: pointer; color: var(--text-primary);">${text}</span>`;
          commentCell.dataset.showingText = 'true';
          // Gắn event listener cho text để click lại sẽ hiện icon
          const commentText = commentCell.querySelector('.comment-text');
          if (commentText) {
            commentText.addEventListener('click', toggleComment);
          }
        }
      };

      eyeBtn.addEventListener('click', toggleComment);
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
function appendPostRow(item) {
  if (!postTableBody) return;
  const flag = item.flag || '';
  const type = mapFlagToType(flag);
  const typeClass = getTypeColorClass(type);
  const tr = document.createElement('tr');
  const postId = item.post_id || '';
  const text = item.text || '';

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
    const res = await callBackend('/data/latest-results', { method: 'GET' });
    const data = res.data;

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

      // Nếu không có user nào interact, hiển thị post với thông tin owner
      if (allUserIds.size === 0) {
        const owner = post.owning_profile || {};
        const ownerId = owner.id || 'unknown';
        const ownerName = owner.name || 'Unknown User';
        const uniqueKey = `${postId}_${ownerId}`;

        if (!loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: ownerId,
            name: ownerName,
            react: false,
            comment: '',
            time: defaultTime,
            type: type,
          });
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      }

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
    // Gọi API để lấy file JSON có timestamp lớn nhất
    const res = await callBackend('/data/latest-results', { method: 'GET' });
    const data = res.data;
    console.log(`Đã load file JSON gần nhất: ${res.filename}, tổng số files:`, data.total_files);

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

      // Nếu không có user nào interact, hiển thị post với thông tin owner
      if (allUserIds.size === 0) {
        const owner = post.owning_profile || {};
        const ownerId = owner.id || 'unknown';
        const ownerName = owner.name || 'Unknown User';
        const uniqueKey = `${postId}_${ownerId}`;

        if (!loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: ownerId,
            name: ownerName,
            react: false,
            comment: '',
            time: defaultTime,
            type: type,
          });
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      }

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
    console.error('Không tải được file JSON từ API:', err);
    // Fallback: thử load data.json cũ (nếu API không khả dụng)
    try {
      const res = await fetch('data.json');
      if (res.ok) {
        const rows = await res.json();
        rows.forEach((row) => {
          appendRow(row);
          counter = Math.max(counter, Number(row.id) + 1);
        });
        initialLoaded = true;
        console.log('Đã load fallback data.json');
      }
    } catch (fallbackErr) {
      console.error('Không tải được data.json fallback:', fallbackErr);
      showToast('Không tìm thấy dữ liệu bài viết để hiển thị', 'error', 4000);
    }
  }

  // Show empty state if no rows
  if (tbody.children.length === 0) {
    emptyState.classList.add('show');
  }
}

// ==========================
// CẢNH BÁO ACCOUNT CÓ VẤN ĐỀ
// ==========================
async function pollAccountStatus() {
  try {
    const res = await callBackendNoAlert('/account/status', { method: 'GET' });
    if (!res || !res.accounts) return;

    const accounts = res.accounts || {};
    Object.keys(accounts).forEach((pid) => {
      const info = accounts[pid];
      if (!info) return;
      if (!info.banned) return;

      const msg = info.message || 'Tài khoản có vấn đề, hãy kiểm tra lại bằng tay.';
      showToast(`Profile ${pid}: ${msg}`, 'warning', 10000);
    });
  } catch (e) {
    // bỏ qua lỗi, không ảnh hưởng luồng cũ
  }
}

// Poll mỗi 45s, hoàn toàn độc lập, chỉ hiển thị thông báo
try {
  setInterval(pollAccountStatus, 45000);
} catch (_) { }

// Start quét bài viết (dùng chung cho nút "Bắt đầu quét" và nút trong tab Setting profile)
async function startScanFlow(options = {}) {
  // Nếu đang quét thì không cho chạy lại
  if (isScanning) {
    showToast('Đang quét, vui lòng đợi hoặc bấm dừng trước', 'warning');
    return;
  }
  
  const {
    runMinutes,
    restMinutes,
    text,
    mode,
  } = options || {};
  
  try {
    // Load và hiển thị tất cả dữ liệu từ all_results_summary.json ngay lập tức
    // Không cần chờ backend, hiển thị dữ liệu trước
    await loadInitialData();

    // Nếu đang có interval check data cũ thì clear trước để tránh setInterval chồng
    if (dataCheckInterval) {
      clearInterval(dataCheckInterval);
      dataCheckInterval = null;
    }

    // Sau đó mới chạy backend (nếu cần)
    const ok = await triggerBackendRun({ runMinutes, restMinutes, text, mode });
    if (!ok) {
      setScanning(false);
      return;
    }

    // Tự động kiểm tra dữ liệu mới mỗi 5 giây để cập nhật khi có dữ liệu mới
    const checkInterval = 5000; // 5 giây
    dataCheckInterval = setInterval(checkForNewData, checkInterval);

    setScanning(true);
    
    // Bắt đầu poll số bài đã quét được
    if (scanStatsInterval) clearInterval(scanStatsInterval);
    updateScanStats(); // Cập nhật ngay lập tức
    scanStatsInterval = setInterval(updateScanStats, 3000); // Poll mỗi 3 giây
    
    // Poll /jobs/status để sync UI nút dừng/tạm dừng + tự tắt khi backend dừng
    try { startScanBackendPoll({ silent: true }); } catch (_) { }
    try { updateStopPauseButtonsByJobs(); } catch (_) { }
    try { await refreshControlState(); } catch (_) { }
  } catch (err) {
    console.error('Lỗi trong startScanFlow:', err);
    setScanning(false);
    throw err;
  }
}

// Event listeners cho startBtn và stopBtn đã bị xóa vì left-panel không còn tồn tại

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
  table.querySelectorAll('tbody tr').forEach((tr, rowIndex) => {
    const row = [];
    tr.querySelectorAll('td').forEach((td, colIndex) => {
      // Cột thứ 1 (index 0) là ID Bài Post - tạo hyperlink đến bài post
      if (colIndex === 0 && td.textContent.trim()) {
        const postId = td.textContent.trim();
        const postUrl = `https://www.facebook.com/${postId}`;
        // Tạo hyperlink trong Excel
        row.push({
          t: 's', // string type
          v: postId,
          l: { Target: postUrl, Tooltip: `Xem bài post trên Facebook` }
        });
      }
      // Cột thứ 2 (index 1) là ID User - tạo hyperlink đến profile
      else if (colIndex === 1 && td.textContent.trim()) {
        const userId = td.textContent.trim();
        const profileUrl = `https://www.facebook.com/${userId}`;
        // Tạo hyperlink trong Excel
        row.push({
          t: 's', // string type
          v: userId,
          l: { Target: profileUrl, Tooltip: `Xem profile Facebook của ${userId}` }
        });
      } else {
        row.push(td.textContent);
      }
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
  if (backendStatus) {
    backendStatus.textContent = message;
  }
  if (statusDot) {
    statusDot.classList.toggle('online', isOnline);
  }
}

async function callBackend(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const method = (options.method || 'POST').toUpperCase();
  const headers = { ...(options.headers || {}) };
  // Chỉ set Content-Type khi có body => tránh preflight OPTIONS spam cho GET /status
  if (options.body != null && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, {
    method,
    headers,
    ...options,
  });

  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    // ignore parse errors, will throw below if not ok
  }

  if (!res.ok) {
    let detail = data.detail || res.statusText || 'Request failed';
    // Nếu backend trả detail dạng object (vd: {message, missing:[...]}) thì format lại cho dễ đọc
    try {
      if (detail && typeof detail === 'object') {
        const msg = detail.message ? String(detail.message) : 'Request failed';
        const missing = Array.isArray(detail.missing) ? detail.missing : [];
        if (missing.length > 0) {
          const lines = missing.map((x) => {
            const pid = (x && x.profile_id) ? String(x.profile_id) : '(unknown)';
            const fields = Array.isArray(x && x.missing) ? x.missing.join(', ') : '';
            return `${pid}${fields ? ` thiếu: ${fields}` : ''}`;
          });
          detail = `${msg} ${lines.join(' | ')}`;
        } else {
          detail = msg;
        }
      }
    } catch (_) { }
    throw new Error(String(detail));
  }

  return data;
}

async function callBackendNoAlert(path, options = {}) {
  try {
    return await callBackend(path, options);
  } catch (e) {
    return null;
  }
}

async function triggerBackendRun(options = {}) {
  setBackendStatus('Đang gửi lệnh chạy...', false);
  try {
    // Bắt buộc phải chọn (tick) profile trước khi chạy backend
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Hãy tick ít nhất 1 profile ở tab "Setting profile" trước khi chạy.', 'error');
      try { switchTab('settings'); } catch (_) { }
      return false;
    }

    const runMinutes = (options.runMinutes != null) ? Number(options.runMinutes) : Number(runMinutesInput.value);
    // Dùng luôn "Thời gian lặp lại (phút)" làm thời gian nghỉ giữa phiên (nếu không truyền override)
    const restMinutes = (options.restMinutes != null) ? Number(options.restMinutes) : Number(intervalInput.value);
    const text = (options.text != null) ? String(options.text || '').trim() : '';
    const mode = (options.mode != null) ? String(options.mode || '').trim().toLowerCase() : '';
    const payload = {};
    if (Number.isFinite(runMinutes) && runMinutes > 0) {
      payload.run_minutes = runMinutes;
    }
    if (Number.isFinite(restMinutes) && restMinutes > 0) {
      payload.rest_minutes = restMinutes;
    }
    payload.profile_ids = selected;
    if (text) payload.text = text;
    if (mode) payload.mode = mode;

    const data = await callBackend('/run', {
      body: JSON.stringify(payload),
    });
    const pidText = data.pid ? ` (PID ${data.pid})` : '';

    // Xác nhận backend thật sự đang chạy (tránh UI báo "Đang quét" nhưng runner đã thoát)
    const deadline = Date.now() + 2500;
    let jobs = null;
    while (Date.now() < deadline) {
      jobs = await callBackendNoAlert('/jobs/status', { method: 'GET' });
      if (jobs && jobs.bot_running) break;
      await new Promise((r) => setTimeout(r, 200));
    }
    if (jobs) lastJobsStatus = jobs;
    try { updateStopPauseButtonsByJobs(); } catch (_) { }

    if (!(jobs && jobs.bot_running)) {
      setBackendStatus(`Backend chưa chạy bot${pidText}`, false);
      showToast('Backend chưa chạy được bot (runner không alive).', 'error', 2200);
      return false;
    }

    setBackendStatus(`Bot đang chạy${pidText}`, true);
    return true;
  } catch (err) {
    console.error(err);
    alert('Không gọi được backend. Hãy kiểm tra FastAPI đã chạy chưa.');
    setBackendStatus('Backend lỗi hoặc chưa khởi động', false);
    return false;
  } finally {
  }
}

async function sendStopSignal() {
  try {
    console.log('[UI] STOP triggered');
    // /stop đã được backend map sang STOP (GLOBAL_EMERGENCY_STOP + đóng NST best-effort)
    await callBackend('/stop');
    setBackendStatus('Đã gửi lệnh dừng backend', false);
  } catch (err) {
    console.warn('Không dừng được backend:', err);
    setBackendStatus('Backend có thể vẫn đang chạy', false);
  }
}

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



// ==== Help Button với Tooltip ====

const helpBtn = document.getElementById('helpBtn');
const helpTooltip = document.getElementById('helpTooltip');

// Date range buttons
const todayBtn = document.getElementById('todayBtn');
const threeDaysBtn = document.getElementById('threeDaysBtn');

// File selector dropdown
const fileSelectorContainer = document.getElementById('fileSelectorContainer');
const closeFileSelector = document.getElementById('closeFileSelector');
const fileSelectorTitle = document.getElementById('fileSelectorTitle');
const fileList = document.getElementById('fileList');
const cancelFileSelection = document.getElementById('cancelFileSelection');
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
// ==== Bộ lọc màu sắc, React, Comment và Sắp xếp ====

const filterButtons = document.querySelectorAll('.filter-btn[data-filter]');
const reactFilterButtons = document.querySelectorAll('.filter-btn[data-filter-react]');
const commentFilterButtons = document.querySelectorAll('.filter-btn[data-filter-comment]');
const timeFilterFrom = document.getElementById('timeFilterFrom');
const timeFilterTo = document.getElementById('timeFilterTo');
const applyTimeFilterBtn = document.getElementById('applyTimeFilterBtn');
const clearTimeFilterBtn = document.getElementById('clearTimeFilterBtn');

// Sử dụng Set để lưu các filter đã chọn (cho phép nhiều lựa chọn)
let selectedTypeFilters = new Set(['all']);
let selectedReactFilters = new Set(); // Không có "all", rỗng = hiển thị tất cả
let selectedCommentFilters = new Set(); // Không có "all", rỗng = hiển thị tất cả
let timeFilterFromValue = null; // Thời gian bắt đầu
let timeFilterToValue = null; // Thời gian kết thúc

function toggleTypeFilter(filterType) {
  if (filterType === 'all') {
    // Nếu click "Tất cả", bỏ chọn tất cả và chỉ chọn "Tất cả"
    selectedTypeFilters.clear();
    selectedTypeFilters.add('all');
  } else {
    // Bỏ "all" nếu chọn filter cụ thể
    selectedTypeFilters.delete('all');

    // Toggle filter
    if (selectedTypeFilters.has(filterType)) {
      selectedTypeFilters.delete(filterType);
    } else {
      selectedTypeFilters.add(filterType);
    }

    // Nếu không còn filter nào được chọn, tự động chọn "all"
    if (selectedTypeFilters.size === 0) {
      selectedTypeFilters.add('all');
    }
  }
  applyAllFilters();
}

function toggleReactFilter(reactFilter) {
  // Toggle filter (không có "all" nữa)
  if (selectedReactFilters.has(reactFilter)) {
    selectedReactFilters.delete(reactFilter);
  } else {
    selectedReactFilters.add(reactFilter);
  }
  applyAllFilters();
}

function toggleCommentFilter(commentFilter) {
  // Toggle filter (không có "all" nữa)
  if (selectedCommentFilters.has(commentFilter)) {
    selectedCommentFilters.delete(commentFilter);
  } else {
    selectedCommentFilters.add(commentFilter);
  }
  applyAllFilters();
}

function applyAllFilters() {
  const rows = tbody.querySelectorAll('tr');

  rows.forEach((row) => {
    let shouldShow = true;

    // Filter theo màu (Type) - có thể chọn nhiều
    if (!selectedTypeFilters.has('all')) {
      const typeCell = row.querySelector('.type-cell');
      let matchesType = false;

      selectedTypeFilters.forEach(filterType => {
        if (typeCell && typeCell.classList.contains(filterType)) {
          matchesType = true;
        }
      });

      if (!matchesType) {
        shouldShow = false;
      }
    }

    // Filter theo React - nếu Set rỗng thì hiển thị tất cả
    if (shouldShow && selectedReactFilters.size > 0) {
      const reactCell = row.querySelector('td:nth-child(4)'); // Cột React
      const hasReact = reactCell && reactCell.textContent.trim() === '✓';
      let matchesReact = false;

      selectedReactFilters.forEach(reactFilter => {
        if (reactFilter === 'has' && hasReact) {
          matchesReact = true;
        } else if (reactFilter === 'none' && !hasReact) {
          matchesReact = true;
        }
      });

      if (!matchesReact) {
        shouldShow = false;
      }
    }

    // Filter theo Comment - nếu Set rỗng thì hiển thị tất cả
    if (shouldShow && selectedCommentFilters.size > 0) {
      const commentCell = row.querySelector('td:nth-child(5)'); // Cột Comment
      const hasComment = commentCell && commentCell.querySelector('.comment-eye-btn');
      let matchesComment = false;

      selectedCommentFilters.forEach(commentFilter => {
        if (commentFilter === 'has' && hasComment) {
          matchesComment = true;
        } else if (commentFilter === 'none' && !hasComment) {
          matchesComment = true;
        }
      });

      if (!matchesComment) {
        shouldShow = false;
      }
    }

    // Filter theo thời gian
    if (shouldShow && (timeFilterFromValue || timeFilterToValue)) {
      const timeCell = row.querySelector('td:nth-child(6)'); // Cột Time
      const timeStr = timeCell ? timeCell.textContent.trim() : '';

      if (timeStr) {
        // Parse timestamp từ row hoặc từ text
        let rowTimestamp = row.dataset.timestamp ? parseInt(row.dataset.timestamp) : 0;
        if (!rowTimestamp) {
          rowTimestamp = parseTime(timeStr);
          row.dataset.timestamp = rowTimestamp; // Lưu lại
        }

        // So sánh với khoảng thời gian đã chọn
        if (timeFilterFromValue && rowTimestamp < timeFilterFromValue) {
          shouldShow = false;
        }
        if (timeFilterToValue && rowTimestamp > timeFilterToValue) {
          shouldShow = false;
        }
      } else {
        // Nếu không có thời gian và có filter thời gian thì ẩn
        shouldShow = false;
      }
    }

    if (shouldShow) {
      row.classList.remove('filtered-out');
    } else {
      row.classList.add('filtered-out');
    }
  });

  // Cập nhật trạng thái active của các nút filter màu
  filterButtons.forEach((btn) => {
    const filterType = btn.dataset.filter;
    if (selectedTypeFilters.has(filterType)) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Cập nhật trạng thái active của các nút filter React
  reactFilterButtons.forEach((btn) => {
    const reactFilter = btn.dataset.filterReact;
    if (selectedReactFilters.has(reactFilter)) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Cập nhật trạng thái active của các nút filter Comment
  commentFilterButtons.forEach((btn) => {
    const commentFilter = btn.dataset.filterComment;
    if (selectedCommentFilters.has(commentFilter)) {
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

// Áp dụng filter theo thời gian
function applyTimeFilter() {
  const fromValue = timeFilterFrom ? timeFilterFrom.value : '';
  const toValue = timeFilterTo ? timeFilterTo.value : '';

  // Chuyển đổi từ datetime-local format (YYYY-MM-DDTHH:mm) sang timestamp
  if (fromValue) {
    timeFilterFromValue = new Date(fromValue).getTime();
  } else {
    timeFilterFromValue = null;
  }

  if (toValue) {
    // Thêm 1 ngày và trừ 1ms để bao gồm cả ngày cuối
    const toDate = new Date(toValue);
    toDate.setHours(23, 59, 59, 999);
    timeFilterToValue = toDate.getTime();
  } else {
    timeFilterToValue = null;
  }

  // Áp dụng filter
  applyAllFilters();

  // Cập nhật trạng thái nút
  if (applyTimeFilterBtn) {
    if (timeFilterFromValue || timeFilterToValue) {
      applyTimeFilterBtn.classList.add('active');
    } else {
      applyTimeFilterBtn.classList.remove('active');
    }
  }
}

// Xóa filter thời gian
function clearTimeFilter() {
  if (timeFilterFrom) timeFilterFrom.value = '';
  if (timeFilterTo) timeFilterTo.value = '';
  timeFilterFromValue = null;
  timeFilterToValue = null;

  // Áp dụng lại filter
  applyAllFilters();

  // Cập nhật trạng thái nút
  if (applyTimeFilterBtn) {
    applyTimeFilterBtn.classList.remove('active');
  }
}

// Hàm parse time từ string sang Date object
function parseTime(timeStr) {
  if (!timeStr) return 0;

  // Thử parse các format thời gian phổ biến
  // Format: "HH:mm:ss" hoặc "HH:mm" hoặc "dd/MM/yyyy HH:mm:ss"
  const now = new Date();

  // Nếu có format đầy đủ với ngày
  if (timeStr.includes('/')) {
    const parts = timeStr.split(' ');
    if (parts.length >= 2) {
      const datePart = parts[0].split('/');
      const timePart = parts[1].split(':');
      if (datePart.length === 3 && timePart.length >= 2) {
        const year = parseInt(datePart[2]);
        const month = parseInt(datePart[1]) - 1;
        const day = parseInt(datePart[0]);
        const hour = parseInt(timePart[0]);
        const minute = parseInt(timePart[1]);
        const second = timePart[2] ? parseInt(timePart[2]) : 0;
        return new Date(year, month, day, hour, minute, second).getTime();
      }
    }
  }

  // Nếu chỉ có giờ:phút:giây
  if (timeStr.includes(':')) {
    const parts = timeStr.split(':');
    if (parts.length >= 2) {
      const hour = parseInt(parts[0]) || 0;
      const minute = parseInt(parts[1]) || 0;
      const second = parts[2] ? parseInt(parts[2]) : 0;
      const date = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, second);
      return date.getTime();
    }
  }

  // Fallback: thử parse trực tiếp
  const parsed = Date.parse(timeStr);
  return isNaN(parsed) ? 0 : parsed;
}

// Khởi tạo: set trạng thái active cho các nút "Tất cả"
function initializeFilters() {
  applyAllFilters();
}

// Thêm event listener cho các nút filter màu
filterButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const filterType = btn.dataset.filter;
    if (filterType) {
      toggleTypeFilter(filterType);
    }
  });
});

// Thêm event listener cho các nút filter React
reactFilterButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const reactFilter = btn.dataset.filterReact;
    if (reactFilter) {
      toggleReactFilter(reactFilter);
    }
  });
});

// Thêm event listener cho các nút filter Comment
commentFilterButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const commentFilter = btn.dataset.filterComment;
    if (commentFilter) {
      toggleCommentFilter(commentFilter);
    }
  });
});

// Thêm event listener cho filter thời gian
if (applyTimeFilterBtn) {
  applyTimeFilterBtn.addEventListener('click', () => {
    applyTimeFilter();
  });
}

if (clearTimeFilterBtn) {
  clearTimeFilterBtn.addEventListener('click', () => {
    clearTimeFilter();
  });
}

// Cho phép áp dụng filter khi nhấn Enter trong input
if (timeFilterFrom) {
  timeFilterFrom.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      applyTimeFilter();
    }
  });
}

// Flag để track khi đang chạy info collector
let isInfoCollectorRunning = false;
let scanStatsInterval = null;
let infoProgressInterval = null;

// Hàm để cập nhật số bài đã quét được
async function updateScanStats() {
  try {
    const res = await callBackendNoAlert('/info/scan-stats', { method: 'GET' });
    if (!res || !res.stats) return;
    
    const stats = res.stats;
    const toast = document.getElementById('scanStatsToast');
    const list = document.getElementById('scanStatsToastList');
    const progressToast = document.getElementById('progressToast');
    
    if (!toast || !list || !progressToast) return;
    
    const selected = getSelectedProfileIds();
    if (selected.length === 0 && Object.keys(stats).length === 0) {
      toast.style.display = 'none';
      // Ẩn progressToast nếu cả 2 toast đều ẩn
      const infoToast = document.getElementById('infoProgressToast');
      if (!infoToast || infoToast.style.display === 'none') {
        progressToast.style.display = 'none';
      }
      return;
    }
    
    // Chỉ hiển thị các profile đã chọn hoặc tất cả nếu không có profile nào được chọn
    const profilesToShow = selected.length > 0 ? selected : Object.keys(stats);
    
    let html = '';
    for (const pid of profilesToShow) {
      const count = stats[pid] || 0;
      html += `<div style="margin: 6px 0; padding: 12px; background: white; border-radius: 8px; border-left: 4px solid #667eea; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 20px;">📝</span>
        <div style="flex: 1;">
          <div style="font-weight: 600; color: #2d3748; font-size: 13px; margin-bottom: 2px;">${pid}</div>
          <div style="color: #667eea; font-weight: bold; font-size: 16px;">Đã quét được ${count} bài</div>
        </div>
      </div>`;
    }
    
    if (html) {
      list.innerHTML = html;
      toast.style.display = 'block';
      progressToast.style.display = 'block';
    } else {
      toast.style.display = 'none';
      // Ẩn progressToast nếu cả 2 toast đều ẩn
      const infoToast = document.getElementById('infoProgressToast');
      if (!infoToast || infoToast.style.display === 'none') {
        progressToast.style.display = 'none';
      }
    }
  } catch (e) {
    // Ignore errors
  }
}

// Hàm để cập nhật tiến trình lấy thông tin
async function updateInfoProgress() {
  try {
    const res = await callBackendNoAlert('/info/progress', { method: 'GET' });
    if (!res) {
      // Nếu không có response, reset state
      if (isInfoCollectorRunning) {
        resetInfoCollectorState();
        updateStopPauseButtonsByJobs();
      }
      return;
    }
    
    const toast = document.getElementById('infoProgressToast');
    const text = document.getElementById('infoProgressToastText');
    const progressBar = document.getElementById('infoProgressToastBar');
    const progressToast = document.getElementById('progressToast');
    
    if (!toast || !text || !progressToast) return;
    
    // Sync isInfoCollectorRunning với backend state
    const backendRunning = Boolean(res.is_running);
    if (isInfoCollectorRunning !== backendRunning) {
      isInfoCollectorRunning = backendRunning;
      if (!backendRunning) {
        // Backend đã dừng, reset state
        resetInfoCollectorState();
      }
      updateStopPauseButtonsByJobs();
    }
    
    if (res.is_running && res.total > 0) {
      const current = res.current || 0;
      const total = res.total || 0;
      const file = res.current_file || '';
      const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
      
      text.textContent = `Đã xử lý ${current}/${total} bài${file ? ` • File: ${file}` : ''}`;
      
      // Cập nhật progress bar
      if (progressBar) {
        progressBar.style.width = `${percentage}%`;
      }
      
      toast.style.display = 'block';
      progressToast.style.display = 'block';
    } else {
      toast.style.display = 'none';
      // Reset progress bar
      if (progressBar) {
        progressBar.style.width = '0%';
      }
      // Ẩn progressToast nếu cả 2 toast đều ẩn
      const scanToast = document.getElementById('scanStatsToast');
      if (!scanToast || scanToast.style.display === 'none') {
        progressToast.style.display = 'none';
      }
    }
  } catch (e) {
    // Nếu có lỗi khi check progress, có thể backend đã dừng
    if (isInfoCollectorRunning) {
      resetInfoCollectorState();
      updateStopPauseButtonsByJobs();
    }
  }
}

async function runInfoCollector(mode = 'all') {
  const isSelected = mode === 'selected';
  const btn = isSelected ? runSelectedInfoBtn : runAllInfoBtn;
  const selected = getSelectedProfileIds();

  if (isSelected && selected.length === 0) {
    showToast('Chọn (tick) ít nhất 1 profile trước.', 'error');
    try { switchTab('settings'); } catch (_) { }
    return;
  }

  // Đánh dấu đang chạy
  isInfoCollectorRunning = true;
  
  setButtonLoading(btn, true, 'Đang lấy thông tin...');
  
  // Bắt đầu poll tiến trình
  if (infoProgressInterval) clearInterval(infoProgressInterval);
  updateInfoProgress(); // Cập nhật ngay lập tức
  infoProgressInterval = setInterval(updateInfoProgress, 2000); // Poll mỗi 2 giây
  
  // Update buttons để enable pause/stop buttons
  updateStopPauseButtonsByJobs();
  
  try {
    const body = { mode: isSelected ? 'selected' : 'all' };
    if (isSelected) body.profiles = selected;
    const res = await callBackend('/info/run', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const summary = res && res.summary ? res.summary : null;
    const msgParts = [];
    msgParts.push(isSelected ? `Đã chạy cho ${body.profiles.length} profile` : 'Đã chạy lấy thông tin toàn bộ');
    if (summary && typeof summary.total_posts_processed === 'number') {
      msgParts.push(`posts: ${summary.total_posts_processed}`);
    }
    showToast(msgParts.join(' | '), 'success', 2200);

    // Tự động tải lại danh sách quét với dữ liệu mới nhất theo timestamp
    try {
      await loadInitialData();
      showToast('Đã cập nhật danh sách quét với dữ liệu mới nhất', 'info', 1500);
    } catch (loadErr) {
      console.warn('Không thể tải lại danh sách quét:', loadErr);
      // Không hiện lỗi cho user vì chức năng chính đã thành công
    }

    // Reset flag sau khi hoàn thành thành công
    resetInfoCollectorState();
  } catch (e) {
    console.error('Error in runInfoCollector:', e);
    // Kiểm tra nếu là lỗi "không có dữ liệu bài viết"
    const errorMsg = (e?.message || e?.detail || String(e) || '').toLowerCase();
    if (errorMsg.includes('không có dữ liệu bài viết') || 
        errorMsg.includes('khong co du lieu bai viet') ||
        errorMsg.includes('no data') ||
        errorMsg.includes('empty')) {
      showToast('Không có dữ liệu bài viết để xử lý', 'error', 4000);
    } else {
      const displayMsg = e?.message || e?.detail || 'Không chạy được lấy thông tin (check backend).';
      showToast(displayMsg, 'error', 3000);
    }
    // Reset flag khi có lỗi
    resetInfoCollectorState();
  } finally {
    setButtonLoading(btn, false);
    // Update buttons sau khi reset state
    updateStopPauseButtonsByJobs();
  }
}

if (runAllInfoBtn) {
  runAllInfoBtn.addEventListener('click', () => runInfoCollector('all'));
}

if (runSelectedInfoBtn) {
  runSelectedInfoBtn.addEventListener('click', () => runInfoCollector('selected'));
}

if (timeFilterTo) {
  timeFilterTo.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      applyTimeFilter();
    }
  });
}

// ==== Tabs: Danh sách quét / Quản lý post / Setting profile ====
const tabConfig = {
  scan: { btn: tabScanList, view: scanView },
  post: { btn: tabPostManager, view: postView },
  settings: { btn: tabSettings, view: settingsView },
};

const ACTIVE_TAB_KEY = 'activeTab';

function switchTab(key) {
  Object.entries(tabConfig).forEach(([k, { btn, view }]) => {
    if (!btn || !view) return;
    const isActive = k === key;
    btn.classList.toggle('active', isActive);
    view.style.display = isActive ? 'block' : 'none';
  });

  if (key === 'post') {
    loadPostsForManager();
  }

  // nhớ tab đang mở để không bị nhảy về tab đầu
  try {
    localStorage.setItem(ACTIVE_TAB_KEY, key);
  } catch (e) {
    // ignore
  }
}

if (tabScanList) tabScanList.addEventListener('click', async (e) => {
  // Chỉ chuyển tab khi người dùng thật sự bấm tab; không auto chuyển ở nơi khác
  e.preventDefault();
  switchTab('scan');

  // Khi click vào tab danh sách quét, tự động load lại dữ liệu mới nhất theo timestamp
  try {
    await loadInitialData();
  } catch (err) {
    console.warn('Không thể load dữ liệu khi click tab danh sách quét:', err);
  }
});
if (tabPostManager) tabPostManager.addEventListener('click', () => switchTab('post'));
if (tabSettings) tabSettings.addEventListener('click', () => switchTab('settings'));

// ============
// Date Range Buttons Logic
// ============

// Function để load data từ file cụ thể
async function loadDataFromFile(filename) {
  console.log('Loading data from file:', filename);

  try {
    // Reset data
    tbody.innerHTML = '';
    counter = 1;
    loadedPostIds.clear();
    initialLoaded = false;

    // Gọi API để lấy data từ file cụ thể
    const res = await callBackend('/data/latest-results', {
      method: 'POST',
      body: JSON.stringify({
        filename: filename
      })
    });

    const data = res.data;
    console.log(`Đã load data từ file: ${filename}`);

    // Xử lý data giống như loadInitialData
    const allPosts = [];
    Object.values(data.results_by_file || {}).forEach(filePosts => {
      if (Array.isArray(filePosts)) {
        allPosts.push(...filePosts);
      }
    });

    console.log(`Tổng số posts: ${allPosts.length}`);

    let displayedCount = 0;
    allPosts.forEach((post) => {
      const postId = post.post_id || '';
      if (!postId) return;

      // Map flag
      let type = 'type1';
      const flag = (post.flag || '').toLowerCase();
      if (flag === 'xanh') type = 'type1';
      else if (flag === 'vàng' || flag === 'vang') type = 'type2';
      else if (flag === 'đỏ' || flag === 'do') type = 'type3';

      // Xử lý reactions và comments
      const reactionsByUser = new Map();
      const commentsByUser = new Map();

      if (post.reactions && Array.isArray(post.reactions)) {
        post.reactions.forEach((r) => {
          const uid = r && r.id ? String(r.id) : '';
          if (!uid) return;
          reactionsByUser.set(uid, r);
        });
      }

      if (post.comments && Array.isArray(post.comments)) {
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

      // Thời gian mặc định
      let defaultTime = new Date().toLocaleTimeString('vi-VN');

      // Tập tất cả user
      const allUserIds = new Set([
        ...reactionsByUser.keys(),
        ...commentsByUser.keys(),
      ]);

      // Nếu không có user nào interact, hiển thị post với thông tin owner
      if (allUserIds.size === 0) {
        const owner = post.owning_profile || {};
        const ownerId = owner.id || 'unknown';
        const ownerName = owner.name || 'Unknown User';
        const uniqueKey = `${postId}_${ownerId}`;

        if (!loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: ownerId,
            name: ownerName,
            react: false,
            comment: '',
            time: defaultTime,
            type: type,
          });
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      }

      allUserIds.forEach((uid) => {
        const reaction = reactionsByUser.get(uid);
        const comment = commentsByUser.get(uid);

        const userId = uid;
        const name = (reaction && reaction.name) || (comment && comment.name) || '';

        const hasReact = !!reaction;
        const commentText = comment && comment.text ? comment.text : '';
        const time = (comment && comment.created_time_vn) ? comment.created_time_vn : defaultTime;

        const uniqueKey = `${postId}_${userId}`;
        if (!loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: userId,
            name: name,
            react: hasReact,
            comment: commentText,
            time: time,
            type: type,
          });
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      });
    });

    console.log(`Đã hiển thị ${displayedCount} dòng dữ liệu từ file ${filename}`);
    initialLoaded = true;

    // Show empty state if no rows
    if (tbody.children.length === 0) {
      emptyState.classList.add('show');
    } else {
      emptyState.classList.remove('show');
    }

  } catch (err) {
    console.error('Không tải được data từ file:', err);
    showToast('Không thể tải dữ liệu từ file đã chọn', 'error', 4000);
  }
}

// Function để show dropdown với danh sách files
async function showFileSelector(rangeType, fromDate, toDate) {
  console.log('Showing file selector for:', rangeType, 'from:', fromDate, 'to:', toDate);

  try {
    // Set title
    let title = '';
    if (rangeType === 'today') title = 'Chọn file data ngày hôm nay';
    else if (rangeType === '3days') title = 'Chọn file data 3 ngày gần nhất';
    fileSelectorTitle.textContent = title;

    // Gọi API để lấy danh sách files
    const res = await callBackend('/data/files-in-range', {
      method: 'POST',
      body: JSON.stringify({
        from_timestamp: Math.floor(fromDate.getTime() / 1000),
        to_timestamp: Math.floor(toDate.getTime() / 1000)
      })
    });

    const files = res.files || [];
    console.log(`Tìm thấy ${files.length} file trong khoảng thời gian`);

    // Populate file list
    fileList.innerHTML = '';

    if (files.length === 0) {
      fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #6b7280;">Không tìm thấy file nào trong khoảng thời gian này</div>';
    } else {
      files.forEach((file, index) => {
        const fileItem = document.createElement('button');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
          <div class="file-name">${file.filename}</div>
          <div class="file-info">${file.date_formatted}</div>
        `;

        fileItem.addEventListener('click', async () => {
          // Load data from selected file
          await loadDataFromFile(file.filename);
          fileSelectorContainer.classList.add('hidden');

          // Update active button
          [todayBtn, threeDaysBtn].forEach(btn => btn.classList.remove('active'));
          if (rangeType === 'today') todayBtn.classList.add('active');
          else if (rangeType === '3days') threeDaysBtn.classList.add('active');
        });

        fileList.appendChild(fileItem);
      });
    }

    // Show dropdown
    fileSelectorContainer.classList.remove('hidden');

  } catch (err) {
    console.error('Không thể load danh sách files:', err);
    showToast('Không thể tải danh sách files', 'error', 4000);
  }
}

// Function để set khoảng thời gian cho các nút preset
function setDateRange(days) {
  const now = new Date();
  const toDate = new Date(now);
  const fromDate = new Date(now);

  if (days === 'today') {
    // Từ 00:00 hôm nay đến hiện tại
    fromDate.setHours(0, 0, 0, 0);
  } else {
    // Từ N ngày trước đến hiện tại
    fromDate.setDate(fromDate.getDate() - days);
  }

  return { fromDate, toDate };
}

// Function để load data theo khoảng thời gian (legacy - không dùng nữa)
async function loadDataByDateRange(fromDate, toDate) {
  console.log('Loading data from:', fromDate, 'to:', toDate);

  try {
    // Reset data
    tbody.innerHTML = '';
    counter = 1;
    loadedPostIds.clear();
    initialLoaded = false;

    // Gọi API để lấy file JSON theo khoảng thời gian
    const res = await callBackend('/data/by-date-range', {
      method: 'POST',
      body: JSON.stringify({
        from_timestamp: Math.floor(fromDate.getTime() / 1000),
        to_timestamp: Math.floor(toDate.getTime() / 1000)
      })
    });

    const data = res.data;
    console.log(`Đã load file JSON theo khoảng thời gian:`, data.total_files);

    // Xử lý data giống như loadInitialData
    const allPosts = [];
    Object.values(data.results_by_file || {}).forEach(filePosts => {
      if (Array.isArray(filePosts)) {
        allPosts.push(...filePosts);
      }
    });

    console.log(`Tổng số posts trong khoảng thời gian: ${allPosts.length}`);

    let displayedCount = 0;
    allPosts.forEach((post) => {
      const postId = post.post_id || '';
      if (!postId) return;

      // Map flag
      let type = 'type1';
      const flag = (post.flag || '').toLowerCase();
      if (flag === 'xanh') type = 'type1';
      else if (flag === 'vàng' || flag === 'vang') type = 'type2';
      else if (flag === 'đỏ' || flag === 'do') type = 'type3';

      // Xử lý reactions và comments
      const reactionsByUser = new Map();
      const commentsByUser = new Map();

      if (post.reactions && Array.isArray(post.reactions)) {
        post.reactions.forEach((r) => {
          const uid = r && r.id ? String(r.id) : '';
          if (!uid) return;
          reactionsByUser.set(uid, r);
        });
      }

      if (post.comments && Array.isArray(post.comments)) {
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

      // Thời gian mặc định
      let defaultTime = new Date().toLocaleTimeString('vi-VN');

      // Tập tất cả user
      const allUserIds = new Set([
        ...reactionsByUser.keys(),
        ...commentsByUser.keys(),
      ]);

      // Nếu không có user nào interact, hiển thị post với thông tin owner
      if (allUserIds.size === 0) {
        const owner = post.owning_profile || {};
        const ownerId = owner.id || 'unknown';
        const ownerName = owner.name || 'Unknown User';
        const uniqueKey = `${postId}_${ownerId}`;

        if (!loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: ownerId,
            name: ownerName,
            react: false,
            comment: '',
            time: defaultTime,
            type: type,
          });
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      }

      allUserIds.forEach((uid) => {
        const reaction = reactionsByUser.get(uid);
        const comment = commentsByUser.get(uid);

        const userId = uid;
        const name = (reaction && reaction.name) || (comment && comment.name) || '';

        const hasReact = !!reaction;
        const commentText = comment && comment.text ? comment.text : '';
        const time = (comment && comment.created_time_vn) ? comment.created_time_vn : defaultTime;

        const uniqueKey = `${postId}_${userId}`;
        if (!loadedPostIds.has(uniqueKey)) {
          appendRow({
            id: postId,
            userId: userId,
            name: name,
            react: hasReact,
            comment: commentText,
            time: time,
            type: type,
          });
          loadedPostIds.add(uniqueKey);
          displayedCount++;
        }
      });
    });

    console.log(`Đã hiển thị ${displayedCount} dòng dữ liệu theo khoảng thời gian`);
    initialLoaded = true;

    // Show empty state if no rows
    if (tbody.children.length === 0) {
      emptyState.classList.add('show');
    } else {
      emptyState.classList.remove('show');
    }

  } catch (err) {
    console.error('Không tải được data theo khoảng thời gian:', err);
    showToast('Không thể tải dữ liệu theo khoảng thời gian', 'error', 4000);
  }
}

// Function để set khoảng thời gian cho các nút preset
function setDateRange(days) {
  const now = new Date();
  const toDate = new Date(now);
  const fromDate = new Date(now);

  if (days === 'today') {
    // Từ 00:00 hôm nay đến hiện tại
    fromDate.setHours(0, 0, 0, 0);
  } else {
    // Từ N ngày trước đến hiện tại
    fromDate.setDate(fromDate.getDate() - days);
  }

  return { fromDate, toDate };
}

// Event listeners cho date buttons
if (todayBtn) {
  todayBtn.addEventListener('click', async () => {
    const { fromDate, toDate } = setDateRange('today');
    await showFileSelector('today', fromDate, toDate);
  });
}

if (threeDaysBtn) {
  threeDaysBtn.addEventListener('click', async () => {
    const { fromDate, toDate } = setDateRange(3);
    await showFileSelector('3days', fromDate, toDate);
  });
}


// Event listeners cho file selector
if (closeFileSelector) {
  closeFileSelector.addEventListener('click', () => {
    fileSelectorContainer.classList.add('hidden');
  });
}

if (cancelFileSelection) {
  cancelFileSelection.addEventListener('click', () => {
    fileSelectorContainer.classList.add('hidden');
  });
}

// Click outside để đóng file selector
document.addEventListener('click', (e) => {
  if (!fileSelectorContainer.contains(e.target) &&
      !e.target.matches('.date-btn')) {
    fileSelectorContainer.classList.add('hidden');
  }
});

// Khởi tạo: luôn vào tab danh sách quét + load state profile
let initialTab = 'scan';
try {
  const saved = localStorage.getItem(ACTIVE_TAB_KEY);
  if (saved && tabConfig[saved]) initialTab = saved;
} catch (e) {
  // ignore
}
switchTab(initialTab);
// Khởi tạo: load state profile rồi sync UI theo backend (để F5 không bị lệch trạng thái)
(async () => {
  try {
    await loadProfileState();
  } catch (_) { }
  try {
    await resyncUiFromBackendAfterReload();
  } catch (_) { }
  try {
    // Tự động load danh sách quét với JSON mới nhất theo timestamp
    await loadInitialData();
  } catch (err) {
    console.warn('Không thể load danh sách quét lúc khởi tạo:', err);
  }
})();
// Khởi tạo filter với trạng thái mặc định
initializeFilters();
