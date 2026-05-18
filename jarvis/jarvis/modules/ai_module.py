"""
JARVIS AI Module
Handles communication with local/remote LLMs via LangChain.
Supports Ollama (local), OpenAI, and HuggingFace backends.
"""

from typing import Optional
from core.config import Config


class AIModule:
    """
    Wraps LangChain LLM backends.
    Falls back gracefully if dependencies are missing.
    """

    def __init__(self, config: Config):
        self.config = config
        self.llm = None
        self.chat_history = []
        self._init_llm()

    def _init_llm(self):
        provider = self.config.ai.provider

        if provider == "ollama":
            self._init_ollama()
        elif provider == "openai":
            self._init_openai()
        elif provider == "huggingface":
            self._init_huggingface()
        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    def _init_ollama(self):
        from langchain_community.chat_models import ChatOllama
        self.llm = ChatOllama(
            model=self.config.ai.model,
            base_url=self.config.ai.ollama_host,
            temperature=self.config.ai.temperature,
        )
        print(f"[AI] Ollama connected: {self.config.ai.ollama_host} / {self.config.ai.model}")

    def _init_openai(self):
        from langchain_openai import ChatOpenAI
        import os
        os.environ["OPENAI_API_KEY"] = self.config.ai.openai_api_key
        self.llm = ChatOpenAI(
            model=self.config.ai.model,
            temperature=self.config.ai.temperature,
            max_tokens=self.config.ai.max_tokens,
        )
        print(f"[AI] OpenAI connected: {self.config.ai.model}")

    def _init_huggingface(self):
        from langchain_community.llms import HuggingFacePipeline
        from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
        import torch

        device = 0 if torch.cuda.is_available() else -1
        pipe = pipeline(
            "text-generation",
            model=self.config.ai.model,
            max_new_tokens=self.config.ai.max_tokens,
            device=device,
            do_sample=True,
            temperature=self.config.ai.temperature,
        )
        self.llm = HuggingFacePipeline(pipeline=pipe)
        print(f"[AI] HuggingFace model loaded: {self.config.ai.model}")

    def chat(self, user_message: str, context: str = "") -> str:
        """
        Send a message to the LLM and return the response.
        Maintains a sliding conversation window.
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        system = self.config.ai.system_prompt
        if context:
            system += f"\n\n{context}"

        messages = [SystemMessage(content=system)]

        # Sliding window of recent history
        window = self.config.memory.conversation_window
        for entry in self.chat_history[-window:]:
            if entry["role"] == "user":
                messages.append(HumanMessage(content=entry["content"]))
            else:
                messages.append(AIMessage(content=entry["content"]))

        messages.append(HumanMessage(content=user_message))

        response = self.llm.invoke(messages)
        text = response.content if hasattr(response, "content") else str(response)

        # Update local history
        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": text})

        return text

    def clear_history(self):
        self.chat_history.clear()

    def summarize(self, text: str) -> str:
        """Quick summarization helper."""
        return self.chat(f"Summarize this concisely:\n\n{text}")

    def generate_code(self, task: str, language: str = "python") -> str:
        """Code generation helper."""
        prompt = (
            f"Write {language} code to: {task}\n"
            "Return only the code, no explanation. "
            "Include inline comments."
        )
        return self.chat(prompt)
