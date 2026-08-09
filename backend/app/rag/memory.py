"""会话记忆 — 内存存储最近 N 轮对话（不依赖数据库，环境未就绪也可用）

设计说明：
- 以 conversation_id 为键，存储 {role, content} 消息列表
- 只保留最近 MAX_TURNS 轮（默认 6 轮），防止 token 无限膨胀
- 内存实现简单可靠；未来可替换为 PostgreSQL 持久化
"""
# ponytail: 内存存储，重启即丢；会话多/需持久化时换 PostgreSQL 表
import time
from collections import defaultdict, deque

MAX_TURNS = 6  # 保留最近 6 轮对话


class SessionMemory:
    """线程安全的内存会话存储（asyncio 单线程下 dict 操作原子）"""

    def __init__(self, max_turns: int = MAX_TURNS):
        self._store: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_turns * 2))
        self._timestamps: dict[str, float] = {}
        self._titles: dict[str, str] = {}   # 会话标题（重命名/自动生成）

    def add(self, conversation_id: str, role: str, content: str) -> None:
        """添加一条消息（user 或 assistant）"""
        self._store[conversation_id].append({
            "role": role,
            "content": content,
            "ts": time.time(),
        })
        self._timestamps[conversation_id] = time.time()

    def get_history(self, conversation_id: str) -> list[dict]:
        """获取该会话的完整历史（不含 ts 字段）"""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self._store.get(conversation_id, [])
        ]

    def clear(self, conversation_id: str) -> None:
        """清空指定会话"""
        self._store.pop(conversation_id, None)
        self._timestamps.pop(conversation_id, None)

    def rename(self, conversation_id: str, new_title: str) -> bool:
        """重命名会话（标题取第一条用户消息前 30 字）"""
        if conversation_id not in self._store or not self._store[conversation_id]:
            return False
        self._titles[conversation_id] = new_title.strip()[:30]
        return True

    def get_title(self, conversation_id: str) -> str:
        """取会话标题（无则自动生成）"""
        if conversation_id in self._titles:
            return self._titles[conversation_id]
        for msg in self._store.get(conversation_id, []):
            if msg.get("role") == "user":
                title = msg["content"].strip().replace("\n", " ")[:30]
                self._titles[conversation_id] = title
                return title
        return "新会话"

    def list_conversations(self, limit: int = 20) -> list[dict]:
        """列出最近会话（按最后活动时间排序）"""
        items = [
            {
                "conversation_id": cid,
                "last_active": ts,
                "messages": len(self._store[cid]),
                "title": self.get_title(cid),
            }
            for cid, ts in self._timestamps.items()
        ]
        items.sort(key=lambda x: x["last_active"], reverse=True)
        return items[:limit]


# 全局单例
_memory = SessionMemory()


def get_memory() -> SessionMemory:
    return _memory


def format_history(history: list[dict], max_chars: int = 2000) -> str:
    """将历史消息格式化为 prompt 片段"""
    if not history:
        return ""
    lines = []
    total = 0
    for m in history:
        snippet = m["content"].replace("\n", " ")[:300]
        if total + len(snippet) > max_chars:
            break
        lines.append(f"{'用户' if m['role'] == 'user' else '顾问'}: {snippet}")
        total += len(snippet)
    return "\n".join(lines)
