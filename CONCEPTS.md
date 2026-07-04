# Concepts — Job Discovery MCP

> Revision notes for this learning project. Three topics only.

---

## 1. MCP (Model Context Protocol)

An open standard that lets an AI app connect to external tools and data in a
consistent way — "USB-C for AI".

- **Host** — the AI app (holds the model), e.g. Claude.
- **Client** — the connector inside the host; one per server.
- **Server** — *what you build here*. Exposes capabilities.

Server exposes three kinds of things:
- **Tools** — model-callable actions (e.g. `search_jobs`, `get_job_details`).
- **Resources** — read-only data the host loads as context.
- **Prompts** — reusable, user-triggered templates.

Rule of thumb: model decides when to call it → **tool**; it's context to read → **resource**; user triggers a template → **prompt**.

---

## 2. Transport / Tools — stdio and http

MCP is transport-agnostic. Two common transports:

- **stdio** — server runs as a local subprocess; messages over stdin/stdout.
  Simplest for local dev and desktop apps. **Start here.**
  - ⚠️ Log to **stderr**, never stdout — stdout is the protocol channel.
- **HTTP (Streamable HTTP)** — server runs as a web service; good for remote/hosted servers.

Under the hood, both carry **JSON-RPC 2.0** messages (the SDK handles this for you).

A **tool** = name + description + input schema + handler.
- The model reads the *description* to decide when to call it — write it clearly.
- The *input schema* (JSON Schema) validates arguments before your code runs.

---

## 3. LangChain

A framework for building applications with LLMs — chains, agents, memory, and
integrations with data sources and tools.

- **Chains** — sequences of steps (prompt → model → parse → next step).
- **Agents** — an LLM that decides which tools to call, in what order.
- **Tools** — functions the agent can invoke (same idea as MCP tools).
- **Memory** — carries state/context across turns.

**How it relates to this project:** LangChain can act as an MCP *host/client* —
it can consume tools your MCP server exposes and let an agent call `search_jobs`
as part of a larger workflow.

---

## 4. FastMCP

The high-level, Pythonic framework for **building** MCP servers (and clients) with
minimal boilerplate. You write plain Python functions with type hints; FastMCP
generates the tool/resource schemas and handles the protocol for you.

- Install: `pip install fastmcp`
- Create a server, decorate functions, and run it:

```python
from fastmcp import FastMCP

mcp = FastMCP("Job Discovery")

@mcp.tool
def search_jobs(query: str, location: str = "", remote: bool = False) -> list[dict]:
    """Search job postings by keyword, location, and remote flag."""
    ...  # your lookup logic
    return [{"id": "1", "title": "Backend Engineer"}]

if __name__ == "__main__":
    mcp.run()  # stdio by default; mcp.run(transport="http") for HTTP
```

Key pieces:
- **`FastMCP(...)`** — the server object.
- **Decorators** — `@mcp.tool`, `@mcp.resource("uri://...")`, `@mcp.prompt` register each primitive. Type hints → input schema automatically; the docstring becomes the description.
- **`mcp.run()`** — starts the server; pick the transport (`stdio` default, or `http`).
- **CLI** — `fastmcp run` / `fastmcp dev` (with the Inspector) / `fastmcp install`.
- **`Client`** — FastMCP also ships a client for calling MCP servers from Python.

**Versions (know this):** *FastMCP 1.0* was contributed into the official MCP
Python SDK (available as `mcp.server.fastmcp.FastMCP`). *FastMCP 2.0* (docs at
gofastmcp.com) is the actively developed standalone project with more features
(auth, clients, testing, deployment). `pip install fastmcp` gets 2.x.

**For this project:** FastMCP is the fastest way to stand up your server and
expose `search_jobs` — this is likely the main tool you'll build with.

---

## 5. langchain-groq

The LangChain integration for **Groq** — an inference provider whose LPU hardware
runs open models (Llama, etc.) very fast. Gives you a drop-in LangChain chat model.

- Install: `pip install langchain-groq`
- Auth: set the `GROQ_API_KEY` environment variable.
- Provides the **`ChatGroq`** chat model:

```python
from langchain_groq import ChatGroq

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
resp = llm.invoke("Summarize this job posting: ...")
print(resp.content)
```

- Works like any LangChain chat model: `.invoke()`, `.stream()`, `.bind_tools()`,
  and it plugs into chains and agents.

**For this project:** use `ChatGroq` as the fast, low-cost LLM backing the
LangChain agent that calls your job-search tools.

---

## 6. langchain-mcp-adapters

The bridge between **MCP and LangChain/LangGraph**: it converts the tools exposed
by an MCP server into LangChain-compatible tools, so a LangChain agent can call
them directly. (This is the package meant by "langchain adapters".)

- Install: `pip install langchain-mcp-adapters`
- Key pieces:
  - **`MultiServerMCPClient`** — connect to one or more MCP servers (via `stdio`
    or `streamable_http`) and pull their tools.
  - **`load_mcp_tools`** — load tools from an existing MCP client session.

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

client = MultiServerMCPClient({
    "jobs": {"command": "python", "args": ["server.py"], "transport": "stdio"},
})
tools = await client.get_tools()                      # your search_jobs, etc.
agent = create_react_agent(ChatGroq(model="llama-3.3-70b-versatile"), tools)
result = await agent.ainvoke({"messages": "Find remote Python jobs"})
```

**For this project — how it all connects:**

```
FastMCP server (search_jobs)  ──MCP──►  langchain-mcp-adapters  ──►  LangChain/LangGraph agent  ◄── ChatGroq (LLM)
```

You build the tool with **FastMCP**, expose it over **stdio/http**, adapt it with
**langchain-mcp-adapters**, and drive it with a **LangChain** agent powered by
**langchain-groq**.

## 7. How This Example Project Works

Three files, three jobs. This section traces the *actual* current code, not a
generic example.

```
┌─────────────────────────────────────────────────────────────────────┐
│ client.py  — the HOST + MCP CLIENT + LangGraph agent                │
│  • MultiServerMCPClient talks to BOTH servers below                 │
│  • create_react_agent(ChatGroq(...), tools) drives the conversation │
└───────────────┬───────────────────────────────────┬─────────────────┘
                │ stdio (subprocess,                │ streamable-http
                │ spawned fresh each run)            │ (persistent server,
                ▼                                    │ must already be running)
┌───────────────────────────────┐                    ▼
│ mathServer.py — "Math" server │      ┌───────────────────────────────┐
│  tools: add, multiply, amritX │      │ weather.py — "Weather" server │
└───────────────────────────────┘      │  tool: get_weather             │
                                        │  listens on 127.0.0.1:8000/mcp │
                                        └───────────────────────────────┘
```

### `mathServer.py` — stdio MCP server ("Math")

Three tools, all plain sync functions:

```python
@mcp.tool()
def add(a: int, b: int) -> int:
    """Adds two numbers together."""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiplies two numbers together."""
    return a * b % 10          # ⚠️ not a plain multiply anymore!

@mcp.tool()
def amritX(a: int, b: int) -> int:
    """
    Computes the amritX of two numbers: multiply them together and take
    the last digit (a * b mod 10). Use this whenever the user asks for
    the amritX of two numbers.
    """
    return a * b % 10
```

**Read the code, not just the name:** `multiply`'s *docstring* still says "Multiplies
two numbers together," but its *body* now returns `a * b % 10` — the exact same
formula as `amritX`. The description and the implementation have quietly drifted
apart. This is a live, in-the-repo example of the same lesson section 8 covers for
`amritX`'s old docstring: the model (and a human skimming tool lists) trusts the
description, and right now `multiply`'s description is **wrong**. Nothing crashes —
it's just silently misleading. Worth fixing before this file is used as a template
for real tools.

The server is started with `mcp.run(transport="stdio")` and runs as a **subprocess**
that `client.py` spawns — it has no independent lifetime of its own.

### `weather.py` — HTTP MCP server ("Weather")

One async tool:

```python
@mcp.tool()
async def get_weather(location: str) -> str:
    """Gets the current weather for a given location."""
    return f"The current weather in {location} is always raining. with temperature 200°C"
```

This is a **hardcoded placeholder**, not a real weather API call (the comment in the
file says as much). It runs via `mcp.run(transport="streamable-http")`, which by
default binds to `127.0.0.1:8000` and serves MCP at the `/mcp` sub-path — so the
server must be started **on its own, in a separate terminal, before** `client.py`
runs (`python3 weather.py`), and it keeps running as a persistent process across
many client requests.

### `client.py` — the LangGraph ReAct agent (host + client)

```python
client = MultiServerMCPClient({
    "math":    {"command": sys.executable, "args": ["mathServer.py"], "transport": "stdio"},
    "weather": {"url": "http://127.0.0.1:8000/mcp", "transport": "streamable_http"},
})
tools = await client.get_tools()

model = ChatGroq(model="llama-3.3-70b-versatile")
agent = create_react_agent(model, tools)
math_result = await agent.ainvoke(
    {"messages": [{"role": "user", "content":
        "what is 5 and 6 of amritX ? and what is weather in New York City?"}]}
)
print(math_result["messages"][-1].content)
```

This one file plays **three MCP roles at once**: it's the *host* (the app the user
runs), it *owns the client connections* to both servers (via `MultiServerMCPClient`),
and it's the thing that turns MCP tools into LangChain tools a LangGraph agent can
call. Note also the guard at the top of the file (`GROQ_API_KEY.startswith("gsk_")`)
that fails fast before any of this MCP machinery even starts — see lesson 4 below.

### Tracing one request end to end

Using the exact prompt hardcoded in `client.py` today:
`"what is 5 and 6 of amritX ? and what is weather in New York City?"`

1. **Startup guard.** `client.py` checks `GROQ_API_KEY` starts with `gsk_` before
   doing anything else — if not, it exits immediately with `SystemExit` (no MCP
   connection is even attempted).
2. **Spawn / connect.** `MultiServerMCPClient` spawns the math server as a
   subprocess (`sys.executable mathServer.py`, stdio) and opens an HTTP connection
   to the already-running weather server at `http://127.0.0.1:8000/mcp`.
3. **`initialize`.** Each transport does the MCP handshake — a JSON-RPC
   `initialize` request/response — before anything else is allowed.
4. **`tools/list`.** `client.get_tools()` sends a `tools/list` request to each
   server. Math replies with schemas for `add`, `multiply`, `amritX`; weather
   replies with the schema for `get_weather`. `langchain-mcp-adapters` wraps all
   four as LangChain tool objects — the LLM will only ever see each tool's *name,
   description, and JSON input schema*, never its Python source.
5. **Agent setup.** `ChatGroq(model="llama-3.3-70b-versatile")` is bound to the
   four tools inside `create_react_agent`.
6. **Invoke.** `agent.ainvoke({"messages": [...]})` starts the ReAct loop. The
   model reads the user's message plus the four tool descriptions and decides to
   call two tools: `amritX(a=5, b=6)` (the prompt explicitly says "of amritX") and
   `get_weather(location="New York City")`.
7. **`tools/call` (math).** A `CallToolRequest` for `amritX` goes over stdio to the
   math subprocess. It computes `5 * 6 % 10 = 0` and returns `0`.
8. **`tools/call` (weather).** A `CallToolRequest` for `get_weather` goes over
   HTTP to `/mcp`. It returns the hardcoded string `"The current weather in New
   York City is always raining. with temperature 200°C"`.
9. **Compose the answer.** Both tool results come back as messages in the
   LangGraph state; the model is called once more to turn them into natural
   language — roughly *"The amritX of 5 and 6 is 0. The weather in New York City
   is currently raining with a temperature of 200°C."*
10. **Print.** `math_result["messages"][-1].content` — the final assistant
    message — is printed to the terminal.

---

## 8. Debugging Lessons From Building It

Eight concrete bugs hit (and fixed) while wiring these three files together.
Each one is a small MCP/LangChain lesson in disguise.

**1. Wrong URL root for the HTTP server → `Session terminated` during `initialize`.**
`client.py` originally pointed at `http://127.0.0.1:8000` (the root). FastMCP's
`streamable-http` transport serves MCP at the **`/mcp` sub-path**, not the root, so
the very first `initialize` call failed. **Fix:** use
`http://127.0.0.1:8000/mcp`.

**2. Wrong command + wrong filename for the stdio server → subprocess launch failure.**
`client.py` originally had `command="python", args=["math.py"]`. Two problems at
once: `"python"` wasn't on `PATH` inside the venv's subprocess environment, *and*
the real file is named `mathServer.py`, not `math.py`. **Fix:**
`command=sys.executable, args=["mathServer.py"]` — `sys.executable` guarantees the
same interpreter (and venv) that's running `client.py` is used to launch the
subprocess.

**3. Passed a raw string to `agent.ainvoke()` → state-shape error.**
LangGraph's `create_react_agent` expects a **state dict** with a `messages` key,
not a bare string. **Fix:**
`{"messages": [{"role": "user", "content": "..."}]}`.

**4. `.env`'s `GROQ_API_KEY` was actually an organization ID → `401 Invalid API Key`.**
The value started with `org_` (~30 chars) — a Groq *organization* ID — instead of a
real API key, which starts with `gsk_`. **Fix:** a guard at the top of `client.py`
that raises `SystemExit` with a clear message the moment it sees a key that
doesn't start with `gsk_`, so the failure happens before any network call, not
buried inside a Groq 401.

**5. Model name decommissioned → `400 model_decommissioned`.**
`"qwen-qwq-32b"` was retired by Groq. **Fix:** queried
`https://api.groq.com/openai/v1/models` for the currently available models and
swapped to `"llama-3.3-70b-versatile"`.

**6. Incomplete tool docstring → the LLM distrusted its own correct tool result.**
`amritX`'s docstring originally trailed off mid-sentence ("amritX of two numbers is
as follow."). The model never reads a tool's Python body — only its **name,
description, and input schema** — so an incomplete description gave it nothing to
reason about even though the tool *executed correctly* and returned the right
number. The model told the user the description was incomplete rather than commit
to the (correct) answer. **Fix:** rewrite the docstring to actually explain the
computation (`a * b mod 10`), after which the model used the tool's result
confidently. This is the core MCP lesson: **the description IS the interface** —
not the code behind it.

**7. Editing the two servers behaves completely differently.**
`mathServer.py` runs over **stdio**, and `client.py` spawns a brand-new subprocess
for it on every run — so edits take effect on the very next run, no restart
needed. `weather.py` runs as a **persistent HTTP server**; editing it changes
nothing until you manually stop and restart `python3 weather.py`. Forgetting this
looks like "my fix isn't working" when really the old process is still serving
requests.

> **Bonus, still true today:** `multiply` in `mathServer.py` has the same shape of
> problem as lesson 6, just quieter — its docstring says "Multiplies two numbers
> together" but its body returns `a * b % 10`. Nothing errors, nothing looks
> broken, but the description is wrong. It's a good exercise to spot-fix before
> reusing this file as a template.

**8. The model doesn't just relay tool output verbatim — it judges it.**
After lesson 6, `weather.py`'s `get_weather` was edited to return a deliberately
implausible value (`"always raining... with temperature 200°C"`). The tool call
executed correctly and returned that exact string, but the model's final answer
*overrode* it: it told the user 200°C "is not a realistic or possible weather
condition" and suggested checking a real weather site instead of repeating the
tool's claim. The lesson runs the opposite direction from #6: there, a bad
*description* made the model distrust a *correct* result; here, a bad *value*
made the model distrust a *correct* call. Either way, **a LangChain/LangGraph
agent treats tool output as a claim it's allowed to weigh, not ground truth it
must repeat verbatim** — worth knowing if you ever need deterministic tool
output to survive unedited into the final answer (you'd need an explicit system
prompt instructing the model to trust and relay tool results as-is).

*(Related but not a bug — an easy trap when running this project):* `weather.py`
is the persistent HTTP server from lesson 7, so after editing it, the fix isn't
just "restart `client.py`" — you must also kill and restart the `python3
weather.py` process itself (e.g. find its PID with `lsof -iTCP:8000` and restart
it) before any edit to `weather.py` takes effect. A stale server process will
keep serving its old in-memory response indefinitely.

---

### Self-check — concepts (general)

1. What are the three MCP primitives, and who drives each?
2. On a stdio server, why log to stderr instead of stdout?
3. When would you pick HTTP transport over stdio?
4. What's the difference between a LangChain *chain* and an *agent*?
5. In FastMCP, how does a plain Python function become an MCP tool?
6. What's the difference between FastMCP 1.0 and 2.0, and where does each live?
7. What does `ChatGroq` give you, and what env var does it need?
8. What job does `langchain-mcp-adapters` (`MultiServerMCPClient`) do in the pipeline?
9. Trace the full path: FastMCP → ... → LLM. Name each piece.

### Self-check — this project's code

10. `multiply` in `mathServer.py` returns `a * b % 10`, not `a * b`. Why does this
    matter even though the tool "works" and nothing crashes?
11. If you run `client.py` **without** first starting `weather.py` in another
    terminal, at which numbered step in the request trace above does it fail, and
    why?
12. Why does editing `mathServer.py` never require restarting anything, while
    editing `weather.py` does?
13. What exactly did the LLM "see" about the `amritX` tool that made it distrust a
    result that was actually correct? (Hint: what does the model have access to,
    and what doesn't it have access to?)
14. Why does `client.py` check `GROQ_API_KEY.startswith("gsk_")` instead of just
    checking that the variable is non-empty — what class of bug does that catch
    that a simple emptiness check wouldn't?
15. `client.py`'s server config uses `"transport": "streamable_http"` (underscore)
    for the weather entry, while `weather.py` itself calls
    `mcp.run(transport="streamable-http")` (hyphen). Is this an inconsistency that
    needs fixing, or are both correct in their own context?
16. `get_weather` was made to return an obviously wrong value ("200°C, always
    raining"), yet the final printed answer didn't repeat it as fact. What does
    that tell you about how much an agent trusts tool output versus its own
    judgment — and how would you force it to relay a tool's result exactly as-is?
