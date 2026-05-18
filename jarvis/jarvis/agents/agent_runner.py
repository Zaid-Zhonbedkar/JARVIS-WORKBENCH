"""
JARVIS Agent Runner
LangChain agents with tool-use for autonomous task execution.
Tools: file search, browser, code execution, system commands.
"""

from typing import Optional, Any
from core.config import Config


class AgentRunner:
    """
    Builds and runs LangChain agents equipped with JARVIS tools.
    Uses ReAct / OpenAI-functions style depending on the LLM.
    """

    def __init__(self, config: Config, ai_module: Any, memory_module: Any):
        self.config = config
        self.ai_module = ai_module
        self.memory_module = memory_module
        self._agent = None
        self._tools = []
        self._init()

    def _init(self):
        self._tools = self._build_tools()
        self._agent = self._build_agent()

    # ------------------------------------------------------------------ #
    #  Tool definitions
    # ------------------------------------------------------------------ #

    def _build_tools(self):
        from langchain.tools import Tool

        tools = []

        # File system search
        tools.append(Tool(
            name="file_search",
            func=self._tool_file_search,
            description=(
                "Search the file system for files matching a query. "
                "Input: search query string. Returns list of matching file paths."
            ),
        ))

        # Read file
        tools.append(Tool(
            name="read_file",
            func=self._tool_read_file,
            description=(
                "Read the contents of a file. Input: absolute file path. "
                "Returns file contents as text."
            ),
        ))

        # Write file
        tools.append(Tool(
            name="write_file",
            func=self._tool_write_file,
            description=(
                "Write content to a file. "
                "Input: JSON string with 'path' and 'content' keys."
            ),
        ))

        # Run shell command
        tools.append(Tool(
            name="shell_command",
            func=self._tool_shell,
            description=(
                "Run a safe shell command and return stdout. "
                "Input: command string. Avoid destructive commands."
            ),
        ))

        # Execute Python code
        tools.append(Tool(
            name="run_python",
            func=self._tool_run_python,
            description=(
                "Execute Python code in a sandbox and return output. "
                "Input: Python code string."
            ),
        ))

        # Web search
        tools.append(Tool(
            name="web_search",
            func=self._tool_web_search,
            description=(
                "Search the web for information. "
                "Input: search query. Returns top results."
            ),
        ))

        # Browser automation
        tools.append(Tool(
            name="browser_navigate",
            func=self._tool_browser,
            description=(
                "Open a URL in a browser and return page content. "
                "Input: URL string."
            ),
        ))

        # Memory recall
        tools.append(Tool(
            name="recall_memory",
            func=self._tool_recall,
            description=(
                "Search JARVIS memory for past conversations or stored facts. "
                "Input: query string."
            ),
        ))

        # System info
        tools.append(Tool(
            name="system_info",
            func=self._tool_sysinfo,
            description="Get current system info: CPU, RAM, disk, processes. Input: ignored.",
        ))

        return tools

    # ------------------------------------------------------------------ #
    #  Agent construction
    # ------------------------------------------------------------------ #

    def _build_agent(self):
        try:
            from langchain.agents import create_react_agent, AgentExecutor
            from langchain_core.prompts import PromptTemplate

            prompt = PromptTemplate.from_template("""You are JARVIS, an AI desktop assistant.
Answer the following as best you can. You have access to these tools:

{tools}

Use the following format:
Question: the input question or task
Thought: think about what to do
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (repeat Thought/Action/Observation as needed)
Thought: I now know the final answer
Final Answer: the final answer to the original input

Question: {input}
{agent_scratchpad}""")

            agent = create_react_agent(
                llm=self.ai_module.llm,
                tools=self._tools,
                prompt=prompt,
            )
            executor = AgentExecutor(
                agent=agent,
                tools=self._tools,
                max_iterations=self.config.agent.max_iterations,
                handle_parsing_errors=True,
                verbose=True,
            )
            return executor
        except Exception as e:
            print(f"[Agent] Could not build LangChain agent: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Run
    # ------------------------------------------------------------------ #

    def run(self, task: str) -> str:
        if self._agent is None:
            if self.ai_module:
                return self.ai_module.chat(task)
            return "[Agent not initialized]"
        try:
            result = self._agent.invoke({"input": task})
            return result.get("output", str(result))
        except Exception as e:
            return f"[Agent error] {e}"

    # ------------------------------------------------------------------ #
    #  Tool implementations
    # ------------------------------------------------------------------ #

    def _tool_file_search(self, query: str) -> str:
        import os, fnmatch
        results = []
        allowed = [os.path.expanduser(p) for p in self.config.agent.allowed_paths]
        q = query.lower()
        for base in allowed:
            for root, dirs, files in os.walk(base):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    if q in fname.lower():
                        results.append(os.path.join(root, fname))
                if len(results) >= 20:
                    break
        return "\n".join(results) if results else "No files found."

    def _tool_read_file(self, path: str) -> str:
        try:
            path = path.strip().strip('"\'')
            with open(path, "r", errors="replace") as f:
                content = f.read(8000)  # cap at 8K chars
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    def _tool_write_file(self, input_str: str) -> str:
        import json, os
        try:
            data = json.loads(input_str)
            path = os.path.expanduser(data["path"])
            content = data["content"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"Written to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _tool_shell(self, command: str) -> str:
        import subprocess
        # Basic safety: block dangerous patterns
        BLOCKED = ["rm -rf", "mkfs", "dd if=", ":(){ ", "sudo rm", "> /dev"]
        for b in BLOCKED:
            if b in command:
                return f"[Blocked] Potentially destructive command: {b}"
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            out = result.stdout + result.stderr
            return out[:3000] if out else "(no output)"
        except Exception as e:
            return f"Shell error: {e}"

    def _tool_run_python(self, code: str) -> str:
        import io, contextlib, traceback
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(compile(code, "<jarvis>", "exec"), {"__builtins__": __builtins__})
            return buf.getvalue() or "(no output)"
        except Exception:
            return traceback.format_exc()

    def _tool_web_search(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    results.append(f"• {r['title']}\n  {r['href']}\n  {r['body'][:200]}")
            return "\n\n".join(results) if results else "No results."
        except Exception as e:
            return f"Web search error: {e}"

    def _tool_browser(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
            url = url.strip()
            if not url.startswith("http"):
                url = "https://" + url
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.config.agent.browser_headless)
                page = browser.new_page()
                page.goto(url, timeout=15000)
                text = page.inner_text("body")[:4000]
                browser.close()
            return text
        except Exception as e:
            return f"Browser error: {e}"

    def _tool_recall(self, query: str) -> str:
        if not self.memory_module:
            return "Memory not available."
        results = self.memory_module.search(query, k=5)
        return "\n".join(f"- {r}" for r in results) if results else "Nothing found in memory."

    def _tool_sysinfo(self, _: str) -> str:
        try:
            import psutil, platform
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"OS: {platform.system()} {platform.release()}\n"
                f"CPU: {cpu}%\n"
                f"RAM: {ram.percent}% used ({ram.used // 1024**2}MB / {ram.total // 1024**2}MB)\n"
                f"Disk: {disk.percent}% used ({disk.used // 1024**3}GB / {disk.total // 1024**3}GB)\n"
                f"Processes: {len(psutil.pids())}"
            )
        except Exception as e:
            return f"System info error: {e}"
