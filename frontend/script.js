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

// Delete Data Modal elements
const deleteDataBtn = document.getElementById('deleteDataBtn');
const deleteDataModal = document.getElementById('deleteDataModal');
const deleteDataModalClose = document.getElementById('deleteDataModalClose');
const deleteDataModalCancel = document.getElementById('deleteDataModalCancel');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
const deleteDateList = document.getElementById('deleteDateList');

const API_BASE = 'http://localhost:8000';
const SETTINGS_STORAGE_KEY = 'profileSettings';
const toastContainer = document.getElementById('toastContainer');

let counter = 1;
let timerId = null;
let initialLoaded = false;
let dataCheckInterval = null; // Interval để kiểm tra dữ liệu mới
let loadedPostIds = new Set(); // Lưu các post_id đã load để tránh trùng lặp
let currentResultsFilename = null; // Track filename hiện tại để phát hiện file mới
let autoRefreshInterval = null; // Interval để auto-refresh khi ở tab kết quả
let postsLoaded = false; // Đã load dữ liệu quản lý post hay chưa
let lastRowCountForToast = null; // Track rowCount cũ để chỉ update toast khi thay đổi
let continuousInfoCollectorInterval = null; // Interval để chạy lấy thông tin liên tục
let isContinuousInfoCollectorRunning = false; // Flag để biết có đang chạy lấy thông tin liên tục không
let profileState = {
  apiKey: '',
  profiles: {}, // { [profileId]: { cookie: '', access_token: '', fb_dtsg: '', lsd: '', spin_r: '', spin_t: '', groups: string[] } }
  selected: {}, // { [profileId]: true/false } (frontend-only)
};
let addRowEl = null; // Row tạm để nhập profile mới
let joinGroupPollTimer = null;
let feedPollTimer = null;
let groupScanPollTimer = null;
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
  
  // Cập nhật toast số user nếu đang lấy thông tin
  updateInfoUserCountToast();
}

// Cập nhật toast hiển thị số user đã quét được
// Chỉ cập nhật khi rowCount tăng (có user mới), không cập nhật nếu rowCount giữ nguyên hoặc giảm
function updateInfoUserCountToast() {
  if (!isInfoCollectorRunning) return;
  
  const toast = document.getElementById('infoUserCountToast');
  const text = document.getElementById('infoUserCountToastText');
  
  if (!toast || !text || !rowCount) return;
  
  const currentCount = parseInt(rowCount.textContent || '0', 10);
  
  // Nếu chưa có giá trị tracking, lưu giá trị hiện tại và hiển thị toast
  if (lastRowCountForToast === null) {
    lastRowCountForToast = currentCount;
    text.textContent = `Đã quét được ${currentCount} user`;
    toast.style.display = 'block';
    return;
  }
  
  // Chỉ update khi rowCount tăng (có user mới)
  if (currentCount > lastRowCountForToast) {
    lastRowCountForToast = currentCount;
    text.textContent = `Đã quét được ${currentCount} user`;
    toast.style.display = 'block';
  }
  // Nếu rowCount giữ nguyên hoặc giảm, không làm gì (giữ nguyên giá trị cũ trong toast)
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

    if (groupScanPollTimer) {
      if (scanGroupSettingBtn && scanGroupSettingBtn.classList.contains('btn-loading')) {
        scanGroupSettingBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang quét group...';
      }
      if (groupScanStartBtn && groupScanStartBtn.classList.contains('btn-loading')) {
        groupScanStartBtn.textContent = isPausedAll ? 'Đang tạm dừng...' : 'Đang quét group...';
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

  // Badge logic đã được xóa
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

  // Disable các nút lấy thông tin khi đang chạy (KHÔNG ghi đè nếu đang loading - setButtonLoading đã xử lý)
  // Chỉ set disabled nếu KHÔNG đang loading để tránh conflict với setButtonLoading
  if (runAllInfoBtn) {
    if (runAllInfoBtn.classList.contains('btn-loading')) {
      console.log('updateStopPauseButtonsByJobs: Skipping runAllInfoBtn because it is loading');
    } else {
      // Disable nếu đang chạy, enable nếu không chạy
      runAllInfoBtn.disabled = isInfoCollectorRunning;
      console.log('updateStopPauseButtonsByJobs: runAllInfoBtn disabled:', isInfoCollectorRunning);
    }
  }
  
  // runSelectedInfoBtn sẽ được xử lý trong updateSettingsActionButtons() để tránh conflict

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
          name: '',
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
          name: '',
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
          name: (cfg && cfg.name) ? String(cfg.name).trim() : '',
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

// Lưu frontend state (selected profiles, mode, time, text) vào backend
async function saveFrontendState() {
  try {
    const state = {
      selected_profiles: profileState.selected || {},
      feed_mode: document.querySelector('input[name="feedMode"]:checked')?.value || 'feed',
      feed_text: feedTextInput?.value || '',
      feed_run_minutes: parseFloat(feedRunMinutesInput?.value || '30') || 30,
      feed_rest_minutes: parseFloat(feedRestMinutesInput?.value || '120') || 120,
      scan_mode: document.querySelector('input[name="scanMode"]:checked')?.value || 'feed',
      scan_text: scanTextInput?.value || '',
      scan_run_minutes: parseFloat(scanRunMinutesInput?.value || '30') || 30,
      scan_rest_minutes: parseFloat(scanRestMinutesInput?.value || '120') || 120,
      group_scan_post_count: parseInt(groupScanPostCountInput?.value || '0', 10),
      group_scan_start_date: groupScanStartDateInput?.value || '',
      group_scan_end_date: groupScanEndDateInput?.value || '',
    };
    
    await callBackendNoAlert('/frontend/state', {
      method: 'POST',
      body: JSON.stringify(state),
    });
  } catch (e) {
    // Không hiển thị lỗi khi lưu state (silent fail)
    console.warn('Không lưu được frontend state:', e);
  }
}

// Đọc và khôi phục frontend state từ backend
async function loadFrontendState() {
  try {
    const state = await callBackendNoAlert('/frontend/state', { method: 'GET' });
    
    // Khôi phục selected profiles - CẬP NHẬT profileState.selected TRƯỚC
    if (state.selected_profiles && typeof state.selected_profiles === 'object') {
      profileState.selected = state.selected_profiles;
      // Cập nhật checkbox trong UI (nếu đã được render)
      document.querySelectorAll('.profile-select-cb').forEach((cb) => {
        const profileId = cb.closest('.profile-row-wrap')?.dataset.profileId;
        if (profileId) {
          cb.checked = Boolean(state.selected_profiles[profileId]);
        }
      });
      // QUAN TRỌNG: Gọi updateSettingsActionButtons() để enable các nút
      updateSettingsActionButtons();
    }
    
    // Khôi phục feed mode
    if (state.feed_mode) {
      const feedModeRadio = document.querySelector(`input[name="feedMode"][value="${state.feed_mode}"]`);
      if (feedModeRadio) {
        feedModeRadio.checked = true;
      }
    }
    
    // Khôi phục feed text
    if (feedTextInput && state.feed_text !== undefined) {
      feedTextInput.value = state.feed_text;
    }
    
    // Khôi phục feed run/rest minutes
    if (feedRunMinutesInput && state.feed_run_minutes !== undefined) {
      feedRunMinutesInput.value = state.feed_run_minutes;
    }
    if (feedRestMinutesInput && state.feed_rest_minutes !== undefined) {
      feedRestMinutesInput.value = state.feed_rest_minutes;
    }
    
    // Khôi phục scan mode
    if (state.scan_mode) {
      const scanModeRadio = document.querySelector(`input[name="scanMode"][value="${state.scan_mode}"]`);
      if (scanModeRadio) {
        scanModeRadio.checked = true;
      }
    }
    
    // Khôi phục scan text
    if (scanTextInput && state.scan_text !== undefined) {
      scanTextInput.value = state.scan_text;
    }
    
    // Khôi phục scan run/rest minutes
    if (scanRunMinutesInput && state.scan_run_minutes !== undefined) {
      scanRunMinutesInput.value = state.scan_run_minutes;
    }
    if (scanRestMinutesInput && state.scan_rest_minutes !== undefined) {
      scanRestMinutesInput.value = state.scan_rest_minutes;
    }
    
    // Khôi phục group scan settings
    if (groupScanPostCountInput && state.group_scan_post_count !== undefined) {
      groupScanPostCountInput.value = state.group_scan_post_count;
    }
    if (groupScanStartDateInput && state.group_scan_start_date) {
      groupScanStartDateInput.value = state.group_scan_start_date;
    }
    if (groupScanEndDateInput && state.group_scan_end_date) {
      groupScanEndDateInput.value = state.group_scan_end_date;
    }
    
    console.log('✅ Đã khôi phục frontend state từ backend');
  } catch (e) {
    console.warn('Không đọc được frontend state:', e);
  }
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
    // nếu đang loading thì giữ nguyên trạng thái disabled (setButtonLoading đã xử lý)
    if (b.classList && b.classList.contains('btn-loading')) return;
    
    // Đặc biệt xử lý runSelectedInfoBtn: cần kiểm tra cả isInfoCollectorRunning
    if (b === runSelectedInfoBtn) {
      // Disable nếu đang chạy hoặc không có selected
      b.disabled = isInfoCollectorRunning || !hasSelected;
    } else {
      // Các nút khác chỉ cần kiểm tra hasSelected
      b.disabled = !hasSelected;
    }
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
  // Hỗ trợ nhiều dòng: thay \n thành <br>
  if (typeof message === 'string' && message.includes('\n')) {
    el.innerHTML = message.split('\n').map(line => line.trim()).filter(line => line).join('<br>');
  } else {
    el.textContent = message;
  }
  toastContainer.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 220);
  }, ms);
}

function setButtonLoading(btn, isLoading, loadingText) {
  if (!btn) {
    console.warn('setButtonLoading: button is null');
    return;
  }
  if (isLoading) {
    if (!btn.dataset.origText) {
      btn.dataset.origText = btn.textContent || '';
    }
    // Force disable và add class
    btn.disabled = true;
    btn.setAttribute('disabled', 'disabled');
    btn.classList.add('btn-loading');
    if (loadingText) btn.textContent = loadingText;
    // Force style để đảm bảo
    btn.style.pointerEvents = 'none';
    btn.style.cursor = 'not-allowed';
    btn.style.opacity = '0.9';
    console.log('setButtonLoading: Set loading for button', btn.id, 'disabled:', btn.disabled, 'has class:', btn.classList.contains('btn-loading'), 'classList:', btn.classList.toString());
  } else {
    btn.disabled = false;
    btn.removeAttribute('disabled');
    btn.classList.remove('btn-loading');
    btn.style.pointerEvents = '';
    btn.style.cursor = '';
    btn.style.opacity = '';
    if (btn.dataset.origText) {
      btn.textContent = btn.dataset.origText;
      delete btn.dataset.origText;
    }
    console.log('setButtonLoading: Removed loading for button', btn.id);
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

  const nameInput = document.createElement('input');
  nameInput.className = 'profile-name-input';
  nameInput.type = 'text';
  nameInput.placeholder = 'Tên profile';
  nameInput.value = (initialInfo && initialInfo.name) ? String(initialInfo.name).trim() : '';
  nameInput.title = 'Tên profile';

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
  saveBtn.className = 'btn-primary';
  saveBtn.textContent = 'Lưu';

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'btn-danger';
  removeBtn.textContent = 'Xóa';

  const groupBtn = document.createElement('button');
  groupBtn.type = 'button';
  groupBtn.className = 'btn-primary';
  groupBtn.textContent = 'Thêm Groups';

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
  groupSaveBtn.className = 'btn-primary';
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
  tokenSaveBtn.className = 'btn-primary';
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
        name: '',
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
    saveFrontendState(); // Lưu state vào backend
    updateSettingsActionButtons();
  });

  const cookieBtn = document.createElement('button');
  cookieBtn.type = 'button';
  cookieBtn.className = 'btn-primary';
  cookieBtn.textContent = 'Cập nhật cookie';

  const tokenBtn = document.createElement('button');
  tokenBtn.type = 'button';
  tokenBtn.className = 'btn-primary';
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
      name: '',
      cookie: '', 
      access_token: '', 
      fb_dtsg: '', 
      lsd: '', 
      spin_r: '', 
      spin_t: '',
      groups: [] 
    };
    const nameValue = (nameInput.value || '').trim();
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
            name: nameValue,
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
        profileState.profiles[nextPid] = { ...cur, name: nameValue };
        // Bỏ tick checkbox khi sửa profile_id (xóa cả selection cũ và mới)
        if (profileState.selected && profileState.selected[currentPid]) {
          delete profileState.selected[currentPid];
        }
        if (profileState.selected && profileState.selected[nextPid]) {
          delete profileState.selected[nextPid];
        }
        currentPid = nextPid;
        pidInput.value = currentPid;
        wrap.dataset.profileId = String(currentPid || '').trim();
        selectCb.checked = false;
        updateGroupBtnLabel();
      } else {
        await callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: nameValue,
            cookie: cur.cookie || '',
            access_token: cur.access_token || '',
            fb_dtsg: cur.fb_dtsg || '',
            lsd: cur.lsd || '',
            spin_r: cur.spin_r || '',
            spin_t: cur.spin_t || '',
          }),
        });
        // Cập nhật name trong profileState
        if (profileState.profiles[currentPid]) {
          profileState.profiles[currentPid].name = nameValue;
        }
        // Bỏ tick checkbox khi lưu profile_id (dù không đổi ID)
        if (profileState.selected && profileState.selected[currentPid]) {
          delete profileState.selected[currentPid];
        }
        selectCb.checked = false;
      }

      saveProfileState();
      saveFrontendState(); // Lưu state vào backend
      updateSettingsActionButtons(); // Cập nhật trạng thái các nút
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
          name: '',
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

  actions.appendChild(saveBtn);

  actions.appendChild(groupBtn);
  actions.appendChild(cookieBtn);
  actions.appendChild(tokenBtn);
  actions.appendChild(removeBtn);
  selectWrap.appendChild(selectCb);
  row.appendChild(selectWrap);
  row.appendChild(nameInput);
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
  saveBtn.className = 'btn-primary';
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
            name: '',
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

// Hàm helper để chạy feed và đợi hoàn thành
async function runFeedAndWait(selected, text, runMinutes) {
  return new Promise((resolve, reject) => {
    callBackend('/feed/start', {
      method: 'POST',
      body: JSON.stringify({
        profile_ids: selected,
        mode: 'feed',
        text: text,
        run_minutes: runMinutes,
        rest_minutes: 0, // Luôn set restMinutes = 0 để feed chạy một lần và dừng
      }),
    })
      .then((res) => {
        const started = res && Array.isArray(res.started) ? res.started.length : 0;
        const skipped = res && Array.isArray(res.skipped) ? res.skipped.length : 0;
        showToast(`Đã chạy nuôi acc (feed): started=${started}, skipped=${skipped}`, 'success', 2000);

        // Đợi một chút để backend kịp start
        setTimeout(() => {
          // Poll status để đợi feed hoàn thành
          let pollCount = 0;
          const maxPolls = Math.ceil((runMinutes * 60 + 60) / 4); // Tối đa = thời gian chạy + 1 phút buffer, poll mỗi 4 giây
          const pollTimer = setInterval(async () => {
            pollCount++;
            if (pollCount > maxPolls) {
              clearInterval(pollTimer);
              reject(new Error('Feed quá lâu, đã timeout'));
              return;
            }
            
            try {
              const st = await callBackendNoAlert('/feed/status', { method: 'GET' });
              if (st) {
                const running = Array.isArray(st.running) ? st.running : [];
                const still = selected.filter((pid) => running.includes(pid));
                if (still.length === 0) {
                  clearInterval(pollTimer);
                  resolve();
                }
              }
            } catch (e) {
              clearInterval(pollTimer);
              reject(new Error('Không lấy được trạng thái feed (kiểm tra FastAPI).'));
            }
          }, 4000);
        }, 2000); // Đợi 2 giây trước khi bắt đầu poll
      })
      .catch((e) => {
        reject(new Error('Không chạy được feed (kiểm tra FastAPI).'));
      });
  });
}

// Hàm helper để chạy search và đợi hoàn thành
async function runSearchAndWait(selected, text, runMinutes) {
  return new Promise((resolve, reject) => {
    callBackend('/feed/start', {
      method: 'POST',
      body: JSON.stringify({
        profile_ids: selected,
        mode: 'search',
        text: text,
        run_minutes: runMinutes,
        rest_minutes: 0, // Luôn set restMinutes = 0 để search chạy một lần và dừng
      }),
    })
      .then((res) => {
        const started = res && Array.isArray(res.started) ? res.started.length : 0;
        const skipped = res && Array.isArray(res.skipped) ? res.skipped.length : 0;
        showToast(`Đã chạy nuôi acc (search): started=${started}, skipped=${skipped}`, 'success', 2000);

        // Đợi một chút để backend kịp start
        setTimeout(() => {
          // Poll status để đợi search hoàn thành
          let pollCount = 0;
          const maxPolls = Math.ceil((runMinutes * 60 + 60) / 4); // Tối đa = thời gian chạy + 1 phút buffer, poll mỗi 4 giây
          const pollTimer = setInterval(async () => {
            pollCount++;
            if (pollCount > maxPolls) {
              clearInterval(pollTimer);
              reject(new Error('Search quá lâu, đã timeout'));
              return;
            }
            
            try {
              const st = await callBackendNoAlert('/feed/status', { method: 'GET' });
              if (st) {
                const running = Array.isArray(st.running) ? st.running : [];
                const still = selected.filter((pid) => running.includes(pid));
                if (still.length === 0) {
                  clearInterval(pollTimer);
                  resolve();
                }
              }
            } catch (e) {
              clearInterval(pollTimer);
              reject(new Error('Không lấy được trạng thái search (kiểm tra FastAPI).'));
            }
          }, 4000);
        }, 2000); // Đợi 2 giây trước khi bắt đầu poll
      })
      .catch((e) => {
        reject(new Error('Không chạy được search (kiểm tra FastAPI).'));
      });
  });
}

// Hàm helper để nghỉ và đợi
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
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
    const runMinutes = parseFloat(String(feedRunMinutesInput?.value || '30').trim()) || 30;
    const restMinutes = parseFloat(String(feedRestMinutesInput?.value || '0').trim()) || 0;

    // Feed: cho phép text rỗng (quét theo keyword mặc định). Search và Feed+Search: bắt buộc có text.
    if (!text && (mode === 'search' || mode === 'feed+search' || mode === 'feed_search')) {
      showToast('Search và Feed+Search cần nhập text.', 'error');
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
      // Chạy mode thông thường (feed hoặc search)
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

        // Luôn poll status để cập nhật loading state (kể cả khi có loop)
        if (feedPollTimer) clearInterval(feedPollTimer);
        feedPollTimer = setInterval(async () => {
          try {
            const st = await callBackendNoAlert('/feed/status', { method: 'GET' });
            const running = (st && Array.isArray(st.running)) ? st.running : [];
            const still = selected.filter((pid) => running.includes(pid));
            if (still.length === 0) {
              // Không còn profile nào đang chạy -> tắt loading
              clearInterval(feedPollTimer);
              feedPollTimer = null;
              setButtonLoading(feedStartBtn, false);
              setButtonLoading(feedAccountSettingBtn, false);
              // Chỉ hiển thị "Hoàn thành" nếu không có loop (restMinutes <= 0)
              if (restMinutes <= 0) {
                showToast('✅ Nuôi acc: Hoàn thành', 'success', 2000);
              }
            } else {
              // Vẫn còn profile đang chạy -> giữ loading state
              if (!feedStartBtn.classList.contains('btn-loading')) {
                setButtonLoading(feedStartBtn, true, 'Đang chạy...');
              }
              if (!feedAccountSettingBtn.classList.contains('btn-loading')) {
                setButtonLoading(feedAccountSettingBtn, true, 'Đang nuôi acc...');
              }
            }
          } catch (e) {
            clearInterval(feedPollTimer);
            feedPollTimer = null;
            setButtonLoading(feedStartBtn, false);
            setButtonLoading(feedAccountSettingBtn, false);
            showToast('Không lấy được trạng thái nuôi acc (kiểm tra FastAPI).', 'error');
          }
        }, 4000);
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

    // Disable button và hiển thị loading
    setButtonLoading(groupScanStartBtn, true, 'Đang quét group...');
    setButtonLoading(scanGroupSettingBtn, true, 'Đang quét group...');
    
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

      // Poll trạng thái quét group để biết khi nào hoàn thành
      if (groupScanPollTimer) clearInterval(groupScanPollTimer);
      groupScanPollTimer = setInterval(async () => {
        try {
          const st = await callBackendNoAlert('/scan-groups/status', { method: 'GET' });
          const processing = st && typeof st.processing === 'boolean' ? st.processing : false;
          const queueLength = st && typeof st.queue_length === 'number' ? st.queue_length : 0;
          
          // Nếu không còn đang xử lý và queue rỗng thì hoàn thành
          if (!processing && queueLength === 0) {
            clearInterval(groupScanPollTimer);
            groupScanPollTimer = null;
            setButtonLoading(groupScanStartBtn, false);
            setButtonLoading(scanGroupSettingBtn, false);
            showToast('✅ Quét group: Hoàn thành', 'success', 2000);
          }
        } catch (e) {
          // Nếu lỗi poll thì dừng poll để không spam
          clearInterval(groupScanPollTimer);
          groupScanPollTimer = null;
          setButtonLoading(groupScanStartBtn, false);
          setButtonLoading(scanGroupSettingBtn, false);
          showToast('Không lấy được trạng thái quét group (kiểm tra FastAPI).', 'error');
        }
      }, 4000);
      
    } catch (error) {
      console.error('Lỗi khi quét group:', error);
      showToast(`❌ Lỗi: ${error.message}`, 'error', 4000);
      setButtonLoading(groupScanStartBtn, false);
      setButtonLoading(scanGroupSettingBtn, false);
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

    const runMinutes = parseFloat(String(scanRunMinutesInput?.value || '0').trim()) || 0;
    const restMinutes = parseFloat(String(scanRestMinutesInput?.value || '0').trim()) || 0;
    const text = String(scanTextInput?.value || '').trim();
    const mode = String(document.querySelector('input[name="scanMode"]:checked')?.value || 'feed').trim().toLowerCase();

    // Search và Feed+Search: bắt buộc có text
    if ((mode === 'search' || mode === 'feed+search' || mode === 'feed_search') && !text) {
      showToast('Search và Feed+Search cần nhập text để search.', 'error');
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

// Chạy lấy thông tin liên tục: cứ có bài là quét, không có thì tạm ngừng, có bài lại quét tiếp
async function runContinuousInfoCollector() {
  if (!isContinuousInfoCollectorRunning) {
    console.log('⚠️ Continuous info collector: Không đang chạy, bỏ qua');
    return;
  }

  try {
    // Check xem có post_ids không
    const res = await callBackendNoAlert('/data/post-ids', { method: 'GET' });
    console.log('🔍 Continuous info collector: Check post_ids response:', res);
    
    // Check xem có files và có ít nhất 1 file có post_ids không
    const hasPosts = res && res.files && Array.isArray(res.files) && res.files.length > 0 && res.total > 0;

    console.log(`🔍 Continuous info collector: hasPosts=${hasPosts}, files.length=${res?.files?.length || 0}, total=${res?.total || 0}, isInfoCollectorRunning=${isInfoCollectorRunning}`);

    if (hasPosts) {
      // Có bài viết, chạy lấy thông tin
      console.log('🔄 Continuous info collector: Có bài viết, bắt đầu lấy thông tin...');

      // Chỉ chạy nếu không đang chạy lấy thông tin
      if (!isInfoCollectorRunning) {
        console.log('✅ Continuous info collector: Bắt đầu chạy runInfoCollector("all", skipScanCheck=true)');
        // Chạy không await để không block polling, skipScanCheck=true để chạy ngay cả khi đang scanning
        runInfoCollector('all', true).catch(e => {
          console.error('❌ Lỗi khi chạy lấy thông tin liên tục:', e);
          // Nếu lỗi "không có dữ liệu bài viết", tiếp tục polling
          const errorMsg = (e?.message || e?.detail || String(e) || '').toLowerCase();
          if (!errorMsg.includes('không có dữ liệu bài viết') &&
              !errorMsg.includes('khong co du lieu bai viet') &&
              !errorMsg.includes('no data') &&
              !errorMsg.includes('empty')) {
            // Lỗi khác, có thể dừng polling
            console.warn('⚠️ Lỗi nghiêm trọng, dừng continuous info collector');
            stopContinuousInfoCollector();
          }
        });
      } else {
        console.log('⏸️ Continuous info collector: Đang chạy lấy thông tin, bỏ qua');
      }
    } else {
      // Không có bài viết, đợi lâu hơn trước khi check lại
      console.log('⏸️ Continuous info collector: Không có bài viết, đợi...');
    }
  } catch (e) {
    console.error('❌ Lỗi khi check post_ids:', e);
    // Lỗi khi check, đợi một lúc rồi thử lại
  }
}

// Bắt đầu chạy lấy thông tin liên tục
function startContinuousInfoCollector() {
  if (isContinuousInfoCollectorRunning) {
    console.log('⚠️ Continuous info collector: Đã đang chạy, bỏ qua');
    return;
  }

  isContinuousInfoCollectorRunning = true;
  console.log('🚀 Bắt đầu chạy lấy thông tin liên tục');

  // Chạy ngay lập tức lần đầu
  runContinuousInfoCollector();

  // Sau đó poll mỗi 30 giây để check có bài viết mới không
  if (continuousInfoCollectorInterval) {
    clearInterval(continuousInfoCollectorInterval);
    continuousInfoCollectorInterval = null;
  }
  continuousInfoCollectorInterval = setInterval(() => {
    if (isContinuousInfoCollectorRunning) {
      console.log('⏰ Continuous info collector: Polling check post_ids...');
      runContinuousInfoCollector();
    } else {
      console.log('⚠️ Continuous info collector: Đã dừng, clear interval');
      if (continuousInfoCollectorInterval) {
        clearInterval(continuousInfoCollectorInterval);
        continuousInfoCollectorInterval = null;
      }
    }
  }, 30000); // 30 giây
  console.log(`✅ Continuous info collector: Interval đã được set (mỗi 30 giây), interval ID: ${continuousInfoCollectorInterval}`);
}

// Dừng chạy lấy thông tin liên tục
function stopContinuousInfoCollector() {
  if (continuousInfoCollectorInterval) {
    clearInterval(continuousInfoCollectorInterval);
    continuousInfoCollectorInterval = null;
  }
  isContinuousInfoCollectorRunning = false;
  console.log('🛑 Dừng chạy lấy thông tin liên tục');
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
  // Ẩn toast số user đã quét được
  const infoUserCountToast = document.getElementById('infoUserCountToast');
  if (infoUserCountToast) infoUserCountToast.style.display = 'none';
  // Reset tracking
  lastRowCountForToast = null;
}

async function handleStopAll() {
  console.log('[UI] STOP ALL triggered');
  
  // Dừng continuous info collector trước
  stopContinuousInfoCollector();
  
  // Reset info collector state ngay lập tức
  resetInfoCollectorState();
  
  // stop-all có thể bấm từ left panel, setting header, hoặc tab kết quả
  const btns = [stopAllBtn, stopAllSettingBtn, stopScanBtn].filter(Boolean);
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
    setButtonLoading(startScanBtn, false);
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
    if (groupScanPollTimer) {
      clearInterval(groupScanPollTimer);
      groupScanPollTimer = null;
    }
    setButtonLoading(autoJoinGroupBtn, false);
    setButtonLoading(feedAccountSettingBtn, false);
    setButtonLoading(feedStartBtn, false);
    setButtonLoading(scanGroupSettingBtn, false);
    setButtonLoading(groupScanStartBtn, false);
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
        // Khi dừng quét, nếu đang ở tab scan thì bật lại autoRefreshInterval
        if (scanView && scanView.style.display !== 'none') {
          startAutoRefresh();
        }
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
      // Khi dừng quét, nếu đang ở tab scan thì bật lại autoRefreshInterval
      if (scanView && scanView.style.display !== 'none') {
        startAutoRefresh();
      }
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
    if (!dataCheckInterval) {
      // Tắt autoRefreshInterval khi bắt đầu quét (dùng dataCheckInterval thay thế)
      stopAutoRefresh();
      dataCheckInterval = setInterval(checkForNewData, 5000);
    }
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
  // Comment: hiển thị comment trực tiếp thay vì icon
  const hasComment = !!comment;
  const commentDisplay = hasComment ? `<span class="comment-text">${comment}</span>` : '';

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

  // Lưu comment vào tr.dataset để dễ truy cập khi xuất Excel
  if (hasComment) {
    tr.dataset.comment = comment;
  }
  
  // Gắn dữ liệu comment và sự kiện click cho icon con mắt
  if (hasComment) {
    const commentCell = tr.children[4]; // cột Comment
    commentCell.dataset.comment = comment;
    commentCell.dataset.showingText = 'false'; // Trạng thái: false = đang hiển thị icon, true = đang hiển thị text

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

  // Bỏ qua post có text chứa CSS code của Facebook
  if (text.includes(':root') || text.includes('__fb-light-mode') || text.includes('__fb-dark-mode')) {
    return; // Không hiển thị post này
  }

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
    const filename = res.filename;
    const data = res.data;
    
    // Nếu filename khác với filename hiện tại, reload toàn bộ
    if (currentResultsFilename && filename !== currentResultsFilename) {
      console.log(`Phát hiện file mới: ${filename} (file cũ: ${currentResultsFilename}), reload toàn bộ...`);
      currentResultsFilename = filename;
      // Reset tracking rowCount khi file mới được tạo
      if (isInfoCollectorRunning) {
        lastRowCountForToast = null;
      }
      await loadInitialData();
      return;
    }
    
    // Cập nhật filename nếu chưa có
    if (!currentResultsFilename) {
      currentResultsFilename = filename;
    }

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
            time: '',
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
          (comment && comment.created_time_vn) ? comment.created_time_vn : '';

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
  
  // Reset tracking rowCount nếu đang lấy thông tin (để toast có thể hiển thị với rowCount mới)
  if (isInfoCollectorRunning) {
    lastRowCountForToast = null;
  }

  try {
    // Gọi API để lấy file JSON có timestamp lớn nhất
    const res = await callBackend('/data/latest-results', { method: 'GET' });
    const filename = res.filename;
    const data = res.data;
    
    // Cập nhật filename hiện tại
    currentResultsFilename = filename;
    
    console.log(`Đã load file JSON gần nhất: ${filename}, tổng số files:`, data.total_files);

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
            time: '',
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
          (comment && comment.created_time_vn) ? comment.created_time_vn : '';

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
// Track profile đã toast trong pollAccountStatus để tránh spam
let polledBannedProfiles = new Set();

async function pollAccountStatus() {
  try {
    const res = await callBackendNoAlert('/account/status', { method: 'GET' });
    if (!res || !res.accounts) return;

    const accounts = res.accounts || {};
    Object.keys(accounts).forEach((pid) => {
      const info = accounts[pid];
      if (!info) return;
      if (!info.banned) return;
      
      // Chỉ toast 1 lần cho mỗi profile để tránh spam
      if (polledBannedProfiles.has(pid)) return;
      polledBannedProfiles.add(pid);

      // Tạo message đầy đủ thông tin
      let detailMsg = `Profile: ${pid}`;
      if (info.title) {
        detailMsg += `\nTitle: ${info.title}`;
      }
      
      if (info.url) {
        detailMsg += `\nURL: ${info.url}`;
      }
      
      
      const msg = info.message || 'Tài khoản có vấn đề, hãy kiểm tra lại bằng tay.';
      const fullMessage = `${msg}\n${detailMsg}`;
      showToast(fullMessage, 'error', 12000);
    });
  } catch (e) {
    // bỏ qua lỗi, không ảnh hưởng luồng cũ
  }
}

// Poll mỗi 45s, hoàn toàn độc lập, chỉ hiển thị thông báo
try {
  setInterval(pollAccountStatus, 45000);
} catch (_) { }

// Hàm helper để chạy scan và đợi hoàn thành
async function runScanAndWait(runMinutes, restMinutes, text, mode) {
  return new Promise((resolve, reject) => {
    triggerBackendRun({ runMinutes, restMinutes, text, mode })
      .then((ok) => {
        if (!ok) {
          reject(new Error('Không chạy được scan'));
          return;
        }
        
        // Đợi một chút để backend kịp start
        setTimeout(() => {
          // Poll status để đợi scan hoàn thành
          let pollCount = 0;
          const maxPolls = Math.ceil((runMinutes * 60 + 60) / 2); // Tối đa = thời gian chạy + 1 phút buffer, poll mỗi 2 giây
          const pollTimer = setInterval(async () => {
            pollCount++;
            if (pollCount > maxPolls) {
              clearInterval(pollTimer);
              reject(new Error('Scan quá lâu, đã timeout'));
              return;
            }
            
            try {
              const st = await callBackendNoAlert('/jobs/status', { method: 'GET' });
              if (st) {
                const botRunning = st.bot_running === true;
                if (!botRunning) {
                  clearInterval(pollTimer);
                  resolve();
                }
              }
            } catch (e) {
              clearInterval(pollTimer);
              reject(new Error('Không lấy được trạng thái scan (kiểm tra FastAPI).'));
            }
          }, 2000); // Poll mỗi 2 giây
        }, 2000); // Đợi 2 giây trước khi bắt đầu poll
      })
      .catch((e) => {
        reject(new Error(e.message || 'Không chạy được scan (kiểm tra FastAPI).'));
      });
  });
}

// Hàm helper để chạy group scan và đợi hoàn thành
async function runGroupScanAndWait(selected, postCount, startDate, endDate) {
  return new Promise((resolve, reject) => {
    callBackend('/scan-groups', {
      method: 'POST',
      body: JSON.stringify({
        profile_ids: selected,
        post_count: postCount,
        start_date: startDate,
        end_date: endDate
      })
    })
      .then(() => {
        // Poll trạng thái quét group để đợi hoàn thành
        let pollCount = 0;
        const maxPolls = 3600; // Tối đa 1 giờ (3600 * 1 giây)
        const pollTimer = setInterval(async () => {
          pollCount++;
          if (pollCount > maxPolls) {
            clearInterval(pollTimer);
            reject(new Error('Quét group quá lâu, đã timeout'));
            return;
          }
          
          try {
            const st = await callBackendNoAlert('/scan-groups/status', { method: 'GET' });
            if (st) {
              const processing = st.processing === true;
              const queueLength = typeof st.queue_length === 'number' ? st.queue_length : 0;
              
              // Nếu không còn đang xử lý và queue rỗng thì hoàn thành
              if (!processing && queueLength === 0) {
                clearInterval(pollTimer);
                resolve();
              }
            }
          } catch (e) {
            clearInterval(pollTimer);
            reject(new Error('Không lấy được trạng thái quét group (kiểm tra FastAPI).'));
          }
        }, 1000); // Poll mỗi 1 giây
      })
      .catch((e) => {
        reject(new Error(e.message || 'Không chạy được quét group (kiểm tra FastAPI).'));
      });
  });
}

// Hàm helper để chạy lấy thông tin và đợi hoàn thành
async function runInfoCollectorAndWait(mode = 'selected') {
  return new Promise((resolve, reject) => {
    const isSelected = mode === 'selected';
    const selected = getSelectedProfileIds();
    
    if (isSelected && selected.length === 0) {
      reject(new Error('Chọn (tick) ít nhất 1 profile trước.'));
      return;
    }
    
    const body = { mode: isSelected ? 'selected' : 'all' };
    if (isSelected) body.profiles = selected;
    
    callBackend('/info/run', {
      method: 'POST',
      body: JSON.stringify(body),
    })
      .then(() => {
        // Đợi một chút để backend kịp start
        setTimeout(() => {
          // Poll trạng thái để đợi hoàn thành
          let pollCount = 0;
          const maxPolls = 1800; // Tối đa 1 giờ (1800 * 2 giây)
          const pollTimer = setInterval(async () => {
            pollCount++;
            if (pollCount > maxPolls) {
              clearInterval(pollTimer);
              reject(new Error('Lấy thông tin quá lâu, đã timeout'));
              return;
            }
            
            try {
              const res = await callBackendNoAlert('/info/progress', { method: 'GET' });
              if (res) {
                const isRunning = res.is_running === true;
                if (!isRunning) {
                  clearInterval(pollTimer);
                  resolve();
                }
              }
            } catch (e) {
              clearInterval(pollTimer);
              reject(new Error('Không lấy được trạng thái lấy thông tin (kiểm tra FastAPI).'));
            }
          }, 2000); // Poll mỗi 2 giây
        }, 2000); // Đợi 2 giây trước khi bắt đầu poll
      })
      .catch((e) => {
        reject(new Error(e.message || 'Không chạy được lấy thông tin (kiểm tra FastAPI).'));
      });
  });
}

// Start quét bài viết với multi-thread (feed+search + group scan song song)
async function startScanFlowMultiThread(options = {}) {
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
    postCount,
    startDate,
    endDate
  } = options || {};
  
  try {
    // Load và hiển thị tất cả dữ liệu từ all_results_summary.json ngay lập tức
    await loadInitialData();

    // Nếu đang có interval check data cũ thì clear trước để tránh setInterval chồng
    if (dataCheckInterval) {
      clearInterval(dataCheckInterval);
      dataCheckInterval = null;
    }

    // Gọi multi-thread endpoint
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile để quét bài viết.', 'error');
      setScanning(false);
      return;
    }

    const payload = {
      profile_ids: selected,
      run_minutes: runMinutes,
      rest_minutes: restMinutes,
      text: text,
      mode: mode
    };

    // Thêm group scan params nếu có
    if (postCount && startDate && endDate) {
      payload.post_count = postCount;
      payload.start_date = startDate;
      payload.end_date = endDate;
    }

    const data = await callBackend('/run-multi-thread', {
      body: JSON.stringify(payload),
    });

    if (data.status === 'error' || data.status === 'partial') {
      const errorMsg = data.message || 'Lỗi không xác định';
      showToast(`❌ ${errorMsg}`, 'error', 4000);
      if (data.errors) {
        console.error('Multi-thread errors:', data.errors);
      }
      setScanning(false);
      return;
    }

    showToast('✅ Đã khởi động quét song song (feed+search + group)', 'success', 3000);

    // Tự động kiểm tra dữ liệu mới mỗi 5 giây
    const checkInterval = 5000;
    // Tắt autoRefreshInterval khi bắt đầu quét (dùng dataCheckInterval thay thế)
    stopAutoRefresh();
    dataCheckInterval = setInterval(checkForNewData, checkInterval);

    setScanning(true);
    
    // Reset danh sách profile die đã toast khi bắt đầu quét mới
    notifiedDeadProfiles.clear();
    polledBannedProfiles.clear();
    
    // Bắt đầu poll số bài đã quét được
    if (scanStatsInterval) clearInterval(scanStatsInterval);
    updateScanStats(); // Cập nhật ngay lập tức
    scanStatsInterval = setInterval(updateScanStats, 3000); // Poll mỗi 3 giây
    
    // Poll /run-multi-thread/status để sync UI
    try { startScanBackendPoll({ silent: true }); } catch (_) { }
    try { updateStopPauseButtonsByJobs(); } catch (_) { }
    try { await refreshControlState(); } catch (_) { }
  } catch (err) {
    console.error('Lỗi trong startScanFlowMultiThread:', err);
    setScanning(false);
    throw err;
  }
}

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
    // Tắt autoRefreshInterval khi bắt đầu quét (dùng dataCheckInterval thay thế)
    stopAutoRefresh();
    dataCheckInterval = setInterval(checkForNewData, checkInterval);

    setScanning(true);
    
    // Reset danh sách profile die đã toast khi bắt đầu quét mới
    notifiedDeadProfiles.clear();
    polledBannedProfiles.clear();
    
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
const startScanBtn = document.getElementById('startScanBtn');
const stopScanBtn = document.getElementById('stopScanBtn');

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
      }
      // Cột thứ 5 (index 4) là Comment - lấy nội dung từ tr.dataset.comment hoặc td.dataset.comment
      else if (colIndex === 4) {
        // Ưu tiên lấy từ tr.dataset.comment (đã lưu khi appendRow)
        let commentText = tr.dataset.comment || '';
        
        // Nếu không có, thử lấy từ td.dataset.comment
        if (!commentText) {
          commentText = td.getAttribute('data-comment') || td.dataset.comment || '';
        }
        
        // Nếu vẫn không có, kiểm tra xem có phần tử .comment-text không (user đã click để hiển thị)
        if (!commentText) {
          const commentTextElement = td.querySelector('.comment-text');
          if (commentTextElement) {
            commentText = commentTextElement.textContent || '';
          }
        }
        
        row.push(commentText);
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
    { wch: 25 }, // Name
    { wch: 12 }, // React
    { wch: 40 }, // Comment - tăng độ rộng để chứa nội dung dài
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

// Nút "Lọc Excel"
const sterilizeExcelBtn = document.getElementById('sterilizeExcelBtn');

function sterilizeExcel() {
  // Tạo input file ẩn
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.xlsx';
  input.multiple = true; // Cho phép chọn nhiều file
  input.style.display = 'none';
  
  let inputCleaned = false;
  
  const cleanupInput = () => {
    if (!inputCleaned) {
      inputCleaned = true;
      if (input.parentNode) {
        input.remove();
      }
    }
  };
  
  input.onchange = async (e) => {
    const files = Array.from(e.target.files);
    cleanupInput(); // Cleanup ngay sau khi chọn file
    
    if (files.length === 0) {
      return;
    }
    
    // Kiểm tra tất cả file đều là .xlsx
    const invalidFiles = files.filter(f => !f.name.toLowerCase().endsWith('.xlsx'));
    if (invalidFiles.length > 0) {
      showToast('Tất cả file phải có định dạng .xlsx', 'error');
      return;
    }
    
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    
    try {
      // Disable button và hiển thị trạng thái loading
      sterilizeExcelBtn.disabled = true;
      const btnText = sterilizeExcelBtn.querySelector('span:last-child');
      const originalText = btnText.textContent;
      btnText.textContent = 'Đang lọc...';
      
      // Gọi API
      const response = await fetch('http://localhost:8000/excel/sterilize', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Lỗi không xác định' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      
      // Lấy file từ response
      const blob = await response.blob();
      
      // Tạo URL tạm thời và download file
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Lấy filename từ header hoặc dùng tên mặc định
      const contentDisposition = response.headers.get('content-disposition');
      let filename = 'sterilized.xlsx';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      // Hiển thị thông báo thành công
      showToast(`Đã lọc thành công ${files.length} file(s)`, 'success');
      btnText.textContent = 'Đã lọc!';
      
      setTimeout(() => {
        btnText.textContent = originalText;
        sterilizeExcelBtn.disabled = false;
      }, 2000);
      
    } catch (error) {
      console.error('Lỗi khi lọc Excel:', error);
      showToast(`Lỗi khi lọc Excel: ${error.message}`, 'error');
      
      // Restore button state
      const btnText = sterilizeExcelBtn.querySelector('span:last-child');
      const originalText = btnText.textContent;
      btnText.textContent = 'Lỗi!';
      setTimeout(() => {
        btnText.textContent = originalText;
        sterilizeExcelBtn.disabled = false;
      }, 2000);
    }
  };
  
  // Cleanup input sau một khoảng thời gian (nếu user cancel dialog)
  setTimeout(cleanupInput, 100);
  
  // Trigger click để mở file dialog
  document.body.appendChild(input);
  input.click();
}

if (sterilizeExcelBtn) {
  sterilizeExcelBtn.addEventListener('click', sterilizeExcel);
}

// Nút "Bắt đầu" trong tab kết quả
if (startScanBtn) {
  startScanBtn.addEventListener('click', async () => {
    // Kiểm tra đang quét
    if (isScanning) {
      showToast('Đang quét, vui lòng đợi hoặc bấm dừng trước', 'warning');
      return;
    }
    
    // Kiểm tra profile đã chọn
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile để quét bài viết.', 'error');
      try { switchTab('settings'); } catch (_) { }
      return;
    }

    // Lấy settings từ inputs hoặc giá trị mặc định
    const runMinutes = parseFloat(String(scanRunMinutesInput?.value || '30').trim()) || 30;
    const restMinutes = parseFloat(String(scanRestMinutesInput?.value || '0').trim()) || 0;
    const text = String(scanTextInput?.value || '').trim();
    // Nút "Bắt đầu" luôn mặc định chạy mode feed+search
    const mode = 'feed+search';

    // Feed+Search: bắt buộc có text
    if (!text) {
      showToast('Feed+Search cần nhập text để search.', 'error');
      return;
    }

    // Lấy thông tin group scan (nếu có)
    const postCount = parseInt(String(groupScanPostCountInput?.value || '0').trim(), 10) || 10;
    const startDate = String(groupScanStartDateInput?.value || '').trim();
    const endDate = String(groupScanEndDateInput?.value || '').trim();

    setButtonLoading(startScanBtn, true, 'Đang chạy...');
    try {
      // Chạy 3 cái cùng lúc: feed+search, group scan, và lấy thông tin liên tục
      // 1. Chạy feed+search và group scan
      await startScanFlowMultiThread({ 
        runMinutes, 
        restMinutes, 
        text, 
        mode,
        postCount,
        startDate,
        endDate
      });
      
      // 2. Bắt đầu chạy lấy thông tin liên tục (không chờ)
      console.log('📍 [startScanBtn] Gọi startContinuousInfoCollector()...');
      startContinuousInfoCollector();
      console.log('📍 [startScanBtn] Đã gọi startContinuousInfoCollector()');
      
      showToast('✅ Đã khởi động quét feed+search, group scan và lấy thông tin liên tục', 'success', 3000);
    } catch (e) {
      showToast('Không chạy được quét bài viết (kiểm tra FastAPI).', 'error');
      setButtonLoading(startScanBtn, false);
      setScanning(false);
      // Nếu lỗi thì cũng dừng continuous info collector
      stopContinuousInfoCollector();
    }
  });
}

// Nút "Dừng" trong tab kết quả - gọi cùng hàm handleStopAll
if (stopScanBtn) {
  stopScanBtn.addEventListener('click', handleStopAll);
}

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
// Time filter elements - commented out vì đã bỏ time filter
// const timeFilterFrom = document.getElementById('timeFilterFrom');
// const timeFilterTo = document.getElementById('timeFilterTo');
// const applyTimeFilterBtn = document.getElementById('applyTimeFilterBtn');
// const clearTimeFilterBtn = document.getElementById('clearTimeFilterBtn');

// Sử dụng Set để lưu các filter đã chọn (cho phép nhiều lựa chọn)
let selectedTypeFilters = new Set(['all']);
let selectedReactFilters = new Set(); // Không có "all", rỗng = hiển thị tất cả
let selectedCommentFilters = new Set(); // Không có "all", rỗng = hiển thị tất cả
// Time filter values - commented out vì đã bỏ time filter
// let timeFilterFromValue = null; // Thời gian bắt đầu
// let timeFilterToValue = null; // Thời gian kết thúc

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
      const hasComment = commentCell && commentCell.textContent.trim() !== '';
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

    // Filter theo thời gian - commented out vì đã bỏ time filter
    /*
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
    */

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

// Time filter functions - commented out vì đã bỏ time filter
/*
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
*/

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

// Time filter event listeners - commented out vì đã bỏ time filter
/*
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
*/

// Flag để track khi đang chạy info collector
let isInfoCollectorRunning = false;
let scanStatsInterval = null;
let infoProgressInterval = null;
// Track profile die/banned đã toast để không toast lại
let notifiedDeadProfiles = new Set();

// Hàm để cập nhật số bài đã quét được
async function updateScanStats() {
  try {
    const res = await callBackendNoAlert('/info/scan-stats', { method: 'GET' });
    if (!res || !res.stats) return;
    
    // Lấy account status để check profile die/banned
    let accountStatus = {};
    try {
      const statusRes = await callBackendNoAlert('/account/status', { method: 'GET' });
      if (statusRes && statusRes.accounts) {
        accountStatus = statusRes.accounts;
      }
    } catch (e) {
      // Ignore errors khi lấy account status
    }
    
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
    let profilesToShow = selected.length > 0 ? selected : Object.keys(stats);
    
    // 🆕 Lọc bỏ profile die/banned khỏi danh sách hiển thị
    const deadProfiles = [];
    profilesToShow = profilesToShow.filter(pid => {
      const status = accountStatus[pid];
      if (status && (status.banned === true || status.status === 'banned' || status.status === 'dead')) {
        deadProfiles.push(pid);
        return false; // Loại bỏ profile die khỏi danh sách hiển thị
      }
      return true; // Giữ lại profile còn sống
    });
    
    // 🆕 Toast cảnh báo khi phát hiện profile die/banned mới
    if (deadProfiles.length > 0) {
      const newDead = deadProfiles.filter(pid => !notifiedDeadProfiles.has(pid));
      if (newDead.length > 0) {
        // Đánh dấu đã toast để không toast lại
        newDead.forEach(pid => notifiedDeadProfiles.add(pid));
        
        // Toast cảnh báo nổi bật với đầy đủ thông tin
        if (newDead.length === 1) {
          const pid = newDead[0];
          const status = accountStatus[pid];
          if (status) {
            // Tạo message chi tiết
            let detailMsg = `Profile: ${pid}`;
            if (status.title) {
              detailMsg += `\nTitle: ${status.title}`;
            }
           
            if (status.url) {
              detailMsg += `\nURL: ${status.url}`;
            }
          
            const fullMessage = `${status.message || `Profile ${pid} bị khóa/bị ban`}\n${detailMsg}`;
            showToast(fullMessage, 'error', 12000);
          } else {
            showToast(`⛔ Profile ${pid} bị khóa/bị ban`, 'error', 8000);
          }
        } else {
          // Nhiều profile: hiển thị danh sách đầy đủ
          const details = newDead.map(pid => {
            const status = accountStatus[pid];
            if (status && status.title) {
              return `${pid} (${status.title})`;
            }
            return pid;
          }).join(', ');
          showToast(`⛔ Có ${newDead.length} profile bị khóa/bị ban:\n${details}`, 'error', 12000);
        }
      }
    }
    
    let html = '';
    for (const pid of profilesToShow) {
      const count = stats[pid] || 0;
      html += `<div style="padding: 8px 12px; background: rgba(0, 255, 13, 0.95); color: white; border-radius: 6px; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); white-space: nowrap;">
        <span style="font-weight: 600;">${pid}</span> : đã quét được <span style="font-weight: 700;">${count}</span> bài
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
        console.log('updateInfoProgress: Backend stopped, resetting state');
        resetInfoCollectorState();
      } else {
        console.log('updateInfoProgress: Backend started, keeping loading state');
      }
      updateStopPauseButtonsByJobs();
    }
    
    // Bỏ toast "đã lấy được 1/bao nhiêu bài" - không hiển thị nữa
    // Giữ lại logic để sync state nhưng không hiển thị toast
    if (res.is_running && res.total > 0) {
      // Không hiển thị toast nữa, chỉ sync state
      // toast.style.display = 'block';
      // progressToast.style.display = 'block';
    } else {
      // Ẩn toast nếu có
      if (toast) toast.style.display = 'none';
      // Reset progress bar
      if (progressBar) {
        progressBar.style.width = '0%';
      }
      // Ẩn progressToast nếu cả 2 toast đều ẩn
      const scanToast = document.getElementById('scanStatsToast');
      if (progressToast && (!scanToast || scanToast.style.display === 'none')) {
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

// Hàm helper để đợi quét xong (bot_running = false)
async function waitForScanToComplete(maxWaitSeconds = 300) {
  const startTime = Date.now();
  const maxWait = maxWaitSeconds * 1000;
  
  while (Date.now() - startTime < maxWait) {
    try {
      const st = await callBackendNoAlert('/jobs/status', { method: 'GET' });
      if (st) lastJobsStatus = st;
      
      const botHasProfiles = Array.isArray(st && st.bot_profile_ids) && st.bot_profile_ids.length > 0;
      const running = !!(st && st.bot_running && botHasProfiles);
      
      if (!running) {
        // Quét đã xong
        return true;
      }
      
      // Đợi 2 giây trước khi check lại
      await new Promise(resolve => setTimeout(resolve, 2000));
    } catch (e) {
      console.warn('Lỗi khi check trạng thái quét:', e);
      // Nếu lỗi, đợi 2 giây rồi thử lại
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  
  // Timeout - quét vẫn chưa xong sau maxWaitSeconds
  return false;
}

async function runInfoCollector(mode = 'all', skipScanCheck = false) {
  const isSelected = mode === 'selected';
  const btn = isSelected ? runSelectedInfoBtn : runAllInfoBtn;
  const selected = getSelectedProfileIds();

  if (isSelected && selected.length === 0) {
    showToast('Chọn (tick) ít nhất 1 profile trước.', 'error');
    try { switchTab('settings'); } catch (_) { }
    return;
  }

  // Kiểm tra xem quét có đang chạy không (bỏ qua nếu skipScanCheck = true - dùng cho continuous collector)
  if (!skipScanCheck) {
    try {
      const st = await callBackendNoAlert('/jobs/status', { method: 'GET' });
      if (st) lastJobsStatus = st;
      
      const botHasProfiles = Array.isArray(st && st.bot_profile_ids) && st.bot_profile_ids.length > 0;
      const isScanning = !!(st && st.bot_running && botHasProfiles);
      
      if (isScanning) {
        // Quét đang chạy, đợi quét xong
        setButtonLoading(btn, true, 'Đang đợi quét xong...');
        showToast('Đang đợi quét bài viết hoàn thành...', 'info', 3000);
        
        const scanCompleted = await waitForScanToComplete(60); // Đợi tối đa 5 phút
        
        if (!scanCompleted) {
          showToast('Quét vẫn chưa xong sau 1 phút. Bắt đầu lấy thông tin...', 'warning', 3000);
        } else {
          showToast('Quét đã xong. Bắt đầu lấy thông tin...', 'success', 2000);
          // Đợi thêm 1 giây để đảm bảo quét hoàn toàn xong
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
    } catch (e) {
      console.warn('Không thể kiểm tra trạng thái quét:', e);
      // Nếu lỗi, tiếp tục lấy thông tin bình thường
    }
  } else {
    console.log('🔄 runInfoCollector: Bỏ qua check scanning (skipScanCheck=true)');
  }

  // Đánh dấu đang chạy
  isInfoCollectorRunning = true;
  
  // Reset tracking rowCount để đảm bảo toast chỉ hiển thị khi có thay đổi mới
  lastRowCountForToast = null;
  
  // Reset rowCount về 0 và hiển thị toast ngay khi bắt đầu
  if (rowCount) {
    rowCount.textContent = '0';
  }
  updateInfoUserCountToast();
  
  // Hiển thị toast khi bắt đầu
  const startMsg = isSelected 
    ? `Đang lấy thông tin cho ${selected.length} profile đã chọn...` 
    : 'Đang lấy thông tin toàn bộ...';
  showToast(startMsg, 'info', 2000);
  
  // Set loading state TRƯỚC khi gọi các hàm update khác để tránh bị ghi đè
  console.log('runInfoCollector: Setting loading for button', btn.id, btn);
  setButtonLoading(btn, true, 'Đang lấy thông tin...');
  
  // Verify loading state was set
  console.log('runInfoCollector: After setButtonLoading - disabled:', btn.disabled, 'has btn-loading class:', btn.classList.contains('btn-loading'), 'classList:', btn.classList.toString());
  
  // Update buttons để enable pause/stop buttons (sau khi đã set loading)
  // Các hàm này sẽ skip nếu button đang loading
  updateStopPauseButtonsByJobs();
  updateSettingsActionButtons();
  
  // Verify loading state is still set after updates
  console.log('runInfoCollector: After updates - disabled:', btn.disabled, 'has btn-loading class:', btn.classList.contains('btn-loading'), 'classList:', btn.classList.toString());
  
  try {
    const body = { mode: isSelected ? 'selected' : 'all' };
    if (isSelected) body.profiles = selected;
    const res = await callBackend('/info/run', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    // Bỏ toast "posts: X" vì dư thừa - đã có toast "Đã cập nhật danh sách quét" ở dưới
    // const summary = res && res.summary ? res.summary : null;
    // Không hiển thị toast "posts: X" nữa

    // Bắt đầu poll tiến trình SAU KHI backend đã start (để tránh reset state quá sớm)
    if (infoProgressInterval) clearInterval(infoProgressInterval);
    // Đợi một chút để backend kịp start trước khi check progress
    setTimeout(() => {
      updateInfoProgress(); // Cập nhật sau khi backend đã start
      infoProgressInterval = setInterval(updateInfoProgress, 2000); // Poll mỗi 2 giây
    }, 1000);

    // Tự động tải lại danh sách quét với dữ liệu mới nhất theo timestamp
    try {
      await loadInitialData();
      // Sau khi loadInitialData() hoàn thành (rowCount đã reset đúng), mới hiển thị toast
      updateInfoUserCountToast();
      showToast('Đã cập nhật danh sách quét với dữ liệu mới nhất', 'success', 3500);
    } catch (loadErr) {
      console.warn('Không thể tải lại danh sách quét:', loadErr);
      // Không hiện lỗi cho user vì chức năng chính đã thành công
    }

    // KHÔNG reset state ở đây - để poll progress tự động reset khi backend dừng
    // resetInfoCollectorState();
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
    // KHÔNG reset loading ở đây nếu đang chạy thành công
    // Chỉ reset nếu có lỗi (đã được xử lý trong catch block)
    // Nếu thành công, để poll progress tự động reset khi backend dừng
    if (!isInfoCollectorRunning) {
      console.log('runInfoCollector finally: Resetting loading because not running');
      setButtonLoading(btn, false);
    } else {
      console.log('runInfoCollector finally: Keeping loading state, backend is running');
    }
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

// Time filter event listener - commented out vì đã bỏ time filter
/*
if (timeFilterTo) {
  timeFilterTo.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      applyTimeFilter();
    }
  });
}
*/

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
  
  // Bật/tắt auto-refresh khi ở tab kết quả
  if (key === 'scan') {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }

  // nhớ tab đang mở để không bị nhảy về tab đầu
  try {
    localStorage.setItem(ACTIVE_TAB_KEY, key);
  } catch (e) {
    // ignore
  }
}

// Bật auto-refresh khi ở tab kết quả
function startAutoRefresh() {
  // Nếu đã có interval thì không tạo mới
  if (autoRefreshInterval) {
    return;
  }
  
  // Nếu đang có dataCheckInterval (khi đang quét) thì không tạo autoRefreshInterval
  // vì dataCheckInterval đã đảm nhiệm việc check dữ liệu mới
  if (dataCheckInterval) {
    return;
  }
  
  // Tạo interval để kiểm tra dữ liệu mới mỗi 5 giây
  autoRefreshInterval = setInterval(async () => {
    // Chỉ chạy khi đang ở tab scan (kết quả) và không có dataCheckInterval đang chạy
    if (scanView && scanView.style.display !== 'none' && !dataCheckInterval) {
      try {
        await checkForNewData();
      } catch (err) {
        console.error('Lỗi khi auto-refresh dữ liệu:', err);
      }
    }
  }, 5000);
  
  console.log('Đã bật auto-refresh cho tab kết quả');
}

// Tắt auto-refresh
function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
    console.log('Đã tắt auto-refresh');
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
            time: '',
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
        const time = (comment && comment.created_time_vn) ? comment.created_time_vn : '';

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

    // Cập nhật hiển thị thời gian của file đã chọn
    updateFileTime(filename);

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
          [todayBtn].forEach(btn => btn.classList.remove('active'));
          if (rangeType === 'today') todayBtn.classList.add('active');
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

  if (days === 'today') {
    // Từ 00:00 hôm nay đến hiện tại
    const fromDate = new Date(now);
    fromDate.setHours(0, 0, 0, 0);
    const toDate = new Date(now);
    return { fromDate, toDate };
  } else {
    // Khoảng thời gian của N ngày trước (từ 00:00 đến 23:59)
    const targetDate = new Date(now);
    targetDate.setDate(targetDate.getDate() - days);

    const fromDate = new Date(targetDate);
    fromDate.setHours(0, 0, 0, 0);

    const toDate = new Date(targetDate);
    toDate.setHours(23, 59, 59, 999);

    return { fromDate, toDate };
  }
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
            time: '',
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
        const time = (comment && comment.created_time_vn) ? comment.created_time_vn : '';

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

// Event listeners cho date buttons
if (todayBtn) {
  todayBtn.addEventListener('click', async () => {
    const { fromDate, toDate } = setDateRange('today');
    await showFileSelector('today', fromDate, toDate);
  });
}


// Function định dạng ngày thành dd/mm
function formatDateForDisplay(daysAgo) {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  const day = date.getDate().toString().padStart(2, '0');
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  return `${day}/${month}`;
}

// Function kiểm tra xem ngày nào có data
async function checkDateHasData(daysAgo) {
  try {
    const now = new Date();
    const targetDate = new Date(now);
    targetDate.setDate(targetDate.getDate() - daysAgo);

    // Tạo khoảng thời gian từ 00:00 đến 23:59 của ngày đó
    const fromDate = new Date(targetDate);
    fromDate.setHours(0, 0, 0, 0);
    const toDate = new Date(targetDate);
    toDate.setHours(23, 59, 59, 999);

    // Gọi API để kiểm tra có file nào trong ngày đó không
    const res = await callBackend('/data/files-in-range', {
      method: 'POST',
      body: JSON.stringify({
        from_timestamp: Math.floor(fromDate.getTime() / 1000),
        to_timestamp: Math.floor(toDate.getTime() / 1000)
      })
    });

    const files = res.files || [];
    return files.length > 0;
  } catch (error) {
    console.error(`Error checking data for ${daysAgo} days ago:`, error);
    return false;
  }
}

// Date dropdown functionality
const selectDateBtn = document.getElementById('selectDateBtn');
const dateDropdown = document.getElementById('dateDropdown');
const dropdownContainer = selectDateBtn ? selectDateBtn.closest('.dropdown-container') : null;

// File time display
const currentTimeText = document.getElementById('currentTimeText');

// Function cập nhật thời gian hiện tại (mặc định)
function updateCurrentTime() {
  const now = new Date();
  const timeString = now.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });

  if (currentTimeText) {
    currentTimeText.textContent = timeString;
  }
}

// Function cập nhật thời gian của file đã chọn
function updateFileTime(filename) {
  try {
    // Parse tên file để lấy date và time
    // Format: all_results_YYYYMMDD_HHMMSS.json
    const pattern = /all_results_(\d{8})_(\d{6})\.json$/;
    const match = filename.match(pattern);

    if (match) {
      const dateStr = match[1]; // YYYYMMDD
      const timeStr = match[2]; // HHMMSS

      // Parse thành date object
      const year = dateStr.substring(0, 4);
      const month = dateStr.substring(4, 6);
      const day = dateStr.substring(6, 8);
      const hour = timeStr.substring(0, 2);
      const minute = timeStr.substring(2, 4);
      const second = timeStr.substring(4, 6);

      const fileDate = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}`);

      const timeString = fileDate.toLocaleString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });

      if (currentTimeText) {
        currentTimeText.textContent = timeString;
      }
    } else {
      // Nếu không parse được, quay về thời gian hiện tại
      updateCurrentTime();
    }
  } catch (error) {
    console.error('Error parsing file time:', error);
    updateCurrentTime();
  }
}

// Cập nhật thời gian hiện tại mặc định khi load trang
updateCurrentTime();

// Cập nhật hiển thị ngày trong dropdown khi trang load
function updateDateDropdownDisplay() {
  for (let i = 1; i <= 10; i++) {
    const dateItem = document.getElementById(`dateItem${i}`);
    if (dateItem) {
      dateItem.textContent = formatDateForDisplay(i);
    }
  }
}

// Gọi hàm cập nhật khi trang load
updateDateDropdownDisplay();

  // Toggle dropdown khi click nút "chọn ngày"
  if (selectDateBtn && dateDropdown) {
    selectDateBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = !dateDropdown.classList.contains('hidden');

      // Đóng tất cả dropdowns khác trước
      document.querySelectorAll('.dropdown-menu').forEach(menu => {
        if (menu !== dateDropdown) {
          menu.classList.add('hidden');
        }
      });

      // Toggle dropdown hiện tại
      if (isOpen) {
        dateDropdown.classList.add('hidden');
        dropdownContainer.classList.remove('open');
      } else {
        dateDropdown.classList.remove('hidden');
        dropdownContainer.classList.add('open');
      }
    });
  }


// Handle click trên dropdown items
if (dateDropdown) {
  dateDropdown.addEventListener('click', async (e) => {
    if (e.target.classList.contains('dropdown-item')) {
      const days = parseInt(e.target.dataset.days);

      // Kiểm tra xem ngày này có data không
      const hasData = await checkDateHasData(days);

      if (hasData) {
        // Nếu có data thì hiển thị file selector
        const { fromDate, toDate } = setDateRange(days);
        await showFileSelector(`${days}days`, fromDate, toDate);

        // Đóng dropdown sau khi chọn
        dateDropdown.classList.add('hidden');
        dropdownContainer.classList.remove('open');
      } else {
        // Nếu không có data thì hiển thị thông báo trong console và không làm gì
        console.log(`Không có dữ liệu cho ${days} ngày trước`);

        // Đóng dropdown
        dateDropdown.classList.add('hidden');
        dropdownContainer.classList.remove('open');
      }
    }
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

// Click outside để đóng file selector và dropdown
document.addEventListener('click', (e) => {
  // Đóng file selector
  if (!fileSelectorContainer.contains(e.target) &&
      !e.target.matches('.date-btn')) {
    fileSelectorContainer.classList.add('hidden');
  }

  // Đóng date dropdown
  if (dropdownContainer && !dropdownContainer.contains(e.target)) {
    dateDropdown.classList.add('hidden');
    dropdownContainer.classList.remove('open');
  }
});

// Thêm event listener để lưu frontend state khi có thay đổi
if (feedTextInput) {
  feedTextInput.addEventListener('input', () => saveFrontendState());
  feedTextInput.addEventListener('change', () => saveFrontendState());
}
if (feedRunMinutesInput) {
  feedRunMinutesInput.addEventListener('input', () => saveFrontendState());
  feedRunMinutesInput.addEventListener('change', () => saveFrontendState());
}
if (feedRestMinutesInput) {
  feedRestMinutesInput.addEventListener('input', () => saveFrontendState());
  feedRestMinutesInput.addEventListener('change', () => saveFrontendState());
}
// Lưu khi chọn feed mode
document.querySelectorAll('input[name="feedMode"]').forEach((radio) => {
  radio.addEventListener('change', () => saveFrontendState());
});

if (scanTextInput) {
  scanTextInput.addEventListener('input', () => saveFrontendState());
  scanTextInput.addEventListener('change', () => saveFrontendState());
}
if (scanRunMinutesInput) {
  scanRunMinutesInput.addEventListener('input', () => saveFrontendState());
  scanRunMinutesInput.addEventListener('change', () => saveFrontendState());
}
if (scanRestMinutesInput) {
  scanRestMinutesInput.addEventListener('input', () => saveFrontendState());
  scanRestMinutesInput.addEventListener('change', () => saveFrontendState());
}
// Lưu khi chọn scan mode
document.querySelectorAll('input[name="scanMode"]').forEach((radio) => {
  radio.addEventListener('change', () => saveFrontendState());
});

if (groupScanPostCountInput) {
  groupScanPostCountInput.addEventListener('input', () => saveFrontendState());
  groupScanPostCountInput.addEventListener('change', () => saveFrontendState());
}
if (groupScanStartDateInput) {
  groupScanStartDateInput.addEventListener('change', () => saveFrontendState());
}
if (groupScanEndDateInput) {
  groupScanEndDateInput.addEventListener('change', () => saveFrontendState());
}

// ==================== DELETE DATA MODAL ====================


// Biến lưu trạng thái expand của các ngày
let expandedDates = new Set();

// Render danh sách ngày có thể xóa (từ hôm nay đến 10 ngày trước)
async function renderDeleteDateList() {
  deleteDateList.innerHTML = '';

  const dates = [];
  // Sử dụng ngày hiện tại theo múi giờ local
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  // Tạo danh sách 11 ngày (hôm nay + 10 ngày trước)
  for (let i = 0; i <= 10; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);

    const dateStr = date.toLocaleDateString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });

    // Tính timestamp đầu ngày (00:00:00) và cuối ngày (23:59:59)
    const startOfDay = Math.floor(date.getTime() / 1000);
    const endOfDay = startOfDay + (24 * 60 * 60) - 1;

    dates.push({
      date: date,
      dateStr: dateStr,
      startTimestamp: startOfDay,
      endTimestamp: endOfDay
    });
  }

  for (const { date, dateStr, startTimestamp, endTimestamp } of dates) {
    // Chuyển dateStr từ DD/MM/YYYY thành YYYYMMDD để match với tên file
    const [day, month, year] = dateStr.split('/');
    const dateKey = `${year}${month}${day}`;

    // Lấy tất cả file trong khoảng 30 ngày trước đến hiện tại
    let files = [];
    try {
      const thirtyDaysAgo = Math.floor(Date.now() / 1000) - (30 * 24 * 60 * 60);
      const now = Math.floor(Date.now() / 1000) + (24 * 60 * 60); // Thêm 1 ngày để chắc chắn

      const res = await callBackend('/data/files-in-range', {
        method: 'POST',
        body: JSON.stringify({
          from_timestamp: thirtyDaysAgo,
          to_timestamp: now
        })
      });

      // Filter file theo ngày từ tên file
      const allFiles = res.files || [];
      files = allFiles.filter(file => {
        const filename = file.filename;
        // Pattern: all_results_YYYYMMDD_HHMMSS.json
        const match = filename.match(/all_results_(\d{8})_(\d{6})\.json$/);
        if (match) {
          const fileDate = match[1]; // YYYYMMDD
          return fileDate === dateKey;
        }
        return false;
      });

      console.log(`Ngày ${dateStr} (${dateKey}): tìm thấy ${files.length} file`);
    } catch (error) {
      console.warn(`Không thể load file cho ngày ${dateStr}:`, error);
      console.error('Error details:', error);
    }

    const isExpanded = expandedDates.has(dateStr);

    // Container cho cả ngày và files
    const dateContainer = document.createElement('div');
    dateContainer.className = 'delete-date-container';

    // Item ngày
    const dateItem = document.createElement('div');
    dateItem.className = 'delete-date-item';
    dateItem.innerHTML = `
      <span class="delete-date-expand-icon">${isExpanded ? '▼' : '▶'}</span>
      <span class="delete-date-text">${dateStr}</span>
      <span class="delete-date-count">(${files.length} file${files.length !== 1 ? 's' : ''})</span>
    `;

    // Click để expand/collapse
    dateItem.addEventListener('click', async (e) => {
      if (isExpanded) {
        expandedDates.delete(dateStr);
      } else {
        expandedDates.add(dateStr);
      }
      await renderDeleteDateList(); // Re-render để cập nhật trạng thái
    });

    dateContainer.appendChild(dateItem);

    // Nếu expanded, hiển thị danh sách file
    if (isExpanded && files.length > 0) {
      const filesContainer = document.createElement('div');
      filesContainer.className = 'delete-files-container';

      files.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'delete-file-item';
        fileItem.innerHTML = `
          <input type="checkbox" class="delete-file-checkbox" data-filename="${file.filename}">
          <span class="delete-file-text">${file.filename}</span>
          <span class="delete-file-time">${new Date(file.timestamp * 1000).toLocaleTimeString('vi-VN')}</span>
        `;

        fileItem.addEventListener('click', (e) => {
          if (e.target.type !== 'checkbox') {
            const checkbox = fileItem.querySelector('.delete-file-checkbox');
            checkbox.checked = !checkbox.checked;
          }
          updateDeleteButtonState();
        });

        filesContainer.appendChild(fileItem);
      });

      dateContainer.appendChild(filesContainer);
    }

    deleteDateList.appendChild(dateContainer);
  }
}

// Cập nhật trạng thái nút xóa
function updateDeleteButtonState() {
  const checkedBoxes = deleteDateList.querySelectorAll('.delete-file-checkbox:checked');
  deleteSelectedBtn.disabled = checkedBoxes.length === 0;
}

// Mở modal xóa dữ liệu
function openDeleteDataModal() {
  renderDeleteDateList();
  deleteDataModal.classList.remove('hidden');
  updateDeleteButtonState();
}

// Đóng modal xóa dữ liệu
function closeDeleteDataModal() {
  deleteDataModal.classList.add('hidden');
  // Reset checkboxes và expanded state
  const checkboxes = deleteDateList.querySelectorAll('.delete-file-checkbox');
  checkboxes.forEach(cb => cb.checked = false);
  expandedDates.clear();
  updateDeleteButtonState();
}

// Xóa các file đã chọn
async function deleteSelectedFiles() {
  const checkedBoxes = deleteDateList.querySelectorAll('.delete-file-checkbox:checked');
  if (checkedBoxes.length === 0) return;

  const selectedFiles = Array.from(checkedBoxes).map(cb => cb.dataset.filename);
  const confirmMessage = `Bạn có chắc muốn xóa ${selectedFiles.length} file đã chọn?\n\n${selectedFiles.join('\n')}\n\nHành động này không thể hoàn tác!`;

  if (!confirm(confirmMessage)) return;

  try {
    setButtonLoading(deleteSelectedBtn, true, 'Đang xóa...');

    const deleteRes = await callBackend('/data/files', {
      method: 'DELETE',
      body: JSON.stringify({ filenames: selectedFiles })
    });

    const deletedCount = deleteRes.total_deleted || 0;
    const failedCount = deleteRes.total_failed || 0;

    if (deletedCount > 0) {
      showToast(`Đã xóa thành công ${deletedCount} file`, 'success', 3000);
      closeDeleteDataModal();

      // Reload data if we're on scan view
      if (!scanView.classList.contains('hidden')) {
        await loadInitialData();
      }
    }

    if (failedCount > 0) {
      showToast(`Có ${failedCount} file xóa thất bại`, 'warning', 3000);
    }

  } catch (error) {
    console.error('Lỗi khi xóa file:', error);
    showToast('Lỗi khi xóa file. Vui lòng thử lại.', 'error');
  } finally {
    setButtonLoading(deleteSelectedBtn, false);
  }
}

// Event listeners cho delete modal
if (deleteDataBtn) {
  deleteDataBtn.addEventListener('click', openDeleteDataModal);
}

if (deleteDataModalClose) {
  deleteDataModalClose.addEventListener('click', closeDeleteDataModal);
}

if (deleteDataModalCancel) {
  deleteDataModalCancel.addEventListener('click', closeDeleteDataModal);
}

if (deleteSelectedBtn) {
  deleteSelectedBtn.addEventListener('click', deleteSelectedFiles);
}

// Đóng modal khi click outside
if (deleteDataModal) {
  deleteDataModal.addEventListener('click', (e) => {
    if (e.target === deleteDataModal) {
      closeDeleteDataModal();
    }
  });
}

// ==================== END DELETE DATA MODAL ====================

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
    await loadProfileState(); // Load profile list và render UI trước
  } catch (_) { }
  try {
    await loadFrontendState(); // Sau đó mới khôi phục frontend state (selected, mode, time, text)
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