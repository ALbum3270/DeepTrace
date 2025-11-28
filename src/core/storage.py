"""
Storage Manager: 负责基于文件的运行结果存储。
"""
from pathlib import Path
from datetime import datetime
import json
import uuid
from typing import Iterable, Any, Union

from .models import Timeline, Evidence

# 项目根目录（storage.py 在 src/core/，往上两级）
PROJECT_ROOT = Path(__file__).parent.parent.parent

class StorageManager:
    def __init__(self, base_dir: Union[Path, str] = "data/runs"):
        # 确保 base_dir 是相对于项目根目录的绝对路径
        if isinstance(base_dir, str):
            self.base_dir = PROJECT_ROOT / base_dir
        else:
            self.base_dir = base_dir

    def start_run(self, topic: str) -> Path:
        """Create a run directory and return its path."""
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        slug = self._slugify(topic)
        short_id = uuid.uuid4().hex[:6]

        run_id = f"{timestamp}_{slug}_{short_id}"
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    def save_meta(
        self,
        run_dir: Path,
        *,
        topic: str,
        start_time: datetime,
        end_time: datetime,
        model: str,
        config: dict[str, Any],
        stats: dict[str, Any],
        version: str = "0.1.0",
    ) -> None:
        meta = {
            "run_id": run_dir.name,
            "version": version,
            "topic": topic,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "model": model,
            "config": config,
            "stats": stats,
        }
        with (run_dir / "meta.json").open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def save_timeline(self, run_dir: Path, timeline: Timeline) -> None:
        data = timeline.model_dump(mode="json")
        with (run_dir / "timeline.json").open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_evidences(
        self,
        run_dir: Path,
        evidences: Iterable[Evidence],
    ) -> None:
        path = run_dir / "evidences.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for ev in evidences:
                line = json.dumps(ev.model_dump(mode="json"), ensure_ascii=False)
                f.write(line + "\n")

    def save_report(self, run_dir: Path, report_md: str) -> None:
        (run_dir / "report.md").write_text(report_md, encoding="utf-8")

    def _slugify(self, topic: str) -> str:
        # 非严格版：够用即可
        s = topic.strip().lower()
        for ch in " ，。！？!?:：/\\" :
            s = s.replace(ch, "-")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        s = "".join(ch for ch in s if ch in allowed)
        return s or "topic"
