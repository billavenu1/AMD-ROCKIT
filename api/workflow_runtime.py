"""
api/workflow_runtime.py
========================
Runtime executor for published ARIA workflows.

Each workflow is a configuration object (model, instructions, knowledge, tools).
The runtime interprets the config at request time and chains:
  Knowledge Retrieval → System Prompt → LLM Call → Tool Execution
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class WorkflowConfig:
    """Immutable snapshot of a workflow's configuration."""
    model: str = "Qwen 7B Instruct"
    instructions: str = ""
    knowledge_type: str = ""        # "Grounded Project" | "Vision"
    knowledge_source: str = ""      # "HR Index" | "Image" | "Video Intelligence" etc.
    tools: List[str] = field(default_factory=list)


@dataclass
class InvocationMetrics:
    total_invocations: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.total_invocations == 0:
            return 0.0
        return self.total_latency_ms / self.total_invocations


class WorkflowRuntime:
    """
    Executes a workflow pipeline based on its stored configuration.

    Orchestrates:
      1. Knowledge retrieval (RAG / Vision)
      2. System prompt + context injection
      3. LLM inference via llm_provider
      4. Tool execution (if active)
    """

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.metrics = InvocationMetrics()

    async def invoke(self, user_message: str) -> Dict[str, Any]:
        """
        Execute the full pipeline for a single user message.

        Returns
        -------
        dict with keys: response, latency_ms, knowledge_context
        """
        from api.llm_provider import get_chat_completion

        start = time.time()

        # Step 1: Resolve knowledge context
        knowledge_context = await self._resolve_knowledge(user_message)

        # If Vision, directly return the results without invoking the LLM
        if self.config.knowledge_type == "Vision":
            latency_ms = (time.time() - start) * 1000
            self.metrics.total_invocations += 1
            self.metrics.total_latency_ms += latency_ms
            
            try:
                parsed = json.loads(knowledge_context)
                # Format nicely
                if isinstance(parsed, list) and len(parsed) > 0:
                    response_text = f"Found {len(parsed)} relevant visual matches:\n" + json.dumps(parsed, indent=2)
                else:
                    response_text = "Here is the vision data:\n" + json.dumps(parsed, indent=2)
            except:
                response_text = knowledge_context if knowledge_context else "No visual matches found."

            return {
                "response": response_text,
                "latency_ms": round(latency_ms, 1),
                "knowledge_context": None,
            }

        # Step 2: Build message list
        messages: list[dict] = []

        # System prompt (instructions)
        if self.config.instructions:
            messages.append({
                "role": "system",
                "content": self.config.instructions,
            })

        # Inject knowledge context
        if knowledge_context:
            messages.append({
                "role": "system",
                "content": f"Relevant context from knowledge base:\n\n{knowledge_context}",
            })

        # Inject active tools description
        if self.config.tools:
            tools_desc = ", ".join(self.config.tools)
            messages.append({
                "role": "system",
                "content": (
                    f"You have access to the following tools: {tools_desc}. "
                    "Use them when relevant to the user's request."
                ),
            })

        # User message
        messages.append({"role": "user", "content": user_message})

        # Step 3: Call LLM
        try:
            response_text = await get_chat_completion(
                messages=messages,
                model=self.config.model,
            )
        except Exception as e:
            logger.error(f"Workflow LLM call failed: {e}")
            response_text = f"Error: Failed to get response from model `{self.config.model}`. {str(e)}"

        # Step 4: Record metrics
        latency_ms = (time.time() - start) * 1000
        self.metrics.total_invocations += 1
        self.metrics.total_latency_ms += latency_ms

        return {
            "response": response_text,
            "latency_ms": round(latency_ms, 1),
            "knowledge_context": knowledge_context[:200] if knowledge_context else None,
        }

    async def _resolve_knowledge(self, query: str) -> str:
        """
        Fetch relevant context from the configured knowledge source.

        For the hackathon, this returns descriptive placeholders for
        sources that aren't fully wired yet, and calls real pipelines
        where they exist.
        """
        k_type = self.config.knowledge_type
        k_source = self.config.knowledge_source

        if not k_type:
            return ""

        try:
            if k_type == "Vision":
                if k_source == "Video Intelligence":
                    return await self._query_video(query)
                elif k_source == "Image":
                    return await self._query_image(query)

            elif k_type == "Grounded Project":
                return await self._query_project(k_source, query)

        except Exception as e:
            logger.warning(f"Knowledge retrieval failed ({k_type}/{k_source}): {e}")
            return f"[Knowledge retrieval error: {e}]"

        return ""

    async def _query_video(self, query: str) -> str:
        """Query the video intelligence pipeline."""
        try:
            # Try to use the existing vision query module
            from vision.query.query_video import query_video
            results = await query_video(query)
            if results:
                return json.dumps(results, indent=2, default=str)
        except ImportError:
            logger.debug("Vision video query module not available")
        except Exception as e:
            logger.warning(f"Video query failed: {e}")
        return "[Video Intelligence: No results found]"

    async def _query_image(self, query: str) -> str:
        """Query the image intelligence pipeline."""
        try:
            from vision.query.query_image import query_image
            results = await query_image(query)
            if results:
                return json.dumps(results, indent=2, default=str)
        except ImportError:
            logger.debug("Vision image query module not available")
        except Exception as e:
            logger.warning(f"Image query failed: {e}")
        return "[Image Intelligence: No results found]"

    async def _query_project(self, source_name: str, query: str) -> str:
        """Query a grounded project RAG index."""
        try:
            # Use the existing embedding + search pipeline
            from api.llm_provider import embed_text
            from open_notebook.database.repository import repo_query

            embedding = embed_text(query)
            # Search the vector index for the given project
            results = await repo_query(
                """
                SELECT id, content, title
                FROM chunk
                WHERE embedding <|5|> $embedding
                ORDER BY vector::similarity(embedding, $embedding) DESC
                LIMIT 5
                """,
                {"embedding": embedding},
            )
            if results:
                context_parts = []
                for r in results:
                    title = r.get("title", "")
                    content = r.get("content", "")
                    context_parts.append(f"[{title}]\n{content}")
                return "\n\n---\n\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Project RAG query failed for '{source_name}': {e}")
        return f"[Grounded Project '{source_name}': No matching documents found]"
