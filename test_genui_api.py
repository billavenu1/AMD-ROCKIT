import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

async def test_stream():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: No API key found in .env")
        return

    print(f"Using API Key: {api_key[:10]}...")
    
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    try:
        print("Requesting stream...")
        stream = await client.chat.completions.create(
            model="gemini-3-flash-preview",
            messages=[{"role": "user", "content": "hi"}],
            stream=True
        )

        print("Response: ", end="", flush=True)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print("\n\nSuccess!")
    except Exception as e:
        print(f"\n\nError: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())
