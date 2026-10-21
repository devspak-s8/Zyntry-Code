// Zyntry Code — VS Code extension.
//
// The missing half of the product: create/approve/run/stream tasks against the
// backend, ingest the current workspace as a repo snapshot, and serve as the
// *local* execution runner (fs + child_process in your workspace folder).
//
// Plain JS only: Node's built-in fetch, fs, path, child_process. No dependencies.

"use strict";

const vscode = require("vscode");
const fs = require("fs");
const fsp = require("fs/promises");
const path = require("path");
const { exec, execFile } = require("child_process");
const http = require("http");

let output; // vscode.OutputChannel
let lastTaskId = null;
let runnerTimer = null;
let runnerRunning = false;
const RUNNER_ID = `vscode-${Math.random().toString(36).slice(2, 10)}`;
const workspaceTokens = new Map(); // workspaceId -> runner token

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function log(...args) {
  const line = args.map((a) => (typeof a === "string" ? a : JSON.stringify(a))).join(" ");
  output.appendLine(`[${new Date().toISOString()}] ${line}`);
}

function config() {
  return vscode.workspace.getConfiguration("zyntry");
}

function baseUrl() {
  return String(config().get("backendUrl", "https://code-api.zyntry.space")).replace(/\/+$/, "");
}

async function api(method, p, body, headers = {}) {
  const h = { "Content-Type": "application/json", ...headers };
  const resp = await fetch(`${baseUrl()}${p}`, {
    method,
    headers: h,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await resp.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!resp.ok) {
    const err = new Error(`HTTP ${resp.status}: ${data.detail || text || resp.statusText}`);
    err.status = resp.status;
    throw err;
  }
  return data;
}

async function pickTaskId() {
  if (lastTaskId) return lastTaskId;
  const id = await vscode.window.showInputBox({ prompt: "Task id" });
  return id || undefined;
}

function summarizePlan(result) {
  const plan = result.plan || {};
  const stages = plan.stages || [];
  return [
    `task ${result.task.id} — status ${result.task.status}`,
    `plan "${plan.summary}" (${stages.length} stages, source=${plan.source})`,
    ...stages.map((s, i) => `  ${i + 1}. [${s.kind}] ${s.title}`),
  ].join("\n");
}

// ---------------------------------------------------------------------------
// task commands
// ---------------------------------------------------------------------------

async function createTask() {
  const prompt = await vscode.window.showInputBox({
    prompt: "Describe the engineering task",
    placeHolder: "Add role-based permissions to the admin API",
  });
  if (!prompt) return;

  try {
    const result = await api("POST", "/tasks", { prompt });
    lastTaskId = result.task.id;
    log("task created:", result.task.id, result.plan.summary);
    output.appendLine(summarizePlan(result));
    output.show();

    const requiresApproval = result.requires_approval;
    if (requiresApproval) {
      log("high-risk task: awaiting approval");
      const action = await vscode.window.showInformationMessage(
        `Task ${result.task.id} requires approval (risk ${result.assessment.risk_level}).`,
        "Approve & run",
        "Just approve",
        "Not now",
      );
      if (action === "Approve & run" || action === "Just approve") {
        await api("POST", `/tasks/${result.task.id}/approve`, {
          approved: true,
          auto_execute: action === "Approve & run",
        });
        log(action === "Approve & run" ? "approved + execution started" : "approved");
      }
    } else {
      const action = await vscode.window.showInformationMessage(
        `Task ${result.task.id} planned (${result.plan.stages.length} stages).`,
        "Run now",
        "Stream",
        "Not now",
      );
      if (action === "Run now") await runTask();
      if (action === "Stream") await streamTask();
    }
  } catch (err) {
    vscode.window.showErrorMessage(`Zyntry: create task failed: ${err.message}`);
  }
}

async function approveTask() {
  const id = await pickTaskId();
  if (!id) return;
  const choice = await vscode.window.showQuickPick(
    [
      { label: "Approve", detail: "Mark planned; do not execute" },
      { label: "Approve & run", detail: "Mark planned and execute immediately" },
      { label: "Reject", detail: "Cancel the task" },
    ],
    { placeHolder: "Decision for this task" },
  );
  if (!choice) return;
  try {
    const approved = choice.label !== "Reject";
    const result = await api("POST", `/tasks/${id}/approve`, {
      approved,
      auto_execute: choice.label === "Approve & run",
    });
    log("approve:", JSON.stringify(result));
    output.show();
  } catch (err) {
    vscode.window.showErrorMessage(`Zyntry: approve failed: ${err.message}`);
  }
}

async function runTask() {
  const id = await pickTaskId();
  if (!id) return;
  output.show();
  log(`executing task ${id} (sync)…`);
  try {
    const summary = await api("POST", `/tasks/${id}/execute`);
    output.appendLine(JSON.stringify(summary, null, 2));
    const status = summary.task?.status || summary.execution?.status;
    vscode.window.showInformationMessage(`Zyntry: execution ${status}`);
  } catch (err) {
    vscode.window.showErrorMessage(`Zyntry: execution failed: ${err.message}`);
  }
}

async function streamTask() {
  const id = await pickTaskId();
  if (!id) return;
  output.show();
  log(`streaming execution of task ${id}…`);
  const resp = await fetch(`${baseUrl()}/tasks/${id}/execute/stream`, {
    method: "POST",
  });
  if (!resp.ok) {
    vscode.window.showErrorMessage(`Zyntry: stream failed: HTTP ${resp.status}`);
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // Simple SSE framing: frames end with a blank line.
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        let event;
        try {
          event = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }
        log(`stream: ${event.type} — ${event.message || ""}`);
        if (event.type === "done") {
          output.appendLine(JSON.stringify(event.summary, null, 2));
          vscode.window.showInformationMessage(
            `Zyntry: execution ${event.summary?.task?.status || "finished"}`,
          );
          return;
        }
        if (event.type === "error") {
          vscode.window.showErrorMessage(`Zyntry: ${event.detail}`);
          return;
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// repo ingestion
// ---------------------------------------------------------------------------

async function ingestRepo() {
  const id = await pickTaskId();
  if (!id) return;
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    vscode.window.showErrorMessage("Zyntry: open a folder first");
    return;
  }
  const root = folders[0].uri.fsPath;
  const maxFiles = Number(config().get("runnerMaxFiles", 200));
  const skipDirs = new Set(["node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".next"]);
  const skipExt = new Set([".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".woff", ".woff2", ".ttf", ".map"]);

  const files = [];
  async function walk(dir) {
    if (files.length >= maxFiles) return;
    let entries;
    try {
      entries = await fsp.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (files.length >= maxFiles) return;
      if (entry.isDirectory()) {
        if (skipDirs.has(entry.name)) continue;
        await walk(path.join(dir, entry.name));
        continue;
      }
      const full = path.join(dir, entry.name);
      if (skipExt.has(path.extname(entry.name).toLowerCase())) continue;
      let size = 0;
      try {
        size = (await fsp.stat(full)).size;
      } catch {
        continue;
      }
      if (size > 200_000) continue; // skip huge files
      try {
        const content = await fsp.readFile(full, "utf8");
        files.push({ path: path.relative(root, full).replace(/\\/g, "/"), language: langFor(entry.name), size, content });
      } catch {
        // binary or unreadable — skip
      }
    }
  }
  await walk(root);

  try {
    const result = await api("POST", `/tasks/${id}/repo`, { files });
    log(`ingested ${result.files_ingested} file(s) into task ${id}`);
    vscode.window.showInformationMessage(`Zyntry: ingested ${result.files_ingested} files`);
  } catch (err) {
    vscode.window.showErrorMessage(`Zyntry: ingest failed: ${err.message}`);
  }
}

function langFor(name) {
  const ext = path.extname(name).slice(1).toLowerCase();
  return {
    js: "javascript", ts: "typescript", tsx: "typescript", jsx: "javascript",
    py: "python", rs: "rust", go: "go", java: "java", rb: "ruby", php: "php",
    cs: "csharp", c: "c", cpp: "cpp", h: "c", html: "html", css: "css",
    scss: "scss", json: "json", yml: "yaml", yaml: "yaml", toml: "toml",
    md: "markdown", sql: "sql", sh: "shell",
  }[ext] || "text";
}

// ---------------------------------------------------------------------------
// local runner (provider=local workspaces)
// ---------------------------------------------------------------------------

async function createWorkspace() {
  const repoUrl = await vscode.window.showInputBox({
    prompt: "Repo URL (optional; local runner works in the open folder regardless)",
  });
  try {
    const ws = await api("POST", "/workspaces", { provider: "local", repo_url: repoUrl || undefined });
    if (ws.runner_token) workspaceTokens.set(ws.id, ws.runner_token);
    log("workspace created:", ws.id, "provider=local");
    output.appendLine(`runner token for ${ws.id}: ${ws.runner_token} (shown once)`);
    output.show();
  } catch (err) {
    vscode.window.showErrorMessage(`Zyntry: create workspace failed: ${err.message}`);
  }
}

function startLocalRunner() {
  if (runnerRunning) {
    vscode.window.showInformationMessage("Zyntry: local runner already running");
    return;
  }
  runnerRunning = true;
  log(`local runner started (id ${RUNNER_ID})`);
  vscode.window.setStatusBarMessage("Zyntry local runner: running");
  runnerTimer = setInterval(pollWorkspaces, Number(config().get("runnerPollSeconds", 3)) * 1000);
  pollWorkspaces();
}

function stopLocalRunner() {
  runnerRunning = false;
  if (runnerTimer) clearInterval(runnerTimer);
  runnerTimer = null;
  log("local runner stopped");
  vscode.window.setStatusBarMessage("Zyntry local runner: stopped");
}

async function pollWorkspaces() {
  if (!runnerRunning) return;
  let workspaces;
  try {
    const data = await api("GET", "/workspaces?pending=true&provider=local");
    workspaces = data.workspaces || [];
  } catch (err) {
    log("runner poll failed:", err.message);
    return;
  }
  for (const ws of workspaces) {
    if (!runnerRunning) return;
    if (ws.runner_id && ws.runner_id !== RUNNER_ID) continue;
    try {
      await serveWorkspace(ws);
    } catch (err) {
      log(`workspace ${ws.id} error:`, err.message);
    }
  }
}

async function serveWorkspace(ws) {
  const token = workspaceTokens.get(ws.id);
  if (!token) {
    log(`workspace ${ws.id}: no runner token known (create it from this extension or set it manually) — skipping`);
    return;
  }
  for (let i = 0; i < 50 && runnerRunning; i++) {
    const data = await api("GET", `/workspaces/${ws.id}/tool-requests/next`, undefined, {
      "x-workspace-token": token,
      "x-runner-id": RUNNER_ID,
    });
    const req = data.tool_request;
    if (!req) return;
    log(`executing ${req.tool} for workspace ${ws.id}`);
    const { status, result } = await executeTool(req, ws);
    await api("POST", `/workspaces/${ws.id}/tool-requests/${req.id}/result`, { status, result }, {
      "x-workspace-token": token,
    });
  }
}

function redact(text, ws) {
  const secrets = Object.values((ws && ws.env) || {}).filter((v) => v);
  let out = text;
  for (const s of secrets) out = out.split(s).join("[REDACTED]");
  return out;
}

function workspaceRoot() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : process.cwd();
}

function confine(root, relPath) {
  const p = path.resolve(root, relPath);
  if (p !== root && !p.startsWith(root + path.sep)) throw new Error("path outside workspace");
  return p;
}

async function executeTool(req, ws) {
  const params = req.params || {};
  const root = workspaceRoot();
  const tool = req.tool;

  if (tool === "fs.list") {
    const dir = confine(root, params.path || ".");
    const entries = await fsp.readdir(dir, { withFileTypes: true });
    return { status: "succeeded", result: { entries: entries.map((e) => ({ name: e.name, is_dir: e.isDirectory() })) } };
  }

  if (tool === "fs.read") {
    const p = confine(root, params.path);
    const content = await fsp.readFile(p, "utf8");
    return { status: "succeeded", result: { path: params.path, content } };
  }

  if (tool === "fs.write") {
    const p = confine(root, params.path);
    const before = fs.existsSync(p) ? await fsp.readFile(p, "utf8") : null;
    await fsp.mkdir(path.dirname(p), { recursive: true });
    await fsp.writeFile(p, params.content || "", "utf8");
    return { status: "succeeded", result: { files: [{ path: params.path, op: before === null ? "create" : "modify", before, after: params.content }] } };
  }

  if (tool === "fs.edit") {
    const p = confine(root, params.path);
    const content = await fsp.readFile(p, "utf8");
    const search = params.search;
    const parts = content.split(search);
    if (!search || parts.length < 2) {
      return { status: "failed", result: { error: `search string not found in ${params.path}` } };
    }
    if (parts.length > 2) {
      return { status: "failed", result: { error: `search string is ambiguous in ${params.path} (${parts.length - 1} matches)` } };
    }
    const updated = parts[0] + params.replace + parts[1];
    await fsp.writeFile(p, updated, "utf8");
    return { status: "succeeded", result: { files: [{ path: params.path, op: "modify", before: content, after: updated }] } };
  }

  if (tool === "fs.delete") {
    const p = confine(root, params.path);
    await fsp.unlink(p);
    return { status: "succeeded", result: { files: [{ path: params.path, op: "delete", before: null, after: null }] } };
  }

  if (tool === "fs.search") {
    const dir = confine(root, params.path || ".");
    const pattern = new RegExp(params.pattern, "i");
    const matches = [];
    const walk = async (d) => {
      for (const entry of await fsp.readdir(d, { withFileTypes: true })) {
        if (entry.isDirectory()) {
          if (["node_modules", ".git"].includes(entry.name)) continue;
          await walk(path.join(d, entry.name));
          continue;
        }
        const full = path.join(d, entry.name);
        const rel = path.relative(root, full).replace(/\\/g, "/");
        try {
          const content = await fsp.readFile(full, "utf8");
          for (const [i, line] of content.split("\n").entries()) {
            if (pattern.test(line)) matches.push({ path: rel, line: i + 1, text: line.trim().slice(0, 300) });
          }
        } catch {
          /* binary — skip */
        }
      }
    };
    await walk(dir);
    return { status: "succeeded", result: { matches: matches.slice(0, 200) } };
  }

  if (tool === "git.status" || tool === "git.diff" || tool === "git.commit" || tool === "git.push") {
    const git = (args) =>
      new Promise((resolve, reject) =>
        execFile("git", args, { cwd: root, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) =>
          err ? reject(new Error(stderr || err.message)) : resolve(String(stdout)),
        ),
      );
    try {
      if (tool === "git.status") {
        const out = await git(["status", "--porcelain", "--untracked-files=all"]);
        const entries = out.split("\n").filter(Boolean).map((line) => ({ status: line.slice(0, 2).trim(), path: line.slice(3) }));
        return { status: "succeeded", result: { entries } };
      }
      if (tool === "git.diff") {
        const status = await git(["status", "--porcelain", "--untracked-files=all"]);
        const files = [];
        for (const line of status.split("\n").filter(Boolean)) {
          const state = line.slice(0, 2).trim();
          let p = line.slice(3);
          if (p.includes(" -> ")) p = p.split(" -> ")[1];
          files.push({ path: p, op: state === "??" ? "create" : "D".includes(state) ? "delete" : "modify" });
        }
        const summary = await git(["diff", "--stat"]);
        return { status: "succeeded", result: { files, summary: summary.trim() } };
      }
      if (tool === "git.commit") {
        await git(["add", "-A"]);
        await git(["commit", "-m", params.message || "zyntry-code changes"]);
        const head = (await git(["rev-parse", "HEAD"])).trim();
        return { status: "succeeded", result: { committed: true, head } };
      }
      if (tool === "git.push") {
        const branch = params.branch || (await git(["rev-parse", "--abbrev-ref", "HEAD"])).trim();
        await git(["push", "origin", branch]);
        return { status: "succeeded", result: { pushed: true, branch } };
      }
    } catch (err) {
      return { status: "failed", result: { error: redact(err.message, ws) } };
    }
  }

  if (tool === "command.run") {
    const timeout = (ws.timeout_seconds || 300) * 1000;
    const started = Date.now();
    try {
      const { stdout, stderr, code, timedOut } = await new Promise((resolve, reject) => {
        const child = exec(params.cmd || "", { cwd: root, timeout, maxBuffer: 4 * 1024 * 1024 }, (error, stdout, stderr) => {
          if (error) {
            resolve({ stdout, stderr, code: error.code, timedOut: error.killed || error.signal === "SIGTERM" });
            return;
          }
          resolve({ stdout, stderr, code: 0, timedOut: false });
        });
      });
      return {
        status: code === 0 && !timedOut ? "succeeded" : timedOut ? "timed_out" : "failed",
        result: {
          stdout: redact(String(stdout).slice(-20000), ws),
          stderr: redact(String(stderr).slice(-20000), ws),
          exit_code: code,
          duration_ms: Date.now() - started,
          timed_out: timedOut,
        },
      };
    } catch (err) {
      return { status: "failed", result: { error: redact(err.message, ws) } };
    }
  }

  return { status: "failed", result: { error: `unsupported tool: ${tool}` } };
}

// ---------------------------------------------------------------------------
// extension bridge — the bundled dashboard (served by this loopback server)
// can ask the extension to attach the open folder as a task's execution
// workspace and start the local runner. The runner token never leaves this
// process; the dashboard only ever sees the workspace record.
// ---------------------------------------------------------------------------

function detectCommands(root) {
  const has = (f) => {
    try {
      return fs.existsSync(path.join(root, f));
    } catch {
      return false;
    }
  };
  const commands = {};
  if (has("package.json")) {
    commands.test = { cmd: "npm test" };
    commands.lint = { cmd: "npm run lint" };
    commands.type_check = { cmd: "npx tsc --noEmit" };
    commands.build = { cmd: "npm run build" };
  } else if (has("pyproject.toml") || has("requirements.txt")) {
    commands.test = { cmd: "pytest" };
    commands.lint = { cmd: "ruff check ." };
    commands.type_check = { cmd: "mypy ." };
  } else if (has("Cargo.toml")) {
    commands.test = { cmd: "cargo test" };
    commands.build = { cmd: "cargo build" };
  } else if (has("go.mod")) {
    commands.test = { cmd: "go test ./..." };
    commands.build = { cmd: "go build ./..." };
  }
  return commands;
}

async function bridgeCreateWorkspace(taskId) {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    throw new Error("no folder open in VS Code");
  }
  const body = { provider: "local", commands: detectCommands(folders[0].uri.fsPath) };
  if (taskId) body.task_id = taskId;
  const ws = await api("POST", "/workspaces", body);
  if (ws.runner_token) workspaceTokens.set(ws.id, ws.runner_token);
  log("bridge: workspace created", ws.id, "provider=local (runner token held locally)");
  if (!runnerRunning) startLocalRunner();
  return ws;
}

async function handleBridge(req, res, pathname) {
  if (pathname === "/bridge/ping") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ extension: true, port: dashboardPort }));
    return true;
  }
  if (pathname === "/bridge/workspace" && req.method === "POST") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    let body = {};
    try {
      body = raw ? JSON.parse(raw) : {};
    } catch {
      /* empty body is fine */
    }
    try {
      const ws = await bridgeCreateWorkspace(body.task_id);
      const safe = { ...ws };
      delete safe.runner_token;
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ workspace: safe }));
    } catch (err) {
      log("bridge: workspace failed:", err.message);
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: err.message }));
    }
    return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// dashboard — the bundled web UI, served on loopback and shown in a webview
// ---------------------------------------------------------------------------

let dashboardServer = null;
let dashboardPort = 0;

const DASHBOARD_MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".wasm": "application/wasm",
  ".ttf": "font/ttf",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".map": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

function dashboardRoot() {
  return path.join(__dirname, "dashboard");
}

function dashboardHandler(root) {
  return async (req, res) => {
    try {
      let rel = decodeURIComponent(new URL(req.url, "http://127.0.0.1").pathname);
      if (await handleBridge(req, res, rel)) return;
      if (rel === "/" || rel === "") rel = "/index.html";
      const file = path.normalize(path.join(root, rel));
      if (file !== root && !file.startsWith(root + path.sep)) {
        res.writeHead(403);
        res.end();
        return;
      }
      fs.readFile(file, (err, data) => {
        if (err) {
          // SPA fallback: unknown paths get the app shell.
          fs.readFile(path.join(root, "index.html"), (err2, html) => {
            if (err2) {
              res.writeHead(404);
              res.end("not found");
              return;
            }
            res.writeHead(200, { "Content-Type": DASHBOARD_MIME[".html"], "Cache-Control": "no-store" });
            res.end(html);
          });
          return;
        }
        const ext = path.extname(file).toLowerCase();
        let body = data;
        if (ext === ".html") body = Buffer.from(seedDashboardConfig(String(data)), "utf8");
        res.writeHead(200, {
          "Content-Type": DASHBOARD_MIME[ext] || "application/octet-stream",
          "Cache-Control": "no-store",
        });
        res.end(body);
      });
    } catch {
      res.writeHead(500);
      res.end();
    }
  };
}

// The dashboard inherits the service URL from VS Code settings on first open;
// values edited later inside the UI always win over the seed.
function seedDashboardConfig(html) {
  const backend = baseUrl();
  let script = "<script>(function(){try{";
  script += `if(localStorage.getItem('zyntry.backendUrl')==null)localStorage.setItem('zyntry.backendUrl',${JSON.stringify(backend)});`;
  script += "}catch(e){}})();</script>";
  return html.replace(/<head(\s[^>]*)?>/i, (m) => m + script);
}

function listenOn(port, root) {
  return new Promise((resolve) => {
    const server = http.createServer(dashboardHandler(root));
    server.once("error", () => resolve(null));
    server.listen(port, "127.0.0.1", () => {
      server.on("error", (e) => log("dashboard server error:", e.message));
      resolve(server);
    });
  });
}

async function startDashboardServer() {
  if (dashboardServer) return dashboardPort;
  const root = dashboardRoot();
  if (!fs.existsSync(path.join(root, "index.html"))) {
    log("dashboard: bundled UI not found at", root);
    return 0;
  }
  for (const port of [8799, 8800, 8801, 8802, 8803]) {
    const server = await listenOn(port, root);
    if (server) {
      dashboardServer = server;
      dashboardPort = port;
      log(`dashboard UI served at http://127.0.0.1:${port}`);
      return port;
    }
  }
  log("dashboard: no free port in 8799-8803");
  return 0;
}

class DashboardViewProvider {
  async resolveWebviewView(view) {
    view.webview.options = { enableScripts: true };
    const port = await startDashboardServer();
    if (!port) {
      view.webview.html =
        '<html><body style="font-family:sans-serif;padding:16px;color:#9aa7b4;background:#0D1217">' +
        "<h3>Zyntry dashboard not bundled</h3><p>This install was built without the dashboard UI. " +
        "Use the frontend dev server (npm run dev in frontend/, http://localhost:3000) or repackage " +
        "the extension from the repo.</p></body></html>";
      return;
    }
    view.webview.html =
      '<!DOCTYPE html><html><head><meta charset="utf-8">' +
      '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; frame-src http://127.0.0.1:* http://localhost:*; style-src \'unsafe-inline\';">' +
      "<style>html,body{margin:0;padding:0;height:100%;background:#0D1217;overflow:hidden}" +
      "iframe{border:0;width:100%;height:100%;display:block}</style></head>" +
      `<body><iframe src="http://127.0.0.1:${port}/"></iframe></body></html>`;
    log("dashboard webview attached");
  }
}

async function openDashboard() {
  const port = await startDashboardServer();
  if (!port) {
    vscode.window.showErrorMessage(
      "Zyntry: bundled dashboard missing. Run the frontend dev server (npm run dev in frontend/) and open http://localhost:3000",
    );
    return;
  }
  const url = `http://127.0.0.1:${port}/`;
  try {
    await vscode.commands.executeCommand("simpleBrowser.show", vscode.Uri.parse(url));
    return;
  } catch {
    /* Simple Browser unavailable — fall through to the system browser */
  }
  vscode.env.openExternal(vscode.Uri.parse(url));
}

// ---------------------------------------------------------------------------
// activation
// ---------------------------------------------------------------------------

function activate(context) {
  output = vscode.window.createOutputChannel("Zyntry Code");
  const reg = (cmd, fn) => vscode.commands.registerCommand(cmd, fn);
  context.subscriptions.push(
    reg("zyntry.createTask", createTask),
    reg("zyntry.approveTask", approveTask),
    reg("zyntry.runTask", runTask),
    reg("zyntry.streamTask", streamTask),
    reg("zyntry.ingestRepo", ingestRepo),
    reg("zyntry.createWorkspace", createWorkspace),
    reg("zyntry.startLocalRunner", startLocalRunner),
    reg("zyntry.stopLocalRunner", stopLocalRunner),
    reg("zyntry.openDashboard", openDashboard),
    vscode.window.registerWebviewViewProvider("zyntry.dashboard", new DashboardViewProvider()),
  );
  log("Zyntry Code extension activated. Backend:", baseUrl());
  // Zero-config: the local runner comes up by itself, so workspace tool
  // requests (file writes, commands, git) are served without any setup.
  if (config().get("autoStartRunner", true)) {
    setTimeout(() => {
      try {
        startLocalRunner();
      } catch (err) {
        log("auto-start runner failed:", err && err.message);
      }
    }, 3000);
  }
}

function deactivate() {
  if (runnerTimer) clearInterval(runnerTimer);
  runnerRunning = false;
  if (dashboardServer) {
    dashboardServer.close();
    dashboardServer = null;
  }
}

module.exports = { activate, deactivate };