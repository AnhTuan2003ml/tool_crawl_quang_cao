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

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
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
const feedConfigPanel = document.getElementById('feedConfigPanel');
const scanConfigPanel = document.getElementById('scanConfigPanel');
const groupScanPanel = document.getElementById('groupScanPanel');
const groupScanUrlInput = document.getElementById('groupScanUrlInput');
const groupScanPostCountInput = document.getElementById('groupScanPostCountInput');
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
  profiles: {}, // { [profileId]: { cookie: '', access_token: '', groups: string[] } }
  selected: {}, // { [profileId]: true/false } (frontend-only)
};
let addRowEl = null; // Row tạm để nhập profile mới
let joinGroupPollTimer = null;
let feedPollTimer = null;
let isScanning = false; // Trạng thái đang quét
let isPausedAll = false; // Trạng thái pause all (UI)

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
  isScanning = isOn;
  startBtn.disabled = isOn;
  const startBtnText = startBtn.querySelector('span:last-child');
  startBtnText.textContent = isOn ? 'Đang quét...' : 'Bắt đầu quét';
  stopBtn.disabled = !isOn;
  
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
  }
  // Thêm loading spinner cho nút bắt đầu quét
  if (startBtn) {
    if (isOn) {
      if (!startBtn.classList.contains('btn-loading')) {
        startBtn.classList.add('btn-loading');
      }
    } else {
      startBtn.classList.remove('btn-loading');
    }
  }
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
        if (key) nextProfiles[key] = { cookie: '', access_token: '' };
      });
    } else if (typeof profileIds === 'string') {
      profileIds.split(',').map((s) => s.trim()).filter(Boolean).forEach((pid) => {
        nextProfiles[pid] = { cookie: '', access_token: '' };
      });
    } else if (profileIds && typeof profileIds === 'object') {
      Object.entries(profileIds).forEach(([pid, cfg]) => {
        const key = String(pid || '').trim();
        if (!key) return;
        nextProfiles[key] = {
          cookie: (cfg && cfg.cookie) ? String(cfg.cookie) : '',
          access_token: (cfg && (cfg.access_token || cfg.accessToken)) ? String(cfg.access_token || cfg.accessToken) : '',
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
  ].filter(Boolean);

  needSelectedBtns.forEach((b) => {
    // nếu đang loading thì giữ nguyên trạng thái disabled
    if (b.classList && b.classList.contains('btn-loading')) return;
    b.disabled = !hasSelected;
  });

  // Các nút ALL (không phụ thuộc tick)
  const allBtns = [stopAllSettingBtn, pauseAllBtn].filter(Boolean);
  allBtns.forEach((b) => {
    if (b.classList && b.classList.contains('btn-loading')) return;
    b.disabled = false;
  });

  // Các nút "Chạy" trong các panel cũng yêu cầu tick profile
  const runBtns = [feedStartBtn, scanStartBtn, groupScanStartBtn].filter(Boolean);
  runBtns.forEach((b) => {
    if (b.classList && b.classList.contains('btn-loading')) return;
    b.disabled = !hasSelected;
  });

  // Nếu đang PAUSE ALL thì disable các nút "Chạy" để tránh bấm lại vô nghĩa
  if (isPausedAll) {
    [scanPostsSettingBtn, scanGroupSettingBtn, autoJoinGroupBtn, feedAccountSettingBtn, feedStartBtn, scanStartBtn, groupScanStartBtn]
      .filter(Boolean)
      .forEach((b) => {
        if (b.classList && b.classList.contains('btn-loading')) return;
        b.disabled = true;
      });
  }

  // Nếu không có selection thì auto đóng panel để tránh người dùng nhập rồi mới biết không chạy được
  if (!hasSelected) {
    if (feedConfigPanel) feedConfigPanel.style.display = 'none';
    if (scanConfigPanel) scanConfigPanel.style.display = 'none';
    if (groupScanPanel) groupScanPanel.style.display = 'none';
  }
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
    if (!btn.dataset.origText) {
      btn.dataset.origText = btn.textContent || '';
    }
    btn.disabled = true;
    btn.classList.add('btn-loading');
    if (loadingText) btn.textContent = loadingText;
  } else {
    btn.disabled = false;
    btn.classList.remove('btn-loading');
    if (btn.dataset.origText) {
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

function buildProfileRow(initialPid, initialInfo) {
  let currentPid = initialPid;
  const wrap = document.createElement('div');
  wrap.className = 'profile-row-wrap';

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

  // Pause/Resume profile button (theo spec)
  const pauseProfileBtn = document.createElement('button');
  pauseProfileBtn.type = 'button';
  pauseProfileBtn.className = 'btn-yellow';
  pauseProfileBtn.textContent = 'Tạm dừng';

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

  function getLocalGroups(pid) {
    const info = profileState.profiles[pid] || {};
    const gs = info.groups;
    if (Array.isArray(gs)) return gs.map((x) => String(x || '').trim()).filter(Boolean);
    return [];
  }

  async function updatePauseBtnLabel() {
    try {
      const st = await callBackendNoAlert('/control/state', { method: 'GET' });
      const paused = st && Array.isArray(st.paused_profiles) ? st.paused_profiles.includes(currentPid) : false;
      if (paused) {
        pauseProfileBtn.textContent = 'Resume';
        pauseProfileBtn.classList.remove('btn-yellow');
        pauseProfileBtn.classList.add('btn-success');
      } else {
        pauseProfileBtn.textContent = 'Pause';
        pauseProfileBtn.classList.remove('btn-success');
        pauseProfileBtn.classList.add('btn-yellow');
      }
    } catch (_) {
      // fallback label
      pauseProfileBtn.textContent = 'Pause';
    }
  }

  pauseProfileBtn.addEventListener('click', async () => {
    if (pauseProfileBtn.classList.contains('btn-loading')) return;
    try {
      const st = await callBackendNoAlert('/control/state', { method: 'GET' });
      const paused = st && Array.isArray(st.paused_profiles) ? st.paused_profiles.includes(currentPid) : false;
      if (!paused) {
        console.log(`[UI] PAUSE profile_id=${currentPid}`);
        setButtonLoading(pauseProfileBtn, true, 'Pausing...');
        await callBackend('/control/pause-profile', { method: 'POST', body: JSON.stringify({ profile_id: currentPid }) });
        showToast(`Đã pause ${currentPid}`, 'success');
      } else {
        console.log(`[UI] RESUME profile_id=${currentPid}`);
        setButtonLoading(pauseProfileBtn, true, 'Resuming...');
        await callBackend('/control/resume-profile', { method: 'POST', body: JSON.stringify({ profile_id: currentPid }) });
        showToast(`Đã resume ${currentPid}`, 'success');
      }
    } catch (e) {
      showToast('Không pause/resume profile được (kiểm tra FastAPI).', 'error');
    } finally {
      setButtonLoading(pauseProfileBtn, false);
      await updatePauseBtnLabel();
    }
  });

  function setLocalGroups(pid, groups) {
    if (!profileState.profiles[pid]) profileState.profiles[pid] = { cookie: '', access_token: '', groups: [] };
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
  tokenBtn.textContent = initialInfo?.access_token ? 'Cập nhật token' : 'Lấy access_token';

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

    const cur = profileState.profiles[currentPid] || { cookie: '', access_token: '', groups: [] };
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

  tokenBtn.addEventListener('click', () => {
    const info = profileState.profiles[currentPid] || {};
    const newVal = prompt(`Dán access token cho profile ${currentPid}:`, info.access_token || '');
    if (newVal === null) return;
    const nextToken = newVal.trim();
    tokenBtn.disabled = true;
    callBackend(`/settings/profiles/${encodeURIComponent(currentPid)}`, {
      method: 'PUT',
      body: JSON.stringify({ access_token: nextToken }),
    })
      .then(() => {
        profileState.profiles[currentPid] = { ...profileState.profiles[currentPid], access_token: nextToken };
        saveProfileState();
        tokenBtn.textContent = nextToken ? 'Cập nhật token' : 'Lấy access_token';
        showToast('Đã lưu token', 'success');
      })
      .catch(() => showToast('Không lưu token (kiểm tra FastAPI).', 'error'))
      .finally(() => (tokenBtn.disabled = false));
  });

  actions.appendChild(saveBtn);
  actions.appendChild(removeBtn);
  actions.appendChild(groupBtn);
  actions.appendChild(pauseProfileBtn);
  actions.appendChild(cookieBtn);
  actions.appendChild(tokenBtn);

  selectWrap.appendChild(selectCb);
  row.appendChild(selectWrap);
  row.appendChild(pidInput);
  row.appendChild(actions);
  wrap.appendChild(row);
  wrap.appendChild(groupPanel);
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
          profileState.profiles[value] = { cookie: '', access_token: '', groups: [] };
        }
        saveProfileState();
        // Thêm row mới mà không render lại toàn bộ (tránh nháy)
        if (profileList.classList.contains('empty-state-box')) {
          profileList.classList.remove('empty-state-box');
          profileList.innerHTML = '';
        }
        const newRow = buildProfileRow(value, profileState.profiles[value]);
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
    if (!isOpen && groupScanUrlInput) groupScanUrlInput.focus();
  });
}

if (groupScanCancelBtn && groupScanPanel) {
  groupScanCancelBtn.addEventListener('click', () => {
    groupScanPanel.style.display = 'none';
  });
}

// UI only: bấm "Chạy" thì chỉ validate + toast (chưa gọi API)
if (groupScanStartBtn) {
  groupScanStartBtn.addEventListener('click', () => {
    const selected = Object.keys(profileState.selected || {}).filter((pid) => profileState.selected[pid]);
    if (selected.length === 0) {
      showToast('Chọn (tick) ít nhất 1 profile trước.', 'error');
      return;
    }
    const raw = String(groupScanUrlInput?.value || '');
    const urls = raw
      .split(/\r?\n/)
      .map((s) => String(s || '').trim())
      .filter(Boolean);
    const postCount = parseInt(String(groupScanPostCountInput?.value || '0').trim(), 10);
    if (urls.length === 0) {
      showToast('Nhập ít nhất 1 URL group (mỗi dòng 1 URL).', 'error');
      return;
    }
    if (!Number.isFinite(postCount) || postCount < 0) {
      showToast('Số bài viết theo dõi không hợp lệ.', 'error');
      return;
    }
    showToast(`✅ Đã nhận ${urls.length} group URL + số bài theo dõi: ${postCount}`, 'success', 2200);
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

    // cho user thấy kết quả ngay ở tab danh sách quét
    try { switchTab('scan'); } catch (_) { }

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

async function handleStopAll() {
  console.log('[UI] STOP ALL triggered');
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
    setButtonLoading(stopBtn, false);

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

    // Nếu đang quét bằng các profile đó, UI không bị kẹt spinner
    setScanning(false);
  } catch (e) {
    showToast('Không dừng được profile đã chọn (kiểm tra FastAPI).', 'error');
  } finally {
    setButtonLoading(stopSelectedProfilesBtn, false);
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

  console.log(`[UI] PAUSE selected profiles=${selected.join(',')}`);
  setButtonLoading(pauseSelectedProfilesBtn, true, 'Đang pause...');
  try {
    await callBackend('/control/pause-profiles', {
      method: 'POST',
      body: JSON.stringify({ profile_ids: selected }),
    });
    showToast(`Đã pause ${selected.length} profile`, 'success', 2200);
  } catch (e) {
    showToast('Không pause được profile đã tick (kiểm tra FastAPI).', 'error');
  } finally {
    setButtonLoading(pauseSelectedProfilesBtn, false);
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
    if (pauseAllBtn) {
      // update label
      const icon = pauseAllBtn.querySelector('span.btn-icon');
      const text = pauseAllBtn.querySelector('span:last-child');
      if (isPausedAll) {
        if (icon) icon.textContent = '▶️';
        if (text) text.textContent = 'Tiếp tục tất cả';
      } else {
        if (icon) icon.textContent = '⏸️';
        if (text) text.textContent = 'Tạm dừng tất cả';
      }
    }
  } catch (_) { }
}

async function handlePauseAllToggle() {
  if (!pauseAllBtn) return;
  if (pauseAllBtn.classList.contains('btn-loading')) return;
  try {
    if (!isPausedAll) {
      console.log('[UI] PAUSE ALL triggered');
      setButtonLoading(pauseAllBtn, true, 'Đang tạm dừng...');
      await callBackend('/control/pause-all', { method: 'POST' });
      showToast('Đã tạm dừng tất cả', 'success');
    } else {
      console.log('[UI] RESUME ALL triggered');
      setButtonLoading(pauseAllBtn, true, 'Đang tiếp tục...');
      await callBackend('/control/resume-all', { method: 'POST' });
      showToast('Đã tiếp tục tất cả', 'success');
    }
  } catch (e) {
    showToast('Không pause/resume được (kiểm tra FastAPI).', 'error');
  } finally {
    setButtonLoading(pauseAllBtn, false);
    await refreshControlState();
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
  } catch (err) {
    console.error('Lỗi trong startScanFlow:', err);
    setScanning(false);
    throw err;
  }
}

startBtn.addEventListener(
  'click',
  async () => {
    // Nếu đang quét thì không cho bấm lại
    if (isScanning) {
      showToast('Đang quét, vui lòng đợi hoặc bấm dừng trước', 'warning');
      return;
    }
    
    // Nếu nút đang loading thì không cho bấm lại
    if (startBtn.classList.contains('btn-loading')) {
      return;
    }
    
    try {
      await startScanFlow();
    } catch (err) {
      console.warn('Không startScanFlow được:', err);
      showToast('Không thể khởi động quét', 'error');
      setScanning(false);
    }
  }
);

stopBtn.addEventListener('click', async () => {
  // Nếu đang dừng rồi thì không làm gì
  if (stopBtn.classList.contains('btn-loading')) {
    return;
  }
  
  // Thêm loading state cho nút dừng
  setButtonLoading(stopBtn, true, 'Đang dừng...');
  
  try {
    // Dừng tất cả intervals và timers
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    // Dừng kiểm tra dữ liệu mới
    if (dataCheckInterval) {
      clearInterval(dataCheckInterval);
      dataCheckInterval = null;
    }

    // Reset UI NGAY LẬP TỨC để user bấm lại được (không chờ backend)
    setScanning(false);
    setButtonLoading(scanStartBtn, false);
    setButtonLoading(scanPostsSettingBtn, false);

    // Gửi lệnh dừng backend (có thể chậm/timeout, nhưng UI không bị kẹt)
    await sendStopSignal();
    
    showToast('Đã dừng quét', 'success');
  } catch (err) {
    console.warn('Lỗi khi dừng:', err);
    showToast('Có lỗi khi dừng quét', 'error');
  } finally {
    // Bỏ loading state của nút dừng
    setButtonLoading(stopBtn, false);
  }
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
    setBackendStatus(`Đã kích hoạt backend${pidText}`, true);
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
  
  // Bỏ active state của các button recent days
  if (todayBtn) todayBtn.classList.remove('active');
  if (recent1DayBtn) recent1DayBtn.classList.remove('active');
  if (recent2DaysBtn) recent2DaysBtn.classList.remove('active');
  
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
  // Bỏ active state của recent days khi thay đổi input thủ công
  timeFilterFrom.addEventListener('change', () => {
    if (todayBtn) todayBtn.classList.remove('active');
    if (recent1DayBtn) recent1DayBtn.classList.remove('active');
    if (recent2DaysBtn) recent2DaysBtn.classList.remove('active');
  });
}

if (timeFilterTo) {
  timeFilterTo.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      applyTimeFilter();
    }
  });
  // Bỏ active state của recent days khi thay đổi input thủ công
  timeFilterTo.addEventListener('change', () => {
    if (todayBtn) todayBtn.classList.remove('active');
    if (recent1DayBtn) recent1DayBtn.classList.remove('active');
    if (recent2DaysBtn) recent2DaysBtn.classList.remove('active');
  });
}

// Chọn ngày (hiện tại, 1 ngày trước, 2 ngày trước)
const todayBtn = document.getElementById('todayBtn');
const recent1DayBtn = document.getElementById('recent1DayBtn');
const recent2DaysBtn = document.getElementById('recent2DaysBtn');

function applyRecentDaysFilter(type) {
  const now = new Date();
  let startDate, endDate;
  
  if (type === 'today') {
    // Hiện tại: từ 0h hôm nay đến 23h59 hôm nay
    startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
    endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
  } else if (type === '1day') {
    // 1 ngày trước: từ 0h hôm qua đến 23h59 hôm qua
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    startDate = new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 0, 0, 0, 0);
    endDate = new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 23, 59, 59, 999);
  } else if (type === '2days') {
    // 2 ngày trước: từ 0h ngày hôm kia đến 23h59 ngày hôm kia
    const dayBefore = new Date(now);
    dayBefore.setDate(dayBefore.getDate() - 2);
    startDate = new Date(dayBefore.getFullYear(), dayBefore.getMonth(), dayBefore.getDate(), 0, 0, 0, 0);
    endDate = new Date(dayBefore.getFullYear(), dayBefore.getMonth(), dayBefore.getDate(), 23, 59, 59, 999);
  }
  
  // Format thành datetime-local format (YYYY-MM-DDTHH:mm)
  const formatDateTime = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };
  
  // Set giá trị vào input
  if (timeFilterFrom && startDate) {
    timeFilterFrom.value = formatDateTime(startDate);
  }
  if (timeFilterTo && endDate) {
    timeFilterTo.value = formatDateTime(endDate);
  }
  
  // Áp dụng filter
  applyTimeFilter();
  
  // Cập nhật trạng thái active của các button
  if (todayBtn) todayBtn.classList.remove('active');
  if (recent1DayBtn) recent1DayBtn.classList.remove('active');
  if (recent2DaysBtn) recent2DaysBtn.classList.remove('active');
  
  if (type === 'today' && todayBtn) {
    todayBtn.classList.add('active');
  } else if (type === '1day' && recent1DayBtn) {
    recent1DayBtn.classList.add('active');
  } else if (type === '2days' && recent2DaysBtn) {
    recent2DaysBtn.classList.add('active');
  }
}

if (todayBtn) {
  todayBtn.addEventListener('click', () => {
    applyRecentDaysFilter('today');
  });
}

if (recent1DayBtn) {
  recent1DayBtn.addEventListener('click', () => {
    applyRecentDaysFilter('1day');
  });
}

if (recent2DaysBtn) {
  recent2DaysBtn.addEventListener('click', () => {
    applyRecentDaysFilter('2days');
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

if (tabScanList) tabScanList.addEventListener('click', () => switchTab('scan'));
if (tabPostManager) tabPostManager.addEventListener('click', () => switchTab('post'));
if (tabSettings) tabSettings.addEventListener('click', () => switchTab('settings'));

// Khởi tạo: luôn vào tab danh sách quét + load state profile
let initialTab = 'scan';
try {
  const saved = localStorage.getItem(ACTIVE_TAB_KEY);
  if (saved && tabConfig[saved]) initialTab = saved;
} catch (e) {
  // ignore
}
switchTab(initialTab);
loadProfileState();
// Khởi tạo filter với trạng thái mặc định
initializeFilters();
