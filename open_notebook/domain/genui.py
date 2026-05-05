import asyncio
from typing import ClassVar, Optional, List, Any
from loguru import logger
from pydantic import Field, ConfigDict

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.base import ObjectModel
from open_notebook.exceptions import DatabaseOperationError


class GenUISession(ObjectModel):
    table_name: ClassVar[str] = "genui_session"
    title: str = "New Chat"

    async def get_messages(self) -> List["GenUIMessage"]:
        try:
            session_id = str(self.id)
            msgs = await repo_query(
                """
                SELECT * FROM genui_message
                WHERE session_id = $record_id OR session_id = $string_id
                ORDER BY order ASC
                """,
                {
                    "record_id": ensure_record_id(session_id),
                    "string_id": session_id,
                },
            )
            return [GenUIMessage(**msg) for msg in msgs] if msgs else []
        except Exception as e:
            logger.error(f"Error fetching messages for genui session {self.id}: {str(e)}")
            raise DatabaseOperationError(e)


class GenUIMessage(ObjectModel):
    table_name: ClassVar[str] = "genui_message"
    session_id: Any
    role: str
    content: Any
    order: int
