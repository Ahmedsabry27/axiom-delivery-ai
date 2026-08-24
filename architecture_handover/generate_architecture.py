#!/usr/bin/env python3
"""Generate the repository-derived architecture handover and editable SVG diagrams."""
from __future__ import annotations

import ast
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "architecture_handover"
API = ROOT / "backend/app/api"

COLORS = {
    "frontend": "#2563eb", "api": "#0891b2", "runtime": "#7c3aed",
    "ai": "#db2777", "capability": "#d97706", "data": "#059669",
    "security": "#dc2626", "stream": "#4f46e5", "external": "#475569",
    "implemented": "#16a34a", "partial": "#ca8a04", "broken": "#dc2626",
    "placeholder": "#64748b", "legacy": "#9333ea",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def wrap(text: str, width: int = 30) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            lines.append(line); line = word
        else:
            line = f"{line} {word}".strip()
    if line: lines.append(line)
    return lines or [""]


def diagram(name: str, title: str, columns: list[tuple[str, list[tuple[str, str, str]]]], edges: list[tuple[str, str, str]], note: str = "") -> None:
    width = max(3200, 700 * len(columns)); height = max(1900, 330 + max(len(x[1]) for x in columns) * 250)
    positions = {}; parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#94a3b8"/></marker><filter id="shadow"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-opacity=".3"/></filter></defs>',
        f'<rect width="100%" height="100%" fill="#06111f"/><text x="80" y="90" fill="#f8fafc" font-family="Arial" font-size="48" font-weight="700">{esc(title)}</text>',
        f'<text x="80" y="140" fill="#94a3b8" font-family="Arial" font-size="22">ACTUAL REPOSITORY • generated {datetime.now(timezone.utc).date().isoformat()}</text>']
    col_w = (width - 160) / len(columns)
    for ci, (label, nodes) in enumerate(columns):
        x = 80 + ci * col_w
        parts.append(f'<rect x="{x}" y="180" width="{col_w-24}" height="{height-330}" rx="22" fill="#0b1b2e" stroke="#1e3a5f"/>')
        parts.append(f'<text x="{x+28}" y="225" fill="#cbd5e1" font-family="Arial" font-size="25" font-weight="700">{esc(label)}</text>')
        for ni, (node_id, label_text, kind) in enumerate(nodes):
            nx, ny, nw, nh = x + 28, 265 + ni * 230, col_w - 80, 155
            positions[node_id] = (nx, ny, nw, nh)
            color = COLORS.get(kind, COLORS["external"])
            parts.append(f'<rect x="{nx}" y="{ny}" width="{nw}" height="{nh}" rx="18" fill="#10243b" stroke="{color}" stroke-width="4" filter="url(#shadow)"/>')
            lines = wrap(label_text, max(22, int(nw/20)))
            for li, text in enumerate(lines[:4]):
                size = 25 if li == 0 else 19
                parts.append(f'<text x="{nx+24}" y="{ny+42+li*30}" fill="#f8fafc" font-family="Arial" font-size="{size}" font-weight="{700 if li==0 else 400}">{esc(text)}</text>')
            parts.append(f'<rect x="{nx+24}" y="{ny+nh-31}" width="15" height="15" rx="3" fill="{color}"/><text x="{nx+48}" y="{ny+nh-18}" fill="#94a3b8" font-family="Arial" font-size="16">{esc(kind.upper())}</text>')
    for source, target, label in edges:
        if source not in positions or target not in positions: continue
        sx, sy, sw, sh = positions[source]; tx, ty, tw, th = positions[target]
        x1, y1 = sx + sw, sy + sh/2; x2, y2 = tx, ty + th/2
        if tx < sx: x1, x2 = sx, tx + tw
        mid = (x1+x2)/2
        parts.append(f'<path d="M{x1},{y1} H{mid} V{y2} H{x2}" fill="none" stroke="#94a3b8" stroke-width="3" marker-end="url(#arrow)"/>')
        parts.append(f'<rect x="{mid-65}" y="{(y1+y2)/2-18}" width="130" height="30" rx="8" fill="#06111f"/><text x="{mid}" y="{(y1+y2)/2+4}" text-anchor="middle" fill="#cbd5e1" font-family="Arial" font-size="15">{esc(label)}</text>')
    legend_y = height - 105
    legend = [("Implemented","implemented"),("Partial","partial"),("Broken/gap","broken"),("Placeholder","placeholder"),("Legacy/unused","legacy")]
    for i,(label,kind) in enumerate(legend):
        lx=90+i*310; parts.append(f'<rect x="{lx}" y="{legend_y}" width="20" height="20" rx="4" fill="{COLORS[kind]}"/><text x="{lx+32}" y="{legend_y+18}" fill="#cbd5e1" font-family="Arial" font-size="18">{label}</text>')
    if note: parts.append(f'<text x="{width-80}" y="{height-42}" text-anchor="end" fill="#94a3b8" font-family="Arial" font-size="17">{esc(note)}</text>')
    parts.append('</svg>')
    svg = OUT / f"{name}.svg"; svg.write_text("\n".join(parts))


def parse_routes() -> list[dict]:
    routes=[]
    route_files = sorted(API.rglob("*.py")) + [ROOT / "backend/app/main.py"]
    inactive = {
        "backend/app/api/main.py",
        "backend/app/api/routers/conversations.py",
    }
    for path in route_files:
        if path.name in {"__init__.py", "dependencies.py", "sse.py"}: continue
        source=path.read_text(); tree=ast.parse(source)
        prefixes={"app": ""} if path == ROOT / "backend/app/main.py" else {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func,"id",None)=="APIRouter":
                prefix=""
                for kw in node.value.keywords:
                    if kw.arg=="prefix" and isinstance(kw.value,ast.Constant): prefix=kw.value.value
                for target in node.targets:
                    if isinstance(target,ast.Name): prefixes[target.id]=prefix
        for node in ast.walk(tree):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
            for dec in node.decorator_list:
                if not isinstance(dec,ast.Call) or not isinstance(dec.func,ast.Attribute): continue
                method=dec.func.attr.upper(); router=getattr(dec.func.value,"id","")
                if method not in {"GET","POST","PUT","PATCH","DELETE"} or router not in prefixes: continue
                route=dec.args[0].value if dec.args and isinstance(dec.args[0],ast.Constant) else ""
                response="—"
                for kw in dec.keywords:
                    if kw.arg=="response_model": response=ast.unparse(kw.value)
                body=ast.get_source_segment(source,node) or ""
                args=[]
                for arg in node.args.args:
                    ann=ast.unparse(arg.annotation) if arg.annotation else ""
                    if arg.arg not in {"db","user","request","response"}: args.append(f"{arg.arg}: {ann}".strip())
                services=sorted(set(re.findall(r"\b([a-z][a-z0-9_]*_service)\.",body)))
                tables=sorted(set(re.findall(r"(?:db\.query|db\.get)\(([A-Z][A-Za-z0-9_]*)",body)))
                relative=str(path.relative_to(ROOT))
                routes.append({"method":method,"path":prefixes[router]+route,"router":relative,"handler":node.name,"active":"Legacy / not included" if relative in inactive else "Active","auth":"Bearer/Cognito" if "get_current_user" in body or "CurrentUser" in body else "None","request":", ".join(args) or "—","response":response,"services":services or ["inline router logic"],"tables":tables or ["not statically evident"]})
    return sorted(routes,key=lambda x:(x["path"],x["method"]))


def parse_models() -> list[dict]:
    models=[]
    files=list((ROOT/"backend/app/database/models").glob("*.py"))+list((ROOT/"backend/app/models").glob("*.py"))
    for path in sorted(files):
        source=path.read_text(); tree=ast.parse(source)
        for cls in [x for x in tree.body if isinstance(x,ast.ClassDef)]:
            table=None; fields=[]
            for stmt in cls.body:
                if isinstance(stmt,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="__tablename__" for t in stmt.targets) and isinstance(stmt.value,ast.Constant): table=stmt.value.value
                if isinstance(stmt,ast.AnnAssign) and isinstance(stmt.target,ast.Name) and isinstance(stmt.value,ast.Call) and getattr(stmt.value.func,"id",None)=="mapped_column":
                    raw=ast.unparse(stmt.value); flags=[]
                    if "primary_key=True" in raw: flags.append("PK")
                    fk=re.search(r"ForeignKey\(['\"]([^'\"]+)",raw)
                    if fk: flags.append("FK→"+fk.group(1))
                    if "unique=True" in raw: flags.append("UNIQUE")
                    fields.append({"name":stmt.target.id,"type":ast.unparse(stmt.annotation).replace("Mapped[","").rstrip("]"),"flags":flags})
            if table: models.append({"table":table,"class":cls.name,"file":str(path.relative_to(ROOT)),"fields":fields})
    return sorted(models,key=lambda x:x["table"])


def create_diagrams() -> list[str]:
    specs = {
    "architecture_frontend": ("Frontend Architecture",[("Browser",[("browser","Browser + Cognito session","frontend")]),("React/Vite",[("entry","main.jsx → App → QueryProvider","frontend"),("router","createBrowserRouter + EnterpriseLayout","frontend"),("pages","Dashboard, Chat, Workflows, Agents + admin pages","implemented")]),("State/API",[("hooks","Hooks + React Query + local state","frontend"),("services","API services + auth token injection","api"),("reducer","runtime.reducer + fetch SSE parser","stream")]),("Backend",[("rest","FastAPI REST","api"),("sse","Authenticated fetch SSE","stream")])],[(("browser","entry","loads")),("entry","router","renders"),("router","pages","routes"),("pages","hooks","state"),("hooks","services","calls"),("services","rest","REST"),("services","reducer","events"),("reducer","sse","SSE")],"Theme: index.css/discovery.css; duplicate legacy src/ tree is unused"),
    "architecture_backend": ("FastAPI Backend Layers",[("API",[("middleware","CORS, TrustedHost, Logging, SecurityHeaders","security"),("routers","16 included router modules","api")]),("Application",[("services","Conversation, Runtime, Agent application/execution","runtime"),("governance","Tool governance + approvals + audit","security")]),("Runtime / AI",[("runtime","RuntimeExecutionService + legacy workflow runtime","runtime"),("agents","Managed AgentExecutionService + selection","ai"),("providers","AIProviderFactory → OpenAI / Bedrock","ai")]),("Capabilities",[("tools","Tool registry/discovery/executor + native tools","capability"),("mcp","MCP client/sync/remote tools","capability"),("actions","Action registry/executor; split persistence path","partial")]),("Persistence / External",[("db","SQLAlchemy → PostgreSQL/RDS","data"),("external","Cognito, OpenAI, Bedrock, MCP, enterprise APIs","external"),("obs","Prometheus + JSON logs + audit","implemented")])],[("middleware","routers","guards"),("routers","services","dispatch"),("services","runtime","orchestrates"),("runtime","agents","executes"),("agents","providers","SDK/API"),("runtime","tools","tool call"),("tools","mcp","adapter"),("services","db","SQL"),("providers","external","model API"),("tools","external","API")],"app/api/main.py and backend-deploy are legacy alternate entrypoints"),
    "architecture_api": ("REST API Architecture",[("Frontend consumers",[("ui","React pages/hooks/services","frontend")]),("Router groups",[("core","Auth, Chat, Conversations, Runtime, Dashboard","api"),("manage","Agents, Executions, Workflows, Actions, Knowledge, Audit","api"),("cap","Tools, Native Tools, MCP, Discovery, Governance","api")]),("Services",[("appsvc","Runtime/Agent/Conversation services","runtime"),("inline","Several admin routers contain inline DB logic","partial")]),("Data/external",[("db","Tenant-filtered SQLAlchemy","data"),("sdk","Cognito/OpenAI/Bedrock/MCP APIs","external")])],[("ui","core","REST/SSE"),("ui","manage","REST"),("ui","cap","REST"),("core","appsvc","calls"),("manage","inline","calls"),("cap","inline","calls"),("appsvc","db","SQL"),("inline","db","SQL"),("appsvc","sdk","SDK")],"Complete endpoint table is in ARCHITECTURE_HANDOVER.md"),
    "architecture_chat_runtime": ("Chat Runtime — Auto vs Explicit Agent",[("Frontend",[("chatpage","ChatPage → useChat","frontend"),("start","POST /api/chat/start","api")]),("Runtime",[("rex","RuntimeExecution (durable)","data"),("select","Explicit ID filter OR automatic lexical confidence selector","partial"),("plan","Schema-driven tool plan / managed agent path","partial")]),("Execution",[("aex","AgentExecution linked by runtime_execution_id","data"),("fallback","Default chat_service fallback when no managed agent","partial"),("cap","Authorized tools/actions + continuations","capability")]),("AI / Events",[("provider","AIProviderFactory → OpenAI/Bedrock","ai"),("events","RuntimeExecutionEvent → SSE → reducer/card","stream")])],[("chatpage","start","REST"),("start","rex","creates IDs"),("rex","select","agent_id / auto"),("select","plan","selection"),("plan","aex","managed agent"),("plan","fallback","no candidate"),("aex","cap","tool calls"),("aex","provider","model"),("fallback","provider","model"),("cap","events","persist"),("provider","events","result"),("events","chatpage","SSE")],"IDs: execution_id=RuntimeExecution; workflow_id; conversation_id; agent_execution_id via linked table"),
    "architecture_sse_events": ("Runtime SSE and Replay",[("Producer",[("service","RuntimeExecutionService.publish_event","runtime"),("bus","ExecutionTracker in-memory list/queues","stream")]),("Persistence",[("steps","runtime_executions.steps summary","data"),("eventtable","runtime_execution_events append-only sequence","data")]),("Transport",[("endpoint","GET /api/runtime/events/{id}","api"),("replay","DB replay when in-memory buffer empty; heartbeat 15s","implemented")]),("Frontend",[("fetch","Authorization-bearing fetch stream; 4 retries","stream"),("reduce","runtimeReducer → inspector/card","frontend")])],[("service","bus","publish"),("service","steps","update"),("service","eventtable","append"),("eventtable","replay","ordered replay"),("bus","endpoint","live"),("replay","endpoint","resume"),("endpoint","fetch","SSE"),("fetch","reduce","events")],"No Last-Event-ID cursor; reconnect replays only when process buffer is empty"),
    "architecture_agents": ("Managed Agent Lifecycle and Execution",[("Management",[("builder","Agent UI + /api/v1/agents","frontend"),("agent","Agent: draft/published/enabled/disabled/archived","data"),("version","Immutable AgentVersion snapshots","data")]),("Assignments",[("assign","Tool, Knowledge, Access, Execution settings","security")]),("Runtime",[("selector","Runtime lexical/capability selector","partial"),("exec","AgentExecutionService","ai"),("continuation","AgentContinuation input/clarification/approval","security")]),("Outputs",[("provider","AIProviderFactory","ai"),("tools","Tool discovery/executor","capability"),("audit","activity + audit + metrics","implemented")])],[("builder","agent","CRUD"),("agent","version","publish"),("version","assign","references"),("agent","selector","enabled+published"),("selector","exec","selected"),("exec","continuation","pause/resume"),("exec","provider","invoke"),("exec","tools","execute"),("exec","audit","record")],"Legacy in-memory default agent/registry still supports workflow runtime"),
    "architecture_ai_providers": ("AI Provider Abstraction",[("Callers",[("runtime","chat_service / AgentExecutionService","runtime")]),("Factory",[("factory","AIProviderFactory cached by provider+model","ai"),("base","AIProvider ask + stream interface","ai")]),("OpenAI",[("openai","OpenAIProvider + OpenAIAdapter","implemented"),("responses","OpenAI Responses API","external")]),("Bedrock",[("bedrock","BedrockProvider + BedrockAdapter","implemented"),("converse","Bedrock Converse / ConverseStream (Nova default)","external")]),("Cross-cutting",[("usage","usage/token/latency/error Prometheus metrics","implemented"),("errors","safe provider error mapping","implemented")])],[("runtime","factory","resolve"),("factory","base","returns"),("base","openai","branch"),("openai","responses","SDK"),("base","bedrock","branch"),("bedrock","converse","boto3"),("openai","usage","metrics"),("bedrock","usage","metrics"),("openai","errors","map"),("bedrock","errors","map")],"Configuration values are names only; secrets omitted"),
    "architecture_planner_agent_selection": ("Planner and Agent Selection",[("Goal",[("goal","User goal + identity + tenant","frontend"),("intent","Rule-based intent classification","partial")]),("Candidates",[("registry","Enabled published tenant agents + authorization","implemented"),("rank","Lexical capability/tool match + confidence threshold","partial")]),("Planning",[("default","DefaultPlanner hardcodes general-execution fallback","partial"),("discover","ToolDiscoveryEngine semantic/lexical index","implemented"),("plan","ExecutionPlan tasks","partial")]),("Execute",[("agent","Managed agent OR default fallback","runtime"),("tool","Resolved authorized tool","capability")])],[("goal","intent","classify"),("intent","registry","filter"),("registry","rank","score"),("rank","agent","select"),("goal","default","plan"),("default","discover","query"),("discover","plan","selected tool"),("plan","tool","task")],"DefaultPlanner is used by legacy runtime; chat runtime has additional inline planning"),
    "architecture_tools": ("Tools, Catalog, Discovery, and Execution",[("Catalog",[("registry","In-memory ToolRegistry loaded at import/startup","capability"),("catalog","tool_definitions + marketplace/search index","data")]),("Discovery",[("engine","ToolDiscoveryEngine: auth, governance, ranking","implemented")]),("Execution",[("executor","ToolExecutor revalidates schema/permission/policy","implemented"),("records","tool_executions + audit/metrics","data")]),("Actual tools",[("builtin","ServiceNow, local files, Azure Blob/Key Vault, report tool","implemented"),("native","file, DB, REST, notification native families","implemented"),("mcp","approved MCP remote tools","implemented")]),("External",[("systems","Configured enterprise endpoints/files/database/MCP","external")])],[("registry","catalog","sync"),("catalog","engine","index"),("engine","executor","selection"),("executor","builtin","invoke"),("executor","native","invoke"),("executor","mcp","invoke"),("executor","records","persist"),("builtin","systems","API/file"),("native","systems","bounded access"),("mcp","systems","MCP")],"Many built-ins are implemented but remain not_configured without environment credentials"),
    "architecture_actions": ("Enterprise Actions",[("Management",[("crud","/api/actions DB CRUD + UI","partial"),("dbaction","actions table stores name/type/status/permissions","data")]),("Runtime action",[("registry","In-memory ActionRegistry with deployment report example","partial"),("executor","ActionExecutor","partial")]),("Governance",[("permission","ActionPermissionValidator + approval models","partial"),("audit","Action audit service/models + general audit","partial")]),("External",[("target","Action-defined external effect","external")])],[("crud","dbaction","SQL"),("registry","executor","lookup"),("executor","permission","intended guard"),("permission","target","approved call"),("executor","audit","record")],"DB-managed actions and in-memory action contracts are separate; approval/audit path is not uniformly wired"),
    "architecture_mcp": ("Model Context Protocol Integration",[("Admin",[("ui","MCP pages + /api/v1/mcp","frontend"),("server","mcp_servers config; secret reference only","data")]),("Protocol",[("client","MCP client manager: streamable HTTP / legacy SSE","capability"),("sync","test/sync tools, resources, prompts","implemented")]),("Capabilities",[("caps","mcp_capabilities + fingerprints/review","data"),("remote","MCPRemoteTool registered only when approved/enabled","security")]),("External",[("mcpserver","Configured HTTPS MCP server","external")])],[("ui","server","CRUD"),("server","client","connect"),("client","sync","list"),("sync","caps","persist"),("caps","remote","register"),("remote","mcpserver","call/read/prompt")],"Configured does not mean active: server and capability gates both apply"),
    "architecture_discovery": ("Tool Discovery",[("Request",[("api","Discovery search/simulate endpoints","api"),("intent","Intent parser + embeddings abstraction","capability")]),("Index",[("index","tool_search_index built from registry/catalog/MCP","data")]),("Decision",[("filters","Permission, health, environment, governance filters","security"),("rank","Candidate ranking + confidence/clarification","implemented")]),("Results",[("events","discovery events, decisions, feedback","data"),("consumer","Planner/agent execution + marketplace UI","runtime")])],[("api","intent","parse"),("intent","index","search"),("index","filters","candidates"),("filters","rank","eligible"),("rank","events","persist"),("rank","consumer","selection")],"Discovery feeds tool execution; it does not ingest knowledge or create agents/actions"),
    "architecture_knowledge": ("Knowledge / RAG Status",[("Management",[("ui","Knowledge page + /api/knowledge CRUD","frontend"),("source","knowledge_sources metadata/status","data")]),("Assignment",[("assign","agent_knowledge_assignments","data")]),("Retrieval",[("retrieve","AgentExecutionService loads authorized source metadata","partial"),("prompt","Citations/metadata included in model context","partial")]),("Missing",[("ingest","No document chunk table / embedding pipeline / vector store","placeholder"),("vector","No semantic retrieval implementation","broken")])],[("ui","source","CRUD"),("source","assign","assign"),("assign","retrieve","authorize"),("retrieve","prompt","context"),("source","ingest","missing"),("ingest","vector","missing")],"This is source management plus metadata citation, not a complete RAG subsystem"),
    "architecture_governance": ("Governance, Approval, and Continuations",[("Identity",[("request","Tenant identity + scopes/groups/roles","security")]),("Policy",[("policy","Tool governance policy engine: deny > approval > allow","security"),("access","Agent/tool/action assignment checks","security")]),("Decision",[("allow","Allowed execution","implemented"),("approval","Durable runtime/agent/governance approval records","partial"),("deny","Safe denial + audit","implemented")]),("Resume",[("continue","One-time continuation validation/expiry","implemented"),("audit","AuditLog / approval history","data")])],[("request","policy","evaluate"),("request","access","authorize"),("policy","allow","allow"),("policy","approval","pause"),("policy","deny","deny"),("approval","continue","approve/resume"),("allow","audit","record"),("deny","audit","record"),("continue","audit","record")],"Multiple approval implementations exist; runtime and standalone governance APIs are not fully unified"),
    "architecture_security_auth": ("Authentication and Authorization Trust Boundaries",[("Untrusted client",[("browser","Amplify/Cognito token in browser","frontend")]),("API boundary",[("bearer","HTTP Bearer dependency","security"),("jwt","Cognito JWKS RS256 issuer/client/token_use validation","security"),("middleware","CORS, TrustedHost, security headers, request IDs","security")]),("Authorization",[("claims","sub, custom:tenant_id, groups, scopes/permissions","security"),("rbac","platform-admin mapping + capability permissions","security")]),("Data/external",[("tenant","Tenant-filtered queries (inconsistent legacy exceptions)","partial"),("cognito","Amazon Cognito JWKS","external")])],[("browser","bearer","Authorization"),("bearer","jwt","verify"),("jwt","cognito","JWKS"),("jwt","claims","claims"),("claims","rbac","authorize"),("rbac","tenant","scope SQL"),("middleware","tenant","guards")],"E2E tokens exist but are forbidden outside test/e2e/ci/local"),
    "architecture_database": ("Database Entity Relationships",[("Conversation",[("conv","conversations PK id; user/tenant/agent refs","data"),("msg","messages FK conversation_id","data"),("rex","runtime_executions + events + continuations","data")]),("Agents",[("agent","agents → versions/activity","data"),("aex","agent_executions → continuations","data"),("assign","agent tool/knowledge/access/settings assignments","data")]),("Capabilities",[("tools","tool definitions/executions/integrations/discovery/governance","data"),("mcp","MCP servers/capabilities/sync runs","data"),("native","native files/content/connections/notifications","data")]),("Platform",[("workflow","workflows/tasks","data"),("action","actions + knowledge_sources","data"),("audit","audit_logs + approvals/clarifications","data")])],[("conv","msg","1:N"),("conv","rex","1:N"),("agent","aex","1:N"),("agent","assign","1:N"),("rex","aex","runtime_execution_id"),("assign","tools","tool name"),("assign","action","knowledge FK"),("mcp","tools","registry sync"),("aex","audit","events")],"Full columns and declared foreign keys are in database_schema.md"),
    "architecture_aws": ("AWS and Deployment Evidence",[("Internet",[("user","Browser/developer","frontend"),("amplify","Amplify build config for frontend","external")]),("Application",[("fastapi","FastAPI container/Procfile; Mangum Lambda handler also present","partial")]),("AWS managed",[("cognito","Amazon Cognito","security"),("bedrock","Amazon Bedrock Runtime","ai"),("rds","PostgreSQL / Amazon RDS","data"),("secrets","Secrets Manager DATABASE_SECRET_ARN","security")]),("Observability",[("cw","CloudWatch implied by deployment docs, not provisioned here","placeholder"),("prom","Prometheus/Grafana Docker/ECS task definitions","implemented")])],[("user","amplify","HTTPS"),("amplify","fastapi","REST/SSE"),("fastapi","cognito","JWKS"),("fastapi","bedrock","boto3"),("fastapi","rds","SQL/TLS"),("fastapi","secrets","GetSecretValue"),("fastapi","prom","scrape")],"VPC, subnets, load balancer, API Gateway/Lambda deployment are NOT DEFINED IN REPOSITORY"),
    "architecture_observability": ("Observability",[("Request",[("client","Frontend request","frontend"),("mw","LoggingMiddleware request ID + duration","implemented")]),("Signals",[("logs","Structured JSON logging / safe redaction","implemented"),("metrics","Prometheus counters, histograms, DB pool/events","implemented"),("audit","Persistent audit_logs and domain events","implemented")]),("Endpoints",[("health","/health /ready /health/details","api"),("prom","/metrics","api")]),("Collectors",[("prometheus","Prometheus configs/task definition","external"),("grafana","Grafana provisioned dashboards","external"),("cloud","Central log sink not defined","placeholder")])],[("client","mw","HTTP"),("mw","logs","emit"),("mw","metrics","observe"),("mw","audit","domain"),("metrics","prom","scrape"),("prom","prometheus","scrape"),("prometheus","grafana","query"),("health","client","probe"),("logs","cloud","not wired")],"Provider, agent, discovery, tool, DB, and HTTP metrics are defined"),
    "architecture_sequence_chat": ("End-to-End Chat Sequence and Alternatives",[("Client",[("user","User / ChatPage","frontend"),("sse","runtime reducer + UI","stream")]),("API",[("chat","POST /api/chat/start","api"),("stream","GET runtime events","api")]),("Runtime",[("runtime","RuntimeExecutionService + durable row","runtime"),("select","Agent selector / planner","partial"),("agent","AgentExecutionService or default chat_service","ai")]),("Dependencies",[("tool","Tool/action + governance","capability"),("model","OpenAI or Bedrock","external"),("db","PostgreSQL","data")])],[("user","chat","1 request"),("chat","runtime","2 create"),("runtime","db","3 persist"),("runtime","select","4 select/plan"),("select","agent","5 execute"),("agent","tool","6 optional tool"),("agent","model","7 invoke"),("tool","db","audit"),("model","runtime","result/failure"),("runtime","stream","persist event"),("stream","sse","SSE"),("sse","user","render")],"Alternatives: required input/approval pause; tool/provider failure → FAILED; cancellation/timeout supported"),
    "architecture_implementation_status": ("Implementation Status Map",[("Implemented",[("green1","Conversation persistence; durable runtime events/SSE replay","implemented"),("green2","OpenAI + Bedrock providers; agent CRUD/lifecycle","implemented"),("green3","Tool SDK/catalog/discovery/MCP; audit/metrics","implemented")]),("Partial",[("yellow1","Agent selection scoring + planner are heuristic/hardcoded","partial"),("yellow2","Actions split across DB management and in-memory runtime","partial"),("yellow3","Governance/continuations have parallel implementations","partial"),("yellow4","Dashboard/admin UI functionality varies by page","partial")]),("Broken / gaps",[("red1","Knowledge has no ingestion, chunks, embeddings, vector retrieval","broken"),("red2","SSE has no Last-Event-ID cursor; multi-process live fanout absent","broken")]),("Placeholder/legacy",[("gray1","app/api/main.py, backend-deploy, root src duplicate","legacy"),("gray2","AWS networking/IaC and centralized log sink undefined","placeholder")])],[],"Status is based on current source, wiring, migrations, and frontend consumers"),
    "architecture_code_dependencies": ("Key Code Dependency Map",[("Frontend",[("page","ChatPage.jsx","frontend"),("hook","useChat.js","frontend"),("rsvc","runtime.service.ts + runtime.reducer.ts","stream")]),("API",[("chatapi","api/chat.py","api"),("runtimeapi","api/runtime.py","api")]),("Services",[("rservice","services/runtime_execution_service.py","runtime"),("aservice","agents/execution_service.py","ai"),("cservice","services/chat_service.py","runtime")]),("Capabilities",[("factory","ai/factory.py → providers","ai"),("tools","tool_discovery + tool_sdk","capability"),("models","models/runtime_execution.py + database/models/*","data")])],[("page","hook","uses"),("hook","rsvc","subscribe"),("hook","chatapi","start"),("rsvc","runtimeapi","REST/SSE"),("chatapi","rservice","calls"),("runtimeapi","rservice","controls"),("rservice","aservice","managed agent"),("rservice","cservice","fallback"),("aservice","factory","model"),("aservice","tools","tools"),("rservice","models","persist")],"See Key File Index for all major capabilities"),
    "architecture_configuration": ("Configuration Consumers (values redacted)",[("Frontend",[("vite","VITE_API_URL, VITE_COGNITO_*, VITE_AWS_REGION","frontend")]),("Core",[("app","APP_ENV, CORS_ALLOWED_ORIGINS, TRUSTED_HOSTS, API docs/schema flags","api"),("ai","AI_PROVIDER, OPENAI_MODEL/API_KEY, AWS_REGION, BEDROCK_*","ai")]),("Data/Auth",[("db","DATABASE_URL or DATABASE_SECRET_ARN + pool settings","data"),("auth","COGNITO_REGION/USER_POOL_ID/CLIENT_ID","security")]),("Capabilities",[("tools","ServiceNow, Azure, file/native DB/REST env references","capability"),("mcp","MCP limits/private-network switch + env:// secret refs","security")])],[("vite","app","REST"),("app","auth","configure"),("app","db","configure"),("app","ai","configure"),("app","tools","configure"),("app","mcp","configure")],"Secret values are intentionally omitted"),
    "architecture_master": ("Enterprise AI Copilot — Master Architecture",[("Users / Frontend",[("user","Users → React/Vite Enterprise UI","frontend"),("state","Router, React Query, hooks, runtime reducer","frontend")]),("API / Security",[("api","FastAPI routers + middleware","api"),("auth","Cognito JWT + tenant/RBAC checks","security"),("sse","REST + durable SSE endpoint","stream")]),("Runtime / AI",[("runtime","RuntimeExecutionService, context, planner, selector","runtime"),("agent","Managed agents + AgentExecutionService","ai"),("provider","AIProviderFactory → OpenAI / Bedrock","ai")]),("Enterprise capabilities",[("tools","Tool catalog/discovery/native Tool SDK","capability"),("actions","Actions + approvals (partially unified)","partial"),("mcp","MCP servers/tools/resources/prompts","capability"),("knowledge","Knowledge source metadata; RAG incomplete","partial")]),("Data / External",[("db","PostgreSQL/RDS: conversations, runtime, agents, tools, audit","data"),("gov","Policies, permissions, continuations, audit","security"),("external","Cognito, OpenAI, Bedrock, MCP/enterprise APIs","external"),("obs","Logs, Prometheus, health, Grafana","implemented")])],[("user","state","interact"),("state","api","REST"),("state","sse","SSE"),("api","auth","verify"),("api","runtime","start/control"),("runtime","agent","execute"),("agent","provider","model invocation"),("runtime","tools","tool call"),("runtime","actions","action call"),("tools","mcp","adapter"),("agent","knowledge","context"),("runtime","gov","policy"),("runtime","db","SQL"),("sse","db","events"),("provider","external","SDK/API"),("mcp","external","MCP"),("api","obs","telemetry")],"Implemented/partial/gap semantics use the legend; all boxes have repository evidence"),
    }
    # aliases/variants that share evidence but emphasize subsystem-specific details
    specs["architecture_actions"] = specs["architecture_actions"]
    names=[]
    for name,(title,cols,edges,note) in specs.items(): diagram(name,title,cols,edges,note); names.append(name)
    required={"architecture_master","architecture_frontend","architecture_backend","architecture_api","architecture_chat_runtime","architecture_sse_events","architecture_agents","architecture_ai_providers","architecture_planner_agent_selection","architecture_tools","architecture_actions","architecture_mcp","architecture_discovery","architecture_knowledge","architecture_governance","architecture_security_auth","architecture_database","architecture_aws","architecture_observability","architecture_sequence_chat","architecture_implementation_status","architecture_code_dependencies","architecture_configuration"}
    missing=required-set(names)
    if missing: raise RuntimeError(f"Missing diagram specs: {sorted(missing)}")
    # One Chromium process renders all complete wide SVG canvases. Quick Look
    # thumbnails are intentionally not used because they crop wide diagrams.
    subprocess.run(
        ["node", str(OUT / "render_architecture.mjs"), *sorted(names)],
        check=True,
    )
    return sorted(names)


def write_docs(routes: list[dict], models: list[dict], diagrams: list[str]) -> None:
    repo_files=[p for p in ROOT.rglob("*") if p.is_file() and not any(x in p.parts for x in {"node_modules",".venv","dist","build","__pycache__",".git","architecture_handover"})]
    frontend=[str(p.relative_to(ROOT)) for p in repo_files if "frontend" in p.parts and p.suffix in {".js",".jsx",".ts",".tsx"}]
    backend=[str(p.relative_to(ROOT)) for p in repo_files if "backend" in p.parts and p.suffix==".py"]
    doc = f"""# Enterprise AI Copilot — Architecture Handover

Generated: {datetime.now(timezone.utc).isoformat()}
Basis: current working tree, including uncommitted implementation. Secret values are omitted.

## 1. Executive Summary

The active product is a Vite/React single-page application backed by `backend/app/main.py`, a FastAPI service using SQLAlchemy and PostgreSQL. Cognito access tokens protect nearly every product endpoint. Chat creates a durable `RuntimeExecution`, selects a published managed agent when an explicit ID or heuristic match is available, otherwise falls back to `chat_service`, and streams append-only `RuntimeExecutionEvent` records over authenticated fetch-based SSE.

The repository has broad implemented management surfaces for agents, tools, native tools, MCP, tool discovery/governance, workflows, actions, knowledge-source metadata, audit, and dashboard metrics. Completeness is uneven. Agent management/execution, providers, tool SDK, MCP, runtime events, audit, and metrics have substantial backend implementations. Planner/agent selection remain heuristic; actions have split models/executors; governance has multiple parallel continuation/approval paths; knowledge is not full RAG. Duplicate legacy roots (`src/`, `backend/app/api/main.py`, `backend/backend-deploy/`) are not the active application.

Status vocabulary: **Implemented** = wired active path; **Partial** = real code with missing/unified behavior; **Placeholder** = interface/UI/config without complete capability; **Legacy/dead** = duplicate or not included by active entrypoint.

## 2. Repository Structure

| Area | Actual contents | Status |
|---|---|---|
| `frontend/` | Active React/Vite app, router, layouts, pages, hooks, services, stores, tests | Implemented |
| `backend/app/` | Active FastAPI app, APIs, services, runtime, agents, providers, tools, governance, persistence | Implemented |
| `backend/alembic/` | PostgreSQL schema history through runtime-agent linkage | Implemented |
| `backend/tests/` | Unit/API/migration/security/provider/runtime/tool/MCP tests | Implemented |
| `observability/`, `prometheus/`, `grafana/`, `ecs/` | Local monitoring stack and task definitions | Implemented/configuration |
| `.github/workflows/`, `amplify.yml`, Docker/Procfile | CI, frontend build, backend container/process definitions | Partial deployment definition |
| root `src/` | Older duplicate chat frontend, not used by `frontend/package.json` | Legacy/dead |
| `backend/backend-deploy/`, `backend/app/api/main.py` | Reduced/alternate backend copies, not the documented uvicorn entry | Legacy/dead |

Inventory counts (excluding dependencies/build/cache): {len(frontend)} frontend source files, {len(backend)} backend Python files, {len(routes)} API operations, {len(models)} mapped tables.

## 3. Frontend Architecture

`frontend/src/main.jsx` mounts the app, Amplify configuration, global CSS and `QueryProvider`. `frontend/src/App.jsx` handles authentication and renders the `RouterProvider`. `app/router.jsx` lazy-loads pages beneath `EnterpriseLayout`; `Sidebar` supplies product navigation. React Query owns server cache; page-local hooks/state manage UI; runtime events use a reducer. No separate global Redux store exists; Zustand-style files exist for chat/conversation/UI but the active Chat page primarily uses hooks and reducer state.

Major pages and wiring:

| Page | Component | Backend/API | Status |
|---|---|---|---|
| Dashboard | `pages/dashboard/DashboardPage.jsx` | `/api/dashboard/*` | Implemented |
| Chat | `pages/ChatPage.jsx` + chat components | conversations, `/api/chat/start`, `/api/runtime/*` | Implemented, runtime details partial |
| Workflows | `pages/workflows/*` | `/api/workflows`, `/api/workflows/run` | Implemented |
| Agents | `pages/agents/*`, builder/test console | `/api/v1/agents/*` | Implemented |
| Actions | `pages/actions/ActionsPage.jsx` | `/api/actions*` | Partial split runtime |
| Tool Catalog / Integrations / Executions | `pages/tools/*` | `/api/v1/tools*`, integrations, executions | Implemented |
| Native Tools | `pages/native/*` | `/api/v1/native-tools`, files/connections/notifications | Implemented |
| MCP Servers | `pages/mcp/*` | `/api/v1/mcp/*` | Implemented/configuration dependent |
| Discovery / Marketplace / Governance / Analytics | `pages/discovery/*` via `AdminPages.jsx` | `/api/v1/tool-*` | Implemented |
| Knowledge | `pages/knowledge/KnowledgePage.jsx` | `/api/knowledge` | Partial: metadata CRUD only |
| Audit | `pages/audit/AuditPage.jsx` | `/api/audit*` | Implemented |
| Settings | `pages/settings/SettingsPage.jsx` | mostly UI/config view | Partial |

Authentication uses Amplify/Cognito; API services call `getAccessToken()` and send Bearer tokens. `runtime.service.ts` deliberately uses `fetch` rather than `EventSource` so the Authorization header is preserved. Theme is a dark enterprise design in `index.css`, `discovery.css`, and layout/component utility classes.

## 4. Backend Architecture

`backend/app/main.py` is the active entry. Lifespan validates the environment, optionally creates development schema, checks DB connectivity/migration head, optionally syncs/indexes tools, loads approved MCP tools, and registers DB metrics. Middleware: CORS, optional TrustedHost, request logging, security headers. Health/readiness/metrics endpoints and a Mangum Lambda handler are present.

The backend is layered but not strictly isolated: routers frequently query SQLAlchemy directly; application services cover conversations/runtime/agents; reusable legacy workflow runtime classes coexist with the chat-specific `RuntimeExecutionService`; tools and MCP use registries plus persisted catalogs.

## 5. API Catalog

All product routes below were extracted from decorators. `not statically evident` means the handler delegates or uses repository helpers; it does not mean no persistence.

| Method | Path | Handler / router | Wiring | Auth | Request model/args | Response | Service | Direct table classes |
|---|---|---|---|---|---|---|---|---|
"""
    for r in routes:
        vals=[r["method"],f'`{r["path"]}`',f'`{r["handler"]}` / `{r["router"]}`',r["active"],r["auth"],r["request"].replace("|","/"),r["response"].replace("|","/"),", ".join(r["services"]),", ".join(r["tables"])]
        doc += "| " + " | ".join(vals) + " |\n"
    doc += """

## 6. Chat Runtime

1. `ChatPage` loads/creates a conversation and calls `useChat.handleStream`.
2. Frontend posts `/api/chat/start` with `conversation_id`, message and optional agent/provider/model/workspace.
3. API verifies conversation ownership and derives permissions/tenant from Cognito claims.
4. `RuntimeExecutionService.start` selects an enabled published tenant agent (explicit match or heuristic confidence), resolves provider/model, persists `RuntimeExecution` and user message, writes audit, and launches an asyncio task.
5. Managed selection calls `AgentExecutionService` with `runtime_execution_id`; otherwise the default chat/provider path executes. Tool schema can produce required-input fields; approval gates produce durable continuations.
6. Every published event updates the runtime summary, appends `RuntimeExecutionEvent`, and enters an in-process tracker. SSE replays persisted events when needed, then tails the tracker.
7. The reducer merges steps/tools/actions/logs/metrics and renders `RuntimeExecutionCard`/`ExecutionInspector` plus continuation UI.

`RuntimeExecution.id` is the UI/SSE execution ID. `workflow_id` is a runtime correlation ID. `conversation_id` links messages/context. `AgentExecution.id` is distinct and is linked through `AgentExecution.runtime_execution_id` (string without a declared FK).

## 7. Runtime State Machine

Declared runtime transitions: `PENDING → RUNNING|CANCELLED`; `RUNNING → WAITING_FOR_INPUT|WAITING_FOR_APPROVAL|COMPLETED|FAILED|CANCELLED|TIMED_OUT`; waiting states may resume to `RUNNING` or terminate. All requested states exist in service logic. Agent execution additionally supports `waiting_for_clarification`, `expired`, queued/running/succeeded/failed/cancelled/timed_out. State naming/casing differs between the two execution systems.

## 8. Agent Architecture

Managed agents are tenant-scoped rows with lifecycle/health, mutable draft configuration and immutable published `AgentVersion` snapshots. Publishing, enabling, disabling, archiving/restoring, assignments, version history, activity, analytics and test execution have APIs/UI. `AgentApplicationService` resolves identity/access and published runtime configuration. `AgentExecutionService` is the canonical persisted-agent entry point, records model/planner/tool/knowledge metadata and supports durable continuations with hashed one-time resume tokens.

Separately, `runtime/agent_registry.py`, `agents/default_agent.py`, and older agent models support the reusable workflow runtime. This in-memory/default agent mechanism is real but distinct from managed database agents.

## 9. Planner

`DefaultPlanner` implements the planner contract but still defaults to `required_capabilities = ["general-execution"]`, creates one “Echo Goal” task, and only replaces the capability when tool discovery selects a tool. Chat runtime also performs inline intent classification, agent ranking, tool matching and plan event construction. Managed agent execution accepts planner names `default`, `react`, and `sequential`, but the provider call path is not a full autonomous ReAct engine. Status: **partial/hardcoded**.

## 10. AI Provider Architecture

`AIProviderFactory` caches provider objects by provider/model. OpenAI uses the Responses API (`responses.create`, including stream events); Bedrock uses boto3 Bedrock Runtime `converse`/`converse_stream`, with regional Nova inference-profile resolution. Adapters translate provider-neutral messages. Both collect latency/token/error metrics and map provider failures to safe domain errors. Provider-level streaming exists; the current durable chat path primarily emits orchestration/result events rather than token deltas.

## 11. Tool Architecture

`ToolRegistry` is populated with built-in plus native tools at import, optionally synced to `tool_definitions` and indexed at startup, and augmented by approved MCP tools. `ToolDiscoveryEngine` filters by identity, permissions, environment, health and governance, then ranks indexed candidates. `ToolExecutor` validates schema, permissions, enablement and policy again before execution and persists execution/audit/metrics.

Actually implemented families include ServiceNow incident/change/asset reads; bounded local file operations; Azure Blob reads/listing; Azure Key Vault reads; report-generation support; native file upload/extract/search/summarize; read-only database query; governed REST request; notification/email approval flow; and approved MCP remote tools. Most external adapters require environment configuration and surface `not_configured` until present.

## 12. Action Architecture

There are two action representations: a simple `actions` management table/API/UI and contract-based in-memory actions (`ActionRegistry`, example deployment-report action, `ActionExecutor`, permission/audit helper models). The runtime registers the report action directly. Retry/risk/approval/audit abstractions exist, but the DB-managed action rows are not uniformly executable through the same governed registry. Status: **partially implemented / not unified**.

## 13. MCP Architecture

MCP server configuration, health testing, sync runs, tool/resource/prompt operations, OAuth start/callback, schema fingerprinting, capability approval and tool registry integration are implemented. Supported transports are streamable HTTP and legacy SSE. SSRF/TLS/host/size controls and environment-secret references are present. A configured server is not active until enabled; a remote tool additionally must be approved, enabled, present and not awaiting schema review.

## 14. Discovery Architecture

Discovery indexes registered tools, parses intent, performs authorization/governance filters, ranks candidates, returns selected/clarification/no-match outcomes, and persists discovery events, candidate decisions and feedback. Marketplace and analytics APIs consume these records. It feeds tool selection. It does **not** currently discover knowledge documents, synthesize actions, or create agents.

## 15. Knowledge Architecture

The system persists knowledge-source metadata and agent assignments. Managed agent execution loads authorized source records and can add citation/source metadata to context and runtime events. No document/chunk model, ingestion worker, embedding persistence, vector index, or semantic retriever is implemented. The “Upload source” UI creates metadata; it does not upload file content. Status: **partial; not full RAG**.

## 16. Governance

Tool governance policies support draft/version/publish/test/evaluate and decisions allow, approval-required, deny. Execution rechecks authorization and policy. Agent access assignments grant view/edit/execute/test and identity groups/roles/scopes contribute platform permissions. Durable approval/clarification APIs and both runtime/agent continuation tables exist. Because standalone governance workflows, runtime continuations, agent continuations, native notification approvals, and older approval classes coexist, approval orchestration is **implemented in parts but not one unified state machine**.

## 17. Authentication / Authorization

Cognito access tokens are verified against cached JWKS (RS256, issuer, `token_use=access`, client ID). Claims supply `sub`, `custom:tenant_id`, groups and scopes/permissions. Platform-admin groups add administrative tool permission; agent authorization also evaluates assignments. Most modern queries filter tenant. Risks: legacy workflow/conversation code contains default-tenant paths, authorization is convention/service based rather than database row-level security, and JWKS retrieval is synchronous within token verification. E2E token support is gated to isolated environments.

## 18. Data Architecture

PostgreSQL is the production target; SQLAlchemy/Alembic own schema. UUID/string identity styles and UTC handling vary by generation. Runtime events are append-only with unique `(execution_id, sequence)`, but sequence allocation uses count+1 and can race under concurrent writers. Some conceptual links (`runtime_execution_id`, conversation IDs in agent execution) are strings without declared foreign keys. See `database_schema.md`.

## 19. AWS Architecture

Repository evidence directly supports Cognito, Bedrock Runtime, RDS/PostgreSQL and Secrets Manager. Amplify build configuration exists. FastAPI includes a Mangum handler, but API Gateway/Lambda infrastructure is not defined. Docker/Procfile and ECS Prometheus/Grafana task definitions also exist, producing multiple deployment possibilities. VPC, subnets, security groups, load balancer, ECS application task/service and CloudWatch log wiring are **not defined in repository**.

## 20. Event Streaming

Event types produced include `step`, `completed`, `error`, `required_input`, `approval_required`, `tool_started|completed|failed`, `action_started|completed|failed`, `metric`, `log`, `knowledge_retrieval_completed`, plus heartbeat comments. Runtime workflow bus events are translated into steps. Events are both in-memory and database-persisted. Reconnect retries up to four times; persisted ordered replay occurs when the process tracker lacks events. There is no `Last-Event-ID`/sequence request cursor and no cross-process pub/sub, so horizontal live streaming is a risk.

## 21. Observability

Request logging attaches request IDs and duration; security-sensitive values are sanitized/redacted. Prometheus metrics cover HTTP/provider/token/error/latency, agents, tools/discovery and DB pool/query behavior. `/health`, `/ready`, `/health/details`, `/metrics` exist. Prometheus/Grafana configs and dashboards exist. Persistent audit logs cover runtime/agent/tool/governance operations. A centralized production log backend/alerting/IaC is not defined.

## 22. Configuration

Important settings (values omitted): `APP_ENV`, `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_INFERENCE_PROFILE_ID`, `BEDROCK_MAX_TOKENS`, `BEDROCK_TEMPERATURE`, `BEDROCK_TOP_P`, `AUTO_AGENT_MIN_CONFIDENCE`, `DATABASE_URL`, `DATABASE_SECRET_ARN`, `DATABASE_HOST/PORT/NAME`, DB pool controls, `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`, `RUN_SCHEMA_CREATE`, `SYNC_TOOL_CATALOG_ON_STARTUP`, `ENABLE_API_DOCS`, frontend `VITE_API_URL` and `VITE_COGNITO_*`. Capability adapters additionally consume ServiceNow/Azure/file/native/MCP environment settings. Secret values must remain in secret stores or environment injection.

## 23. Deployment

Frontend: Vite build under `frontend/`, with Amplify config and static security headers. Backend: Dockerfile/Procfile run FastAPI/uvicorn; production startup requires current migrations and secure settings. `docker-compose.yml` and observability compose support local operation. The presence of Mangum and ECS monitoring files does not establish a single production topology. Deployment dependencies include PostgreSQL, Cognito JWKS reachability, configured model provider credentials/IAM, and any selected enterprise adapters.

## 24. Known Technical Debt

- Duplicate frontend/backend roots and overlapping API/service generations.
- Runtime planning/selection logic is spread across `RuntimeExecutionService`, `DefaultPlanner`, workflow runtime and `AgentExecutionService`.
- Runtime and agent statuses/continuations use different casing and models.
- Route handlers frequently contain persistence/business logic.
- String-only conceptual relationships lack foreign keys.
- Event sequence count+1 is not concurrency-safe.
- Provider/model selection behavior differs between managed agent and fallback paths.
- Minified/one-line frontend modules reduce maintainability.

## 25. Partially Implemented Components

Planner/agent selection, action unification, knowledge/RAG, unified governance/approval, multi-process SSE, Settings, AWS infrastructure definition, deployment topology, and some legacy workflow integration.

## 26. Known Broken Flows

- Knowledge “upload” cannot ingest/retrieve document content.
- Live SSE across multiple backend processes has no shared broker.
- Last-event cursor replay is absent and reconnect may duplicate events depending on process state.
- DB-managed arbitrary action execution is not the same path as registered action contracts.
- Selecting configured agent-builder defaults (`provider=configured`, `model=model-a`) can publish unusable runtime model configuration unless replaced with a real provider/model.
- Root legacy `src/` changes do not affect the active `frontend/` build.

## 27. Architecture Risks

Highest risks are execution-path duplication, authorization drift between generations, multi-process event delivery, incomplete RAG expectations, external adapter secret/config sprawl, and deployment ambiguity. The database contains tenant IDs but enforcement relies on application filters. Long-running work uses in-process asyncio tasks and is not durable across process restart.

## 28. Recommended Next Development Steps

1. Make `RuntimeExecutionService` the thin durable shell around one canonical planner/selector and `AgentExecutionService`; define one status/continuation contract.
2. Replace in-process task/tracker fanout with a durable job runner and Redis/Postgres pub-sub or equivalent; add cursor-based SSE replay.
3. Unify DB actions with governed action contracts/executor and approval/audit.
4. Implement real knowledge ingestion/chunking/embedding/vector retrieval, or relabel the UI as source metadata management.
5. Consolidate duplicate roots/entrypoints after proving they are unused.
6. Add explicit infrastructure-as-code and a single documented deployment topology/security boundary.
7. Add database constraints/RLS or a centralized tenant-scoped repository layer.

## 29. Key File Index

| Capability | Frontend | Backend | Persistence | API |
|---|---|---|---|---|
| Chat/runtime | `ChatPage.jsx`, `useChat.js`, `runtime.service.ts`, reducer/cards | `api/chat.py`, `api/runtime.py`, `runtime_execution_service.py` | conversations/messages/runtime executions/events/continuations | `/api/chat/start`, `/api/runtime/*` |
| Agents | agents pages/components/service | `api/agents_v1.py`, `agents/application_service.py`, `agents/execution_service.py` | agents, versions, activity, assignments, executions, continuations | `/api/v1/agents/*` |
| Providers | Chat header selection | `ai/factory.py`, providers/adapters, core clients | execution provider/model/usage fields | through chat/agent execution |
| Tools/discovery | tools/native/discovery pages/services | `api/tools.py`, `api/native_tools.py`, `api/tool_discovery.py`, `tool_sdk/*`, `tool_discovery/*` | tool definitions/executions/index/marketplace/policies/events | `/api/v1/tools*`, `/api/v1/native-*`, `/api/v1/tool-*` |
| Actions | Actions page/service | `api/management.py`, `actions/*`, runtime registration | actions; audit logs | `/api/actions*` |
| MCP | MCP pages/service | `api/mcp.py`, `mcp_integration/*` | MCP servers/capabilities/sync runs | `/api/v1/mcp/*` |
| Knowledge | Knowledge page/service | management API, agent execution retrieval | knowledge_sources, agent_knowledge_assignments | `/api/knowledge*` |
| Governance | Governance page/service, continuation UI | tool governance, governance workflows, approval modules | policies, approval/clarification requests, continuations | `/api/v1/tool-governance/*`, approvals/clarifications |
| Auth/security | `useAuth`, Amplify config, auth services | `auth/*`, middleware, sanitization/headers | claim references, tenant columns | Bearer dependency; `/api/auth/me` |
| Dashboard/ops | Dashboard page/hooks/components | dashboard/operations routers | aggregate runtime/workflow/agent tables | `/api/dashboard/*`, `/api/executions/recent` |
| Audit/metrics | Audit page | audit services/events, metrics/logging | audit_logs | `/api/audit*`, `/metrics` |

## 30. Diagram Index

"""
    for name in diagrams: doc += f"- `{name}.png` — editable source `{name}.svg`\n"
    doc += """

## Current Chat Implementation Status

| Capability | Status | Evidence / limitation |
|---|---|---|
| Conversation persistence/titles | Implemented | Conversation/messages tables and services; title utility/backend updates |
| Agent selector / automatic selection | Partial | Enabled published tenant agents; explicit authorization; heuristic lexical confidence |
| Provider/model resolution | Implemented | request/default/managed-version resolution; paths differ |
| Planner | Partial | inline runtime planning plus hardcoded DefaultPlanner fallback |
| Tool execution | Implemented | discovery, schema, permissions, governance, persisted execution |
| Action execution | Partial | registered report action works; action systems not unified |
| Required-input detection / WAITING_FOR_INPUT | Implemented | selected tool JSON schema → durable continuation |
| Continuation | Implemented | validation, expiry, one-use semantics; parallel runtime/agent models |
| Approval | Partial | durable gates/APIs exist; multiple approval systems |
| SSE | Implemented | authenticated fetch stream, DB append/replay, heartbeat |
| SSE persistence | Implemented | `runtime_execution_events` |
| SSE reconnect | Partial | four retries, no cursor/Last-Event-ID, no shared live broker |
| RuntimeExecution/AgentExecution link | Implemented without FK | `runtime_execution_id` string and migration |
| Bedrock/OpenAI | Implemented | Converse/Responses, streaming/provider metrics |
| Runtime duration/failure | Implemented | duration/error/status fields and terminal events |
| Chat layout/runtime inspector | Implemented | three-pane page and inspector/cards |
| Audit/metrics | Implemented | runtime/agent/tool audit and Prometheus; production sinks undefined |
"""
    (OUT/"ARCHITECTURE_HANDOVER.md").write_text(doc)

    schema="# Database Schema\n\nGenerated from current SQLAlchemy mapped models. Types reflect Python annotations; declared relationships are identified from `ForeignKey`.\n\n"
    for model in models:
        schema += f"## `{model['table']}` — `{model['class']}`\n\nSource: `{model['file']}`\n\n| Column | Type | Constraints/reference |\n|---|---|---|\n"
        for f in model["fields"]: schema += f"| `{f['name']}` | `{f['type']}` | {', '.join(f['flags']) or '—'} |\n"
        schema += "\n"
    (OUT/"database_schema.md").write_text(schema)

    gaps=["Knowledge lacks ingestion/chunks/embeddings/vector retrieval","SSE lacks cursor and cross-process live fanout","Action persistence and contract executor are not unified","AWS application networking/IaC is not defined","Duplicate legacy source/entrypoint trees remain"]
    manifest={"generated_at":datetime.now(timezone.utc).isoformat(),"repository":"enterprise-ai-copilot","diagrams":[{"png":f"{x}.png","source":f"{x}.svg"} for x in diagrams],"critical_frontend_files":["frontend/src/main.jsx","frontend/src/App.jsx","frontend/src/app/router.jsx","frontend/src/pages/ChatPage.jsx","frontend/src/hooks/useChat.js","frontend/src/services/runtime.service.ts","frontend/src/store/runtime.reducer.ts"],"critical_backend_files":["backend/app/main.py","backend/app/api/chat.py","backend/app/api/runtime.py","backend/app/services/runtime_execution_service.py","backend/app/agents/execution_service.py","backend/app/ai/factory.py","backend/app/tool_discovery/engine.py","backend/app/tool_sdk/executor.py"],"critical_database_models":[m["table"] for m in models],"api_groups":sorted(set(Path(r["router"]).stem for r in routes)),"known_gaps":gaps,"known_broken_flows":["Knowledge upload creates metadata only","Live SSE is process-local after replay","DB action execution is separate from ActionRegistry"],"partially_implemented":["planner","automatic agent selection","actions","unified approvals","knowledge/RAG","multi-process SSE","AWS deployment topology"]}
    (OUT/"architecture_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    routes=parse_routes(); models=parse_models(); diagrams=create_diagrams(); write_docs(routes,models,diagrams)
    print(json.dumps({"routes":len(routes),"tables":len(models),"diagrams":len(diagrams)}))


if __name__ == "__main__": main()
