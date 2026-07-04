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

---

### Self-check (cover the answers and recall)

1. What are the three MCP primitives, and who drives each?
2. On a stdio server, why log to stderr instead of stdout?
3. When would you pick HTTP transport over stdio?
4. What's the difference between a LangChain *chain* and an *agent*?
5. In FastMCP, how does a plain Python function become an MCP tool?
6. What's the difference between FastMCP 1.0 and 2.0, and where does each live?
7. What does `ChatGroq` give you, and what env var does it need?
8. What job does `langchain-mcp-adapters` (`MultiServerMCPClient`) do in the pipeline?
9. Trace the full path: FastMCP → ... → LLM. Name each piece.
