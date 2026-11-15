from models.chat import ChatMessage
from utils.run_store import RunStore

CHAT_COLUMNS = ("id", "run_id", "seq", "role", "content_json", "status", "created_at")


class ChatStore:
    def __init__(self, store: RunStore) -> None:
        self._store = store

    def append(self, run_id: str, *messages: ChatMessage) -> bool:
        with self._store._use() as connection:
            if connection.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
                return False
            last = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM chat_messages WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            rows = [
                tuple(
                    self._store._clean(value)
                    for value in (
                        message.id, run_id, last + offset, message.role, message.model_dump_json(),
                        message.status, message.created_at,
                    )
                )
                for offset, message in enumerate(messages, start=1)
            ]
            connection.executemany(
                f"INSERT INTO chat_messages ({', '.join(CHAT_COLUMNS)}) VALUES ({', '.join('?' for _ in CHAT_COLUMNS)})",
                rows,
            )
        return True

    def list(self, run_id: str) -> list[ChatMessage]:
        with self._store._use() as connection:
            rows = connection.execute(
                "SELECT content_json FROM chat_messages WHERE run_id = ? ORDER BY seq", (run_id,)
            ).fetchall()
        return [ChatMessage.model_validate_json(row["content_json"]) for row in rows]

    def count(self, run_id: str, role: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM chat_messages WHERE run_id = ?"
        parameters: tuple[str, ...] = (run_id,)
        if role is not None:
            query += " AND role = ?"
            parameters += (role,)
        with self._store._use() as connection:
            return connection.execute(query, parameters).fetchone()[0]

    def clear(self, run_id: str) -> int:
        with self._store._use() as connection:
            return connection.execute("DELETE FROM chat_messages WHERE run_id = ?", (run_id,)).rowcount
