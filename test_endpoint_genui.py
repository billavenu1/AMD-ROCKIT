import httpx
import asyncio
import json
import sys

async def test_genui_endpoint():
    # The FastAPI server typically runs on port 5055 in this project
    url = "http://localhost:5055/api/genui/chat"
    
    payload = {
        "messages": [
            {"role": "user", "content": "Reply with exactly: 'Hello from GenUI test'"}
        ],
        "systemPrompt": "You are a helpful assistant."
    }
    
    print(f"--- Testing GenUI Endpoint ---")
    print(f"Target URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 30)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"Error: Status code {response.status_code}")
                    body = await response.aread()
                    print(f"Response body: {body.decode()}")
                    return

                print("Streaming response:")
                full_content = ""
                async for line in response.aiter_lines():
                    if line:
                        data_str = line.strip()
                        if not data_str:
                            continue
                        
                        try:
                            # print(f"DEBUG RAW: {data_str}")
                            data = json.loads(data_str)
                            
                            # Check for the error format we added in the previous task
                            if "error" in data:
                                print(f"\n[BACKEND ERROR]: {data['error']}")
                                break
                            
                            # Handle OpenAI format delta
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content")
                                if content is not None:
                                    full_content += content
                                    print(content, end="", flush=True)
                                    
                        except json.JSONDecodeError:
                            # Might be a raw error string
                            print(f"\n[RAW]: {data_str}")

                if full_content:
                    print("\n" + "-" * 30)
                    print("Test Passed: Received valid streamed content.")
                else:
                    print("\n" + "-" * 30)
                    print("Test Failed: Stream completed but no content was received.")

    except httpx.ConnectError:
        print("\nError: Could not connect to the server. Is the FastAPI backend running on port 5055?")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_genui_endpoint())
