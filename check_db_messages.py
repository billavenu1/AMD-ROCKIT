import asyncio
import json
from dotenv import load_dotenv
load_dotenv()
from open_notebook.database.repository import repo_query, ensure_record_id

async def check_messages():
    sessions = await repo_query("SELECT * FROM genui_session ORDER BY updated DESC LIMIT 1")
    if not sessions:
        print("No sessions found")
        return
    
    session = sessions[0]
    session_id = ensure_record_id(str(session['id']))
    print(f"Latest Session: {session_id} - {session.get('title')}")
    
    messages = await repo_query(
        "SELECT * FROM genui_message WHERE session_id = $id ORDER BY order ASC",
        {"id": session_id}
    )
    print(f"Messages for {session_id}:")
    for m in messages:
        print(f"  [{m['role']}] {m['content'][:50]}...")

if __name__ == "__main__":
    asyncio.run(check_messages())
