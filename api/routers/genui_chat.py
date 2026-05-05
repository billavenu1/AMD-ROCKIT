import json
import asyncio
from typing import List, Optional, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from api.llm_provider import stream_chat_completion, get_default_model_id
from open_notebook.database.repository import repo_query, ensure_record_id
from open_notebook.domain.genui import GenUISession, GenUIMessage

router = APIRouter()

class SessionResponse(BaseModel):
    id: str
    title: str
    created: str
    updated: str

class MessageItem(BaseModel):
    role: str
    content: Any

class ChatRequest(BaseModel):
    threadId: Optional[str] = None
    messages: List[MessageItem]
    systemPrompt: Optional[str] = None
    model: Optional[str] = None

@router.post("/sessions", response_model=SessionResponse)
async def create_session():
    session = GenUISession()
    await session.save()
    return SessionResponse(
        id=session.id or "",
        title=session.title,
        created=str(session.created),
        updated=str(session.updated)
    )

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    sessions = await repo_query("SELECT * FROM genui_session ORDER BY updated DESC")
    return [SessionResponse(
        id=str(s["id"]),
        title=s.get("title", "New Chat"),
        created=str(s.get("created", "")),
        updated=str(s.get("updated", ""))
    ) for s in sessions]

@router.get("/sessions/{session_id}", response_model=List[MessageItem])
async def get_session_history(session_id: str):
    full_session_id = session_id if session_id.startswith("genui_session:") else f"genui_session:{session_id}"
    session = await GenUISession.get(full_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await session.get_messages()
    return [MessageItem(role=msg.role, content=msg.content) for msg in messages]

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    full_session_id = session_id if session_id.startswith("genui_session:") else f"genui_session:{session_id}"
    session = await GenUISession.get(full_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await repo_query(
        "DELETE FROM genui_message WHERE session_id = $record_id OR session_id = $string_id",
        {"record_id": ensure_record_id(full_session_id), "string_id": full_session_id},
    )
    await session.delete()
    return {"success": True}

async def generate_chat_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    try:
        session_id = request.threadId
        if not session_id:
            logger.info("No threadId provided, creating new GenUISession")
            session = GenUISession()
            try:
                await session.save()
                logger.info(f"New session saved with ID: {session.id}")
            except Exception as e:
                logger.error(f"Failed to save new GenUISession: {e}")
                raise Exception(f"Database Error (Session Save): {str(e)}")
            session_id = str(session.id)
        else:
            full_session_id = session_id if session_id.startswith("genui_session:") else f"genui_session:{session_id}"
            logger.info(f"Using existing threadId: {full_session_id}")
            try:
                session = await GenUISession.get(full_session_id)
            except Exception as e:
                logger.error(f"Failed to fetch GenUISession {full_session_id}: {e}")
                raise Exception(f"Database Error (Session Get): {str(e)}")

            if not session:
                logger.info(f"Session {full_session_id} not found, creating new one")
                session = GenUISession()
                session.id = ensure_record_id(full_session_id)
                try:
                    await session.save()
                    logger.info(f"New session (forced ID) saved: {session.id}")
                except Exception as e:
                    logger.error(f"Failed to save GenUISession with forced ID: {e}")
                    raise Exception(f"Database Error (Session Save Forced): {str(e)}")
                session_id = str(session.id)

        full_session_id = session_id if session_id.startswith("genui_session:") else f"genui_session:{session_id}"
        
        # Save user messages to DB
        logger.info(f"Cleaning up old messages for session: {full_session_id}")
        try:
            await repo_query(
                "DELETE FROM genui_message WHERE session_id = $record_id OR session_id = $string_id",
                {"record_id": ensure_record_id(full_session_id), "string_id": full_session_id},
            )
        except Exception as e:
            logger.warning(f"Failed to cleanup old messages (non-critical): {e}")

        logger.info(f"Saving {len(request.messages)} user messages to DB")
        for i, msg in enumerate(request.messages):
            try:
                db_msg = GenUIMessage(
                    session_id=ensure_record_id(full_session_id),
                    role=msg.role,
                    content=msg.content,
                    order=i
                )
                await db_msg.save()
            except Exception as e:
                logger.error(f"Failed to save message {i} for session {full_session_id}: {e}")
                raise Exception(f"Database Error (Message Save {i}): {str(e)}")

        if len(request.messages) > 0 and session.title == "New Chat":
            first_user_msg = next((m for m in request.messages if m.role == "user"), None)
            if first_user_msg:
                session.title = first_user_msg.content[:30] + ("..." if len(first_user_msg.content) > 30 else "")
                try:
                    await session.save()
                    logger.info(f"Updated session title to: {session.title}")
                except Exception as e:
                    logger.warning(f"Failed to update session title: {e}")

        # Resolve model: request body > env var > available_models.json default
        model_name = request.model or get_default_model_id()

        full_response = ""
        openai_messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Use systemPrompt from request if provided, otherwise fallback to default
        sys_prompt = request.systemPrompt or "You are a helpful assistant. You can generate UI components using React and Tailwind if requested. Always wrap UI components in appropriate code blocks."

        # Stream via centralized llm_provider
        async for chunk_json in stream_chat_completion(
            messages=openai_messages,
            model=model_name,
            system_prompt=sys_prompt,
        ):
            # Parse to accumulate full_response for DB persistence
            try:
                data = json.loads(chunk_json)
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_response += content
            except json.JSONDecodeError:
                pass

            yield chunk_json

        # Save assistant message before finishing to ensure persistence
        try:
            db_msg = GenUIMessage(
                session_id=ensure_record_id(full_session_id),
                role="assistant",
                content=full_response,
                order=len(request.messages)
            )
            await db_msg.save()
            logger.info(f"Assistant message saved for session {full_session_id}")
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")

    except Exception as e:
        logger.error(f"Error in GenUI chat stream processing: {e}")
        error_chunk = {
            "id": "error",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "error",
            "choices": [{"index": 0, "delta": {"content": f"\n\n**Internal Error:** {str(e)}"}, "finish_reason": "stop"}]
        }
        yield f"{json.dumps(error_chunk)}\n"


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    # Ensure session exists to get the ID for the header
    session_id = request.threadId
    if not session_id:
        session = GenUISession()
        await session.save()
        session_id = str(session.id)
        # Update request object so generator uses the same ID
        request.threadId = session_id
    
    return StreamingResponse(
        generate_chat_stream(request),
        media_type="application/x-ndjson",
        headers={
            "X-Thread-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
