"""
Multi-thread runner để chạy song song quét feed+search và quét group

Cải tiến:
- Error handling chi tiết
- Logging structured
- Configuration linh hoạt
- Performance monitoring
- Health checks
- Graceful shutdown
"""

import threading
import time
import logging
import json
import sys
from typing import List, Optional, Dict, Any, Callable
from multiprocessing import Process
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import traceback

# ====== FIX IMPORT PATH KHI CHẠY TRỰC TIẾP ======
# Nếu chạy trực tiếp từ thư mục worker, thêm parent directory vào sys.path
if __name__ == "__main__" or not any("backend" in str(p) for p in sys.path):
    current_file = Path(__file__).resolve()
    # Tìm backend directory (parent của worker)
    backend_dir = current_file.parent.parent
    if backend_dir.exists() and backend_dir.name == "backend":
        backend_path = str(backend_dir)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import các dependencies cần thiết
try:
    from ..app.api import (
        _run_bot_profile_loop,
        _process_group_scan_queue,
        _group_scan_queue,
        _group_scan_lock,
        _group_scan_processing,
        _group_scan_stop_requested,
        _bot_lock,
        _bot_processes,
        _prune_bot_processes,
        control_state
    )
    from ..core.paths import get_data_dir, get_config_dir
    from ..core.settings import get_settings
    from .get_post_from_page import get_posts_from_page
except ImportError:
    # Fallback imports nếu chạy độc lập
    try:
        from app.api import (
            _run_bot_profile_loop,
            _process_group_scan_queue,
            _group_scan_queue,
            _group_scan_lock,
            _group_scan_processing,
            _group_scan_stop_requested,
            _bot_lock,
            _bot_processes,
            _prune_bot_processes,
            control_state
        )
        from core.paths import get_data_dir, get_config_dir
        from core.settings import get_settings
        from worker.get_post_from_page import get_posts_from_page
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error(f"Current sys.path: {sys.path}")
        logger.error("=" * 60)
        logger.error("LƯU Ý: File này cần được chạy trong môi trường có đầy đủ dependencies:")
        logger.error("  - fastapi")
        logger.error("  - playwright")
        logger.error("  - và các dependencies khác trong requirements.txt")
        logger.error("=" * 60)
        logger.error("Để test, hãy:")
        logger.error("  1. Kích hoạt virtual environment: venv\\Scripts\\activate")
        logger.error("  2. Hoặc chạy từ FastAPI server (không chạy trực tiếp file này)")
        logger.error("=" * 60)
        raise


@dataclass
class RunnerConfig:
    """Configuration cho MultiThreadRunner"""
    # Feed search config
    run_minutes: float = 30.0
    rest_minutes: float = 120.0
    text: str = ""
    mode: str = "feed"

    # Group scan config
    post_count: int = 10
    start_date: str = ""
    end_date: str = ""

    # Runner config
    max_retries: int = 3
    retry_delay: float = 5.0
    health_check_interval: float = 10.0
    thread_join_timeout: float = 30.0
    process_join_timeout: float = 60.0

    def validate(self) -> List[str]:
        """Validate configuration và trả về danh sách errors"""
        errors = []

        # Validate feed search
        if self.run_minutes <= 0:
            errors.append("run_minutes phải > 0")
        if self.rest_minutes < 0:
            errors.append("rest_minutes phải >= 0")
        if self.mode not in ("feed", "search", "feed+search", "feed_search"):
            errors.append("mode phải là 'feed', 'search', hoặc 'feed+search'")
        if self.mode in ("search", "feed+search", "feed_search") and not self.text.strip():
            errors.append("Search mode cần text")

        # Validate group scan
        if self.post_count <= 0:
            errors.append("post_count phải > 0")
        if self.start_date and self.end_date:
            try:
                from datetime import datetime
                datetime.strptime(self.start_date, "%Y-%m-%d")
                datetime.strptime(self.end_date, "%Y-%m-%d")
            except ValueError:
                errors.append("start_date và end_date phải có format YYYY-MM-DD")

        # Validate runner config
        if self.max_retries < 0:
            errors.append("max_retries phải >= 0")
        if self.retry_delay <= 0:
            errors.append("retry_delay phải > 0")

        return errors


@dataclass
class RunnerStats:
    """Thống kê cho MultiThreadRunner"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    feed_search_started: int = 0
    feed_search_completed: int = 0
    feed_search_errors: int = 0
    group_scan_started: int = 0
    group_scan_completed: int = 0
    group_scan_errors: int = 0
    last_health_check: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict với thời gian format"""
        data = asdict(self)
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        if self.last_health_check:
            data['last_health_check'] = self.last_health_check.isoformat()
        if self.start_time and self.end_time:
            data['duration_seconds'] = (self.end_time - self.start_time).total_seconds()
        return data


class MultiThreadRunner:
    """Runner để chạy song song quét feed+search và quét group"""

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
        self.feed_search_thread: Optional[threading.Thread] = None
        self.group_scan_thread: Optional[threading.Thread] = None
        self.health_check_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.stats = RunnerStats()
        self._lock = threading.RLock()
        self._health_check_stop_event = threading.Event()

        # Callbacks
        self.on_feed_search_error: Optional[Callable[[str, Exception], None]] = None
        self.on_group_scan_error: Optional[Callable[[str, Exception], None]] = None
        self.on_health_issue: Optional[Callable[[str], None]] = None

    def _safe_execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function với error handling"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def _validate_config(self) -> bool:
        """Validate configuration"""
        errors = self.config.validate()
        if errors:
            logger.error(f"Configuration validation failed: {errors}")
            return False
        return True

    def _start_health_check(self):
        """Khởi động health check thread"""
        if self.health_check_thread and self.health_check_thread.is_alive():
            return

        def health_check_worker():
            logger.info("🏥 Health check thread started")
            while not self._health_check_stop_event.is_set():
                try:
                    self._perform_health_check()
                    self.stats.last_health_check = datetime.now()
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                    if self.on_health_issue:
                        self.on_health_issue(f"Health check failed: {e}")

                self._health_check_stop_event.wait(self.config.health_check_interval)

            logger.info("🏥 Health check thread stopped")

        self.health_check_thread = threading.Thread(target=health_check_worker, daemon=True, name="HealthCheck")
        self.health_check_thread.start()

    def _perform_health_check(self):
        """Perform health check"""
        issues = []

        # Check feed search thread - chỉ warning nếu thread died bất thường (chưa completed)
        # Nếu thread đã được clear (None) thì không check (đã completed bình thường)
        if self.feed_search_thread is not None and not self.feed_search_thread.is_alive():
            # Chỉ warning nếu thread chưa completed (died bất thường)
            # Nếu đã completed thì không coi là issue (thread đã hoàn thành bình thường)
            if self.stats.feed_search_completed < self.stats.feed_search_started:
                issues.append("Feed search thread died unexpectedly")
            # Nếu completed >= started thì thread đã hoàn thành bình thường, không warning
            # Nếu thread đã completed, clear reference để không check nữa
            elif self.stats.feed_search_completed >= self.stats.feed_search_started:
                self.feed_search_thread = None

        # Check group scan thread - chỉ warning nếu thread died bất thường (chưa completed)
        # Nếu thread đã được clear (None) thì không check (đã completed bình thường)
        if self.group_scan_thread is not None and not self.group_scan_thread.is_alive():
            # Chỉ warning nếu thread chưa completed (died bất thường)
            # Nếu đã completed thì không coi là issue (thread đã hoàn thành bình thường)
            if self.stats.group_scan_completed < self.stats.group_scan_started:
                issues.append("Group scan thread died unexpectedly")
            # Nếu completed >= started thì thread đã hoàn thành bình thường, không warning
            # Nếu thread đã completed, clear reference để không check nữa
            elif self.stats.group_scan_completed >= self.stats.group_scan_started:
                self.group_scan_thread = None

        # Check bot processes
        try:
            with _bot_lock:
                _prune_bot_processes()
                dead_processes = [pid for pid, proc in _bot_processes.items() if proc and not proc.is_alive()]
                if dead_processes:
                    issues.append(f"Dead bot processes: {dead_processes}")
        except Exception as e:
            issues.append(f"Cannot check bot processes: {e}")

        # Check group scan queue
        try:
            with _group_scan_lock:
                if _group_scan_processing and len(_group_scan_queue) == 0:
                    # Processing but no tasks - might be stuck
                    issues.append("Group scan might be stuck (processing but no tasks)")
        except Exception as e:
            issues.append(f"Cannot check group scan: {e}")

        if issues:
            logger.warning(f"🚨 Health issues detected: {issues}")
            if self.on_health_issue:
                for issue in issues:
                    self.on_health_issue(issue)

    def start_feed_search(
        self,
        profile_ids: List[str],
        run_minutes: Optional[float] = None,
        rest_minutes: Optional[float] = None,
        text: Optional[str] = None,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Khởi động quét feed+search trong thread riêng

        Args:
            profile_ids: Danh sách profile IDs
            run_minutes: Thời gian chạy (phút) - nếu None dùng config
            rest_minutes: Thời gian nghỉ (phút) - nếu None dùng config
            text: Text để search - nếu None dùng config
            mode: "feed", "search", hoặc "feed+search" - nếu None dùng config

        Returns:
            Dict với status và thông tin
        """
        with self._lock:
            if self.feed_search_thread and self.feed_search_thread.is_alive():
                return {"status": "error", "message": "Feed search đang chạy"}

            # Update config with provided params
            config = RunnerConfig(
                run_minutes=run_minutes or self.config.run_minutes,
                rest_minutes=rest_minutes or self.config.rest_minutes,
                text=text or self.config.text,
                mode=mode or self.config.mode
            )

            # Validate
            errors = config.validate()
            if errors:
                return {"status": "error", "message": f"Validation failed: {errors}"}

            if not profile_ids:
                return {"status": "error", "message": "Không có profile nào được chọn"}

            def feed_search_worker():
                logger.info(f"🚀 Bắt đầu quét feed+search cho {len(profile_ids)} profile(s)...")
                logger.info(f"   Config: mode={config.mode}, run={config.run_minutes}m, rest={config.rest_minutes}m, text='{config.text}'")

                self.stats.feed_search_started = len(profile_ids)
                started: List[str] = []
                skipped: List[Dict[str, str]] = []
                retry_count = 0

                while retry_count <= self.config.max_retries and not self.stop_event.is_set():
                    try:
                        # Reset stats cho retry
                        if retry_count > 0:
                            logger.info(f"🔄 Retry {retry_count}/{self.config.max_retries} feed search...")

                        with _bot_lock:
                            _prune_bot_processes()
                            for pid in profile_ids:
                                if self.stop_event.is_set():
                                    break

                                existing = _bot_processes.get(pid)
                                if existing and existing.is_alive():
                                    skipped.append({"profile_id": pid, "reason": "already_running"})
                                    continue

                                proc = Process(
                                    target=_run_bot_profile_loop,
                                    args=(pid, config.run_minutes, config.rest_minutes, config.text, config.mode, profile_ids),
                                    daemon=True,
                                )
                                proc.start()
                                _bot_processes[pid] = proc
                                started.append(pid)

                        logger.info(f"✅ Đã khởi động feed+search cho {len(started)} profile(s)")
                        if skipped:
                            logger.warning(f"⚠️ Bỏ qua {len(skipped)} profile(s) đang chạy")

                        # Monitor processes
                        consecutive_errors = 0
                        while not self.stop_event.is_set() and consecutive_errors < 5:
                            with _bot_lock:
                                _prune_bot_processes()
                                running = [pid for pid, proc in _bot_processes.items() if proc and proc.is_alive()]

                            if not running:
                                logger.info("✅ Tất cả feed+search process đã hoàn thành")
                                self.stats.feed_search_completed = len(started)
                                # Clear thread reference để health check không warning
                                self.feed_search_thread = None
                                return

                            # Check for process errors
                            if len(running) < len(started) - self.stats.feed_search_errors:
                                consecutive_errors += 1
                                logger.warning(f"⚠️ Có process bị die, consecutive_errors={consecutive_errors}")
                            else:
                                consecutive_errors = 0

                            time.sleep(2)

                        if consecutive_errors >= 5:
                            raise RuntimeError("Quá nhiều process bị die")

                    except Exception as e:
                        self.stats.feed_search_errors += 1
                        logger.error(f"❌ Lỗi trong feed search worker (attempt {retry_count + 1}): {e}")
                        logger.debug(f"Traceback: {traceback.format_exc()}")

                        if self.on_feed_search_error:
                            self.on_feed_search_error(f"Feed search error (attempt {retry_count + 1})", e)

                        retry_count += 1
                        if retry_count <= self.config.max_retries:
                            logger.info(f"⏳ Đợi {self.config.retry_delay}s trước khi retry...")
                            time.sleep(self.config.retry_delay)
                        else:
                            logger.error("❌ Hết số lần retry, dừng feed search")
                            break

                logger.info("🏁 Feed search worker kết thúc")

            self.feed_search_thread = threading.Thread(target=feed_search_worker, daemon=True, name="FeedSearch")
            self.feed_search_thread.start()

            return {
                "status": "ok",
                "message": f"Đã khởi động quét feed+search cho {len(profile_ids)} profile(s)",
                "profiles": profile_ids,
                "config": asdict(config)
            }

    def start_group_scan(
        self,
        profile_ids: List[str],
        post_count: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Khởi động quét group trong thread riêng

        Args:
            profile_ids: Danh sách profile IDs
            post_count: Số bài viết tối đa cần quét từ mỗi group - nếu None dùng config
            start_date: Ngày bắt đầu (YYYY-MM-DD) - nếu None dùng config
            end_date: Ngày kết thúc (YYYY-MM-DD) - nếu None dùng config

        Returns:
            Dict với status và thông tin
        """
        with self._lock:
            if self.group_scan_thread and self.group_scan_thread.is_alive():
                return {"status": "error", "message": "Group scan đang chạy"}

            # Update config with provided params
            config = RunnerConfig(
                post_count=post_count or self.config.post_count,
                start_date=start_date or self.config.start_date,
                end_date=end_date or self.config.end_date
            )

            # Validate
            errors = config.validate()
            if errors:
                return {"status": "error", "message": f"Validation failed: {errors}"}

            if not profile_ids:
                return {"status": "error", "message": "Không có profile nào được chọn"}

            if not config.start_date or not config.end_date:
                return {"status": "error", "message": "Thiếu thông tin ngày tháng"}

            def group_scan_worker():
                logger.info(f"🚀 Bắt đầu quét group cho {len(profile_ids)} profile(s)...")
                logger.info(f"   Config: post_count={config.post_count}, start_date={config.start_date}, end_date={config.end_date}")

                self.stats.group_scan_started = len(profile_ids)
                retry_count = 0

                while retry_count <= self.config.max_retries and not self.stop_event.is_set():
                    try:
                        # Reset stats cho retry
                        if retry_count > 0:
                            logger.info(f"🔄 Retry {retry_count}/{self.config.max_retries} group scan...")

                        # Thêm tasks vào queue
                        with _group_scan_lock:
                            # Reset stop flag khi bắt đầu quét mới
                            _group_scan_stop_requested = False
                            for profile_id in profile_ids:
                                if self.stop_event.is_set():
                                    break

                                task = {
                                    "profile_id": profile_id,
                                    "post_count": config.post_count,
                                    "start_date": config.start_date,
                                    "end_date": config.end_date
                                }
                                _group_scan_queue.append(task)

                        logger.info(f"✅ Đã thêm {len(profile_ids)} profile vào hàng chờ quét group")

                        # Bắt đầu xử lý queue
                        threading.Thread(target=_process_group_scan_queue, daemon=True, name="GroupScanProcessor").start()

                        # Monitor queue processing
                        consecutive_empty = 0
                        while not self.stop_event.is_set():
                            with _group_scan_lock:
                                queue_empty = len(_group_scan_queue) == 0
                                not_processing = not _group_scan_processing

                            if queue_empty and not_processing:
                                consecutive_empty += 1
                                if consecutive_empty >= 3:  # Confirm completion
                                    logger.info("✅ Tất cả group scan tasks đã hoàn thành")
                                    self.stats.group_scan_completed = len(profile_ids)
                                    # Clear thread reference để health check không warning
                                    self.group_scan_thread = None
                                    return
                            else:
                                consecutive_empty = 0

                            time.sleep(2)

                    except Exception as e:
                        self.stats.group_scan_errors += 1
                        logger.error(f"❌ Lỗi trong group scan worker (attempt {retry_count + 1}): {e}")
                        logger.debug(f"Traceback: {traceback.format_exc()}")

                        if self.on_group_scan_error:
                            self.on_group_scan_error(f"Group scan error (attempt {retry_count + 1})", e)

                        retry_count += 1
                        if retry_count <= self.config.max_retries:
                            logger.info(f"⏳ Đợi {self.config.retry_delay}s trước khi retry...")
                            time.sleep(self.config.retry_delay)
                        else:
                            logger.error("❌ Hết số lần retry, dừng group scan")
                            break

                logger.info("🏁 Group scan worker kết thúc")

            self.group_scan_thread = threading.Thread(target=group_scan_worker, daemon=True, name="GroupScan")
            self.group_scan_thread.start()

            return {
                "status": "ok",
                "message": f"Đã khởi động quét group cho {len(profile_ids)} profile(s)",
                "profiles": profile_ids,
                "config": asdict(config)
            }

    def start_all(
        self,
        profile_ids: List[str],
        # Feed search params
        run_minutes: Optional[float] = None,
        rest_minutes: Optional[float] = None,
        text: Optional[str] = None,
        mode: Optional[str] = None,
        # Group scan params
        post_count: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Khởi động cả feed+search và group scan song song

        Returns:
            Dict với status của cả 2 tasks
        """
        with self._lock:
            if self.is_running:
                return {"status": "error", "message": "Multi-thread runner đang chạy"}

            # Validate overall config
            if not self._validate_config():
                return {"status": "error", "message": "Configuration không hợp lệ"}

            if not profile_ids:
                return {"status": "error", "message": "Không có profile nào được chọn"}

            self.is_running = True
            self.stop_event.clear()
            self.stats = RunnerStats(start_time=datetime.now())

            # Start health check
            self._start_health_check()

            results = {}
            errors = []

            # Start feed search
            try:
                feed_result = self.start_feed_search(
                    profile_ids=profile_ids,
                    run_minutes=run_minutes,
                    rest_minutes=rest_minutes,
                    text=text,
                    mode=mode
                )
                results["feed_search"] = feed_result
                if feed_result.get("status") != "ok":
                    errors.append(f"Feed search: {feed_result.get('message', 'Unknown error')}")
            except Exception as e:
                logger.error(f"Failed to start feed search: {e}")
                results["feed_search"] = {"status": "error", "message": str(e)}
                errors.append(f"Feed search exception: {e}")

            # Start group scan (chỉ nếu có đủ thông tin)
            group_start_date = start_date or self.config.start_date
            group_end_date = end_date or self.config.end_date

            if group_start_date and group_end_date:
                try:
                    group_result = self.start_group_scan(
                        profile_ids=profile_ids,
                        post_count=post_count,
                        start_date=group_start_date,
                        end_date=group_end_date
                    )
                    results["group_scan"] = group_result
                    if group_result.get("status") != "ok":
                        errors.append(f"Group scan: {group_result.get('message', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Failed to start group scan: {e}")
                    results["group_scan"] = {"status": "error", "message": str(e)}
                    errors.append(f"Group scan exception: {e}")
            else:
                results["group_scan"] = {"status": "skipped", "message": "Thiếu thông tin ngày tháng cho group scan"}
                logger.info("⚠️ Group scan bị skip do thiếu thông tin ngày tháng")

            # Overall status
            overall_status = "ok" if not errors else "partial" if results else "error"

            response = {
                "status": overall_status,
                "message": f"Đã khởi động multi-thread runner ({overall_status})",
                "results": results,
                "profiles_count": len(profile_ids),
                "profiles": profile_ids
            }

            if errors:
                response["errors"] = errors
                logger.warning(f"🚨 Multi-thread runner started with errors: {errors}")

            logger.info(f"🎯 Multi-thread runner started: {overall_status} - Feed: {results.get('feed_search', {}).get('status')} - Group: {results.get('group_scan', {}).get('status')}")

            return response

    def stop_all(self) -> Dict[str, Any]:
        """
        Dừng tất cả các thread và process đang chạy với graceful shutdown

        Returns:
            Dict với status
        """
        logger.info("🛑 Dừng multi-thread runner...")
        start_time = time.time()

        with self._lock:
            if not self.is_running:
                return {"status": "ok", "message": "Multi-thread runner đã dừng"}

            # Set stop events
            self.stop_event.set()
            self._health_check_stop_event.set()

            # Stop health check thread first
            if self.health_check_thread and self.health_check_thread.is_alive():
                logger.info("🛑 Dừng health check thread...")
                self.health_check_thread.join(timeout=self.config.thread_join_timeout)
                if self.health_check_thread.is_alive():
                    logger.warning("⚠️ Health check thread không dừng được trong timeout")

            # Stop feed search processes gracefully
            try:
                logger.info("🛑 Dừng feed search processes...")
                with _bot_lock:
                    _prune_bot_processes()
                    alive_processes = [(pid, proc) for pid, proc in _bot_processes.items() if proc and proc.is_alive()]

                    if alive_processes:
                        logger.info(f"🛑 Terminate {len(alive_processes)} bot process(es)...")

                        # First try graceful termination
                        for pid, proc in alive_processes:
                            try:
                                proc.terminate()
                                logger.debug(f"✅ Sent terminate signal to process {pid}")
                            except Exception as e:
                                logger.warning(f"⚠️ Không thể terminate process {pid}: {e}")

                        # Wait for processes to terminate
                        terminated = []
                        start_wait = time.time()
                        while time.time() - start_wait < self.config.process_join_timeout:
                            with _bot_lock:
                                _prune_bot_processes()
                                still_alive = [pid for pid, proc in _bot_processes.items() if proc and proc.is_alive()]

                            if not still_alive:
                                break

                            time.sleep(0.5)

                        # Force kill if still alive
                        with _bot_lock:
                            _prune_bot_processes()
                            force_killed = []
                            for pid, proc in list(_bot_processes.items()):
                                if proc and proc.is_alive():
                                    try:
                                        proc.kill()
                                        force_killed.append(pid)
                                        logger.warning(f"💀 Force killed process {pid}")
                                    except Exception as e:
                                        logger.error(f"❌ Không thể force kill process {pid}: {e}")

                            if force_killed:
                                logger.warning(f"💀 Force killed {len(force_killed)} process(es): {force_killed}")

                    _bot_processes.clear()

            except Exception as e:
                logger.error(f"⚠️ Lỗi khi dừng feed search: {e}")

            # Stop group scan queue trước
            try:
                logger.info("🛑 Dừng group scan queue...")
                with _group_scan_lock:
                    _group_scan_stop_requested = True
                    queue_length = len(_group_scan_queue)
                    _group_scan_queue.clear()
                logger.info(f"✅ Đã dừng group scan queue (cleared {queue_length} task(s))")
            except Exception as e:
                logger.error(f"⚠️ Lỗi khi dừng group scan queue: {e}")

            # Stop worker threads
            threads_to_stop = [
                ("Feed search", self.feed_search_thread),
                ("Group scan", self.group_scan_thread)
            ]

            for thread_name, thread in threads_to_stop:
                if thread and thread.is_alive():
                    logger.info(f"🛑 Đợi {thread_name} thread dừng...")
                    thread.join(timeout=self.config.thread_join_timeout)
                    if thread.is_alive():
                        logger.warning(f"⚠️ {thread_name} thread không dừng được trong timeout")
                    else:
                        logger.info(f"✅ {thread_name} thread đã dừng")

            # Final cleanup
            self.feed_search_thread = None
            self.group_scan_thread = None
            self.health_check_thread = None
            self.is_running = False
            self.stats.end_time = datetime.now()

            duration = time.time() - start_time
            
            return {
                "status": "ok",
                "message": f"Dừng multi-thread runner trong {duration:.2f}s",
                "duration_seconds": round(duration, 2),
                "stats": self.stats.to_dict()
            }

    def status(self) -> Dict[str, Any]:
        """
        Kiểm tra status chi tiết của multi-thread runner

        Returns:
            Dict với thông tin status đầy đủ
        """
        with self._lock:
            feed_search_alive = self.feed_search_thread and self.feed_search_thread.is_alive()
            group_scan_alive = self.group_scan_thread and self.group_scan_thread.is_alive()
            health_check_alive = self.health_check_thread and self.health_check_thread.is_alive()

            # Bot processes status
            try:
                with _bot_lock:
                    _prune_bot_processes()
                    running_profiles = [pid for pid, proc in _bot_processes.items() if proc and proc.is_alive()]
                    total_processes = len(_bot_processes)
            except Exception as e:
                logger.error(f"Cannot get bot processes status: {e}")
                running_profiles = []
                total_processes = 0

            # Group scan status
            try:
                with _group_scan_lock:
                    queue_length = len(_group_scan_queue)
                    processing = _group_scan_processing
            except Exception as e:
                logger.error(f"Cannot get group scan status: {e}")
                queue_length = 0
                processing = False

            # Calculate health score (0-100)
            health_score = 100
            health_issues = []

            if not self.is_running:
                health_score -= 50
                health_issues.append("Runner not running")

            if self.is_running and not health_check_alive:
                health_score -= 20
                health_issues.append("Health check not running")

            if feed_search_alive and len(running_profiles) == 0:
                health_score -= 15
                health_issues.append("Feed search running but no bot processes")

            if group_scan_alive and not processing and queue_length == 0:
                health_score -= 10
                health_issues.append("Group scan running but idle")

            # Memory usage estimation (rough)
            memory_mb = 0
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
            except ImportError:
                pass  # psutil not available
            except Exception:
                pass  # Cannot get memory info

            status_data = {
                "is_running": self.is_running,
                "health_score": max(0, health_score),
                "health_issues": health_issues,
                "threads": {
                    "feed_search": {
                        "alive": feed_search_alive,
                        "name": self.feed_search_thread.name if self.feed_search_thread else None
                    },
                    "group_scan": {
                        "alive": group_scan_alive,
                        "name": self.group_scan_thread.name if self.group_scan_thread else None
                    },
                    "health_check": {
                        "alive": health_check_alive,
                        "name": self.health_check_thread.name if self.health_check_thread else None
                    }
                },
                "bot_processes": {
                    "running": running_profiles,
                    "total": total_processes
                },
                "group_scan": {
                    "queue_length": queue_length,
                    "processing": processing
                },
                "stats": self.stats.to_dict(),
                "config": asdict(self.config),
                "memory_usage_mb": round(memory_mb, 2) if memory_mb > 0 else None,
                "uptime_seconds": (datetime.now() - self.stats.start_time).total_seconds() if self.stats.start_time else None
            }

            return status_data


# Global instance với config mặc định
_runner = MultiThreadRunner()


def start_multi_thread(
    profile_ids: List[str],
    # Feed search params
    run_minutes: float = 30.0,
    rest_minutes: float = 120.0,
    text: str = "",
    mode: str = "feed",
    # Group scan params
    post_count: int = 10,
    start_date: str = "",
    end_date: str = ""
) -> Dict[str, Any]:
    """Convenience function để khởi động multi-thread runner"""
    return _runner.start_all(
        profile_ids=profile_ids,
        run_minutes=run_minutes,
        rest_minutes=rest_minutes,
        text=text,
        mode=mode,
        post_count=post_count,
        start_date=start_date,
        end_date=end_date
    )


def stop_multi_thread() -> Dict[str, Any]:
    """Convenience function để dừng multi-thread runner"""
    return _runner.stop_all()


def get_multi_thread_status() -> Dict[str, Any]:
    """Convenience function để kiểm tra status chi tiết"""
    return _runner.status()


def configure_multi_thread(config: RunnerConfig) -> Dict[str, Any]:
    """Cấu hình multi-thread runner

    Args:
        config: RunnerConfig object

    Returns:
        Dict với validation result
    """
    global _runner

    # Validate config
    errors = config.validate()
    if errors:
        return {"status": "error", "message": f"Configuration validation failed: {errors}"}

    # Update runner config
    _runner.config = config
    logger.info(f"✅ Đã cập nhật config: mode={config.mode}, run={config.run_minutes}m, rest={config.rest_minutes}m")

    return {"status": "ok", "message": "Configuration updated successfully"}


def set_multi_thread_callbacks(
    on_feed_search_error: Optional[Callable[[str, Exception], None]] = None,
    on_group_scan_error: Optional[Callable[[str, Exception], None]] = None,
    on_health_issue: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Thiết lập callbacks cho multi-thread runner

    Args:
        on_feed_search_error: Callback khi có lỗi feed search (message, exception)
        on_group_scan_error: Callback khi có lỗi group scan (message, exception)
        on_health_issue: Callback khi có vấn đề health (message)

    Returns:
        Dict với status
    """
    global _runner

    _runner.on_feed_search_error = on_feed_search_error
    _runner.on_group_scan_error = on_group_scan_error
    _runner.on_health_issue = on_health_issue

    logger.info("✅ Đã thiết lập callbacks cho multi-thread runner")
    return {"status": "ok", "message": "Callbacks set successfully"}


if __name__ == "__main__":
    # Example usage với enhanced features
    print("🚀 Enhanced Multi-thread Runner Example")
    print("=" * 60)

    # Example parameters
    profile_ids = ["profile1", "profile2"]  # Thay bằng profile IDs thực tế
    run_minutes = 5.0  # 5 phút chạy
    rest_minutes = 2.0  # 2 phút nghỉ
    text = "test search"
    mode = "feed+search"
    post_count = 5
    start_date = "2024-12-01"
    end_date = "2024-12-31"

    # Thiết lập callbacks để demo
    def on_feed_error(msg, exc):
        print(f"📢 Feed Search Error: {msg}")

    def on_group_error(msg, exc):
        print(f"📢 Group Scan Error: {msg}")

    def on_health_issue(msg):
        print(f"📢 Health Issue: {msg}")

    set_multi_thread_callbacks(
        on_feed_search_error=on_feed_error,
        on_group_scan_error=on_group_error,
        on_health_issue=on_health_issue
    )

    # Tùy chỉnh config
    custom_config = RunnerConfig(
        run_minutes=run_minutes,
        rest_minutes=rest_minutes,
        text=text,
        mode=mode,
        post_count=post_count,
        start_date=start_date,
        end_date=end_date,
        max_retries=2,
        health_check_interval=5.0
    )

    config_result = configure_multi_thread(custom_config)
    print(f"Config result: {config_result}")

    # Start multi-thread
    print("\nKhởi động multi-thread runner...")
    result = start_multi_thread(
        profile_ids=profile_ids,
        run_minutes=run_minutes,
        rest_minutes=rest_minutes,
        text=text,
        mode=mode,
        post_count=post_count,
        start_date=start_date,
        end_date=end_date
    )
    print(f"Start result: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # Monitor status với health check
    print("\n📊 Monitoring status (Ctrl+C để dừng)...")
    try:
        iteration = 0
        while True:
            iteration += 1
            status = get_multi_thread_status()

            print(f"\n--- Status Check #{iteration} ---")
            print(f"Running: {status['is_running']}")
            print(f"Health Score: {status['health_score']}/100")
            if status['health_issues']:
                print(f"Health Issues: {status['health_issues']}")

            print(f"Threads: Feed={status['threads']['feed_search']['alive']}, Group={status['threads']['group_scan']['alive']}, Health={status['threads']['health_check']['alive']}")
            print(f"Bot Processes: {len(status['bot_processes']['running'])}/{status['bot_processes']['total']} running")
            print(f"Group Queue: {status['group_scan']['queue_length']} (processing: {status['group_scan']['processing']})")

            if status.get('uptime_seconds'):
                print(f"Uptime: {status['uptime_seconds']:.1f}s")

            # Exit condition
            if not status["is_running"]:
                print("✅ Runner đã dừng")
                break

            if iteration >= 50:  # Safety limit
                print("⚠️ Đã monitor đủ lâu, dừng...")
                break

            time.sleep(3)

    except KeyboardInterrupt:
        print("\nNhận Ctrl+C, graceful shutdown...")
        stop_result = stop_multi_thread()
        print(f"Stop result: {json.dumps(stop_result, indent=2, ensure_ascii=False)}")

    print("\n✅ Example hoàn thành!")
    print("💡 Để sử dụng trong production:")
    print("   - Import các functions từ multi_thread module")
    print("   - Sử dụng configure_multi_thread() để tùy chỉnh")
    print("   - Set callbacks để handle errors")
    print("   - Monitor với get_multi_thread_status()")
