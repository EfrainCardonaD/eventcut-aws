"""
Wizard Web Interactivo Paso a Paso para Despliegue de EventCut en AWS.
Abre automáticamente una interfaz web local (http://127.0.0.1:8765) con:
  - Flujo guiado de 10 steps con botón explícito 'Continuar al siguiente Step'
  - Botón dedicado 'Limpiar Todo AWS (Desde 0)'
  - Panel de configuración opcional (SMTP, contraseñas demo)
  - Consola de logs en tiempo real + panel de URLs/recursos desplegados
  - Pestaña integrada para ejecutar las Pruebas de Resiliencia en vivo
"""
from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

INFRA_DIR = Path(__file__).resolve().parent
if str(INFRA_DIR) not in sys.path:
    sys.path.insert(0, str(INFRA_DIR))

from aws_deployer import STEPS, run_all_steps, run_step
from config import load_state, save_state
from resilience_tests import RESULTS_FILE, run_all_resilience_tests

HOST = "127.0.0.1"
PORT = 8765


class JobRunner:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.current_job: str | None = None
        self.logs: list[str] = []
        self.last_error: str | None = None

    def append_log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        with self.lock:
            for line in str(msg).splitlines():
                self.logs.append(f"[{ts}] {line}")
            if len(self.logs) > 2000:
                self.logs = self.logs[-1500:]
        print(msg, flush=True)

    def start_job(self, label: str, fn) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.current_job = label
            self.last_error = None

        def _worker():
            try:
                fn(self.append_log)
            except Exception as exc:
                with self.lock:
                    self.last_error = str(exc)
                self.append_log(f"[ERROR] {exc}")
            finally:
                with self.lock:
                    self.running = False
                    self.current_job = None

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            state = load_state()
            resilience = None
            if RESULTS_FILE.is_file():
                try:
                    resilience = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {
                "running": self.running,
                "current_job": self.current_job,
                "last_error": self.last_error,
                "logs": self.logs[-250:],
                "steps": [asdict(s) for s in STEPS],
                "state": state,
                "resilience": resilience,
            }


RUNNER = JobRunner()

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>EventCut AWS — Wizard de Despliegue Paso a Paso</title>
<style>
  :root {
    --bg: #0b1120; --card: #111827; --card2: #1e293b; --border: #334155;
    --text: #f8fafc; --muted: #94a3b8; --primary: #3b82f6; --primary-h: #2563eb;
    --green: #10b981; --red: #ef4444; --amber: #f59e0b;
  }
  * { box-sizing: border-box; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
  body { margin: 0; background: var(--bg); color: var(--text); min-height: 100vh; }
  header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
    padding: 20px 28px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
  }
  header h1 { margin: 0; font-size: 20px; letter-spacing: .3px; }
  header p { margin: 4px 0 0; color: #cbd5e1; font-size: 13px; }
  .badge { padding: 5px 11px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #1e293b; border: 1px solid var(--border); }
  .badge.ok { background: rgba(16,185,129,.18); color: #34d399; border-color: #059669; }
  .badge.busy { background: rgba(245,158,11,.2); color: #fbbf24; border-color: #d97706; }
  .container { display: grid; grid-template-columns: 440px 1fr; gap: 18px; padding: 20px 24px; max-width: 1550px; margin: 0 auto; }
  @media (max-width: 1050px) { .container { grid-template-columns: 1fr; } }
  .panel { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; }
  .panel h2 { margin: 0 0 12px; font-size: 15px; color: #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
  .step-list { display: flex; flex-direction: column; gap: 9px; }
  .step-card {
    background: var(--card2); border: 1px solid var(--border); border-radius: 10px;
    padding: 11px 13px; transition: all .2s; cursor: pointer;
  }
  .step-card.active { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(59,130,246,.28); }
  .step-card.done { border-color: #059669; background: rgba(16,185,129,.08); }
  .step-card.destructive { border-left: 4px solid var(--red); }
  .step-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .step-title { font-weight: 600; font-size: 13.5px; }
  .step-sub { color: var(--muted); font-size: 12px; margin-top: 4px; line-height: 1.35; }
  .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
  .chip { font-size: 10.5px; padding: 2px 7px; border-radius: 6px; background: #0f172a; color: #93c5fd; border: 1px solid #1e3a8a; }
  .actions-bar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
  button {
    border: none; border-radius: 9px; padding: 10px 16px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: .15s; color: white;
  }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .btn-primary { background: var(--primary); }
  .btn-primary:hover:not(:disabled) { background: var(--primary-h); }
  .btn-danger { background: var(--red); }
  .btn-danger:hover:not(:disabled) { background: #dc2626; }
  .btn-green { background: var(--green); color: #052e16; }
  .btn-green:hover:not(:disabled) { background: #059669; color: white; }
  .btn-ghost { background: var(--card2); border: 1px solid var(--border); color: #e2e8f0; }
  .btn-ghost:hover:not(:disabled) { background: #334155; }
  .progress-wrap { background: #0f172a; border-radius: 999px; height: 9px; overflow: hidden; margin-bottom: 14px; border: 1px solid var(--border); }
  .progress-bar { height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); width: 0%; transition: width .35s; }
  .log-box {
    background: #020617; border: 1px solid #1e293b; border-radius: 10px; padding: 12px;
    font-family: 'Cascadia Code', Consolas, monospace; font-size: 12px; line-height: 1.45;
    height: 390px; overflow-y: auto; white-space: pre-wrap; color: #cbd5e1;
  }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; }
  @media (max-width: 800px) { .grid-2 { grid-template-columns: 1fr; } }
  .kv { background: var(--card2); border: 1px solid var(--border); border-radius: 10px; padding: 12px; font-size: 12.5px; }
  .kv div { margin: 4px 0; word-break: break-all; }
  .kv a { color: #60a5fa; text-decoration: none; font-weight: 600; }
  .kv a:hover { text-decoration: underline; }
  .err-banner { background: rgba(239,68,68,.15); border: 1px solid var(--red); color: #fecaca; padding: 10px 12px; border-radius: 9px; margin-bottom: 12px; font-size: 12.5px; display: none; }
  .active-step-box { background: linear-gradient(135deg, rgba(37,99,235,.16), rgba(16,185,129,.1)); border: 1px solid #3b82f6; border-radius: 12px; padding: 14px; margin-bottom: 14px; }
  .active-step-box h3 { margin: 0 0 6px; font-size: 15px; }
  .active-step-box p { margin: 0 0 12px; font-size: 13px; color: #cbd5e1; }
</style>
</head>
<body>
<header>
  <div>
    <h1>EventCut AWS — Asistente de Despliegue Automatizado (IaC)</h1>
    <p>ALB + Auto Scaling Group (2 EC2 Docker) + Amazon RDS MySQL 8.0 + Amazon S3 (Migración Cloudflare R2) + CloudWatch/SNS</p>
  </div>
  <div style="display:flex;gap:8px;align-items:center;">
    <span id="statusBadge" class="badge">Cargando...</span>
    <span id="accountBadge" class="badge">Cuenta: —</span>
  </div>
</header>

<div class="container">
  <!-- Columna izquierda: Lista de Steps -->
  <div class="panel">
    <h2>
      <span>Pasos de Despliegue (0 → 9)</span>
      <span id="progressText" style="font-size:12px;color:#94a3b8;">0/10</span>
    </h2>
    <div class="progress-wrap"><div id="progressBar" class="progress-bar"></div></div>
    <div id="stepList" class="step-list"></div>
  </div>

  <!-- Columna derecha: Control activo, consola y recursos -->
  <div style="display:flex;flex-direction:column;gap:16px;">
    <div class="panel">
      <div id="errBanner" class="err-banner"></div>

      <div class="active-step-box">
        <h3 id="nextStepTitle">Step 0: Validar Entorno</h3>
        <p id="nextStepSub">Haz clic en 'Continuar' para ejecutar este paso en tu cuenta de AWS.</p>
        <div class="actions-bar" style="margin-bottom:0;">
          <button id="btnContinue" class="btn-primary" onclick="runSelectedOrNext()">▶ Continuar (Ejecutar Step)</button>
          <button id="btnCleanup" class="btn-danger" onclick="runCleanup()">🗑 Limpiar Todo AWS (Desde 0)</button>
          <button id="btnAuto" class="btn-green" onclick="runAllAuto()">⚡ Ejecutar Todo Automático</button>
          <button id="btnResilience" class="btn-ghost" onclick="runResilience()">🧪 Correr Pruebas de Resiliencia</button>
        </div>
      </div>

      <h2>
        <span>Consola en Tiempo Real</span>
        <span id="jobLabel" style="font-size:12px;color:#60a5fa;">En espera</span>
      </h2>
      <div id="logBox" class="log-box">Esperando ejecución...</div>

      <div class="grid-2">
        <div class="kv">
          <strong style="color:#93c5fd;">🌐 URLs y Endpoints Desplegados</strong>
          <div>Frontend S3: <a id="urlFrontend" href="#" target="_blank">—</a></div>
          <div>API Gateway (ALB): <a id="urlAlb" href="#" target="_blank">—</a></div>
          <div>Media Bucket S3: <span id="mediaHost">—</span></div>
          <div>Amazon RDS MySQL: <span id="rdsEndpoint">—</span></div>
        </div>
        <div class="kv">
          <strong style="color:#34d399;">🔑 Credenciales Demo y Nodos Activos</strong>
          <div>Admin: <span id="credAdmin">—</span></div>
          <div>Estudiante Demo: <span id="credDemo">—</span></div>
          <div>Nodos EC2 (ASG): <span id="ec2Nodes">—</span></div>
          <div>Alarmas CloudWatch: <span id="cwAlarms">—</span></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
let selectedStepId = null;
let latestData = null;

async function postJson(path, body = {}) {
  const r = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  return await r.json();
}

async function runSelectedOrNext() {
  if (!latestData) return;
  const completed = latestData.state.completed_steps || [];
  let target = selectedStepId;
  if (!target) {
    const next = latestData.steps.find(s => !completed.includes(s.id));
    target = next ? next.id : latestData.steps[latestData.steps.length - 1].id;
  }
  if (target === 'cleanup') {
    if (!confirm('¿Confirmas LIMPIAR TODOS los recursos de usuario en us-east-1 para iniciar desde 0?')) return;
  }
  await postJson('/api/run-step', { step_id: target });
  selectedStepId = null;
  poll();
}

async function runCleanup() {
  if (!confirm('ATENCIÓN: Esto eliminará TODOS los recursos de usuario en us-east-1 (EC2, RDS, S3, ALB, ASG, DynamoDB). ¿Continuar?')) return;
  await postJson('/api/run-step', { step_id: 'cleanup' });
  selectedStepId = null;
  poll();
}

async function runAllAuto() {
  if (!confirm('Esto ejecutará los 10 steps en secuencia (incluyendo limpieza total desde 0 y despliegue completo ~15 min). ¿Continuar?')) return;
  await postJson('/api/run-all', {});
  poll();
}

async function runResilience() {
  if (!confirm('Ejecutará las 4 pruebas de resiliencia en vivo (incluye docker kill y terminación de 1 instancia EC2 para probar ASG self-healing). ¿Continuar?')) return;
  await postJson('/api/run-resilience', {});
  poll();
}

function selectStep(id) {
  selectedStepId = id;
  render();
}

function render() {
  if (!latestData) return;
  const { running, current_job, last_error, logs, steps, state } = latestData;
  const completed = state.completed_steps || [];

  const statusBadge = document.getElementById('statusBadge');
  statusBadge.textContent = running ? `Ejecutando: ${current_job}` : 'Listo';
  statusBadge.className = 'badge ' + (running ? 'busy' : 'ok');
  document.getElementById('accountBadge').textContent = 'Cuenta: ' + (state.account_id || 'Sin validar');
  document.getElementById('jobLabel').textContent = running ? `Corriendo ${current_job}...` : 'En espera';

  const errBox = document.getElementById('errBanner');
  if (last_error) {
    errBox.style.display = 'block';
    errBox.textContent = 'Último error: ' + last_error;
  } else {
    errBox.style.display = 'none';
  }

  const pct = Math.round((completed.length / steps.length) * 100);
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressText').textContent = `${completed.length}/${steps.length} (${pct}%)`;

  const nextAuto = steps.find(s => !completed.includes(s.id));
  const activeStep = steps.find(s => s.id === selectedStepId) || nextAuto || steps[steps.length - 1];

  document.getElementById('nextStepTitle').textContent =
    nextAuto && activeStep.id === nextAuto.id
      ? `Siguiente Step (${activeStep.index}/9): ${activeStep.title}`
      : `Step Seleccionado (${activeStep.index}/9): ${activeStep.title}`;
  document.getElementById('nextStepSub').textContent = `${activeStep.subtitle} (Tiempo estimado: ${activeStep.estimated_time})`;

  document.getElementById('btnContinue').disabled = running;
  document.getElementById('btnCleanup').disabled = running;
  document.getElementById('btnAuto').disabled = running;
  document.getElementById('btnResilience').disabled = running || !state.alb_url;

  const list = document.getElementById('stepList');
  list.innerHTML = '';
  for (const s of steps) {
    const isDone = completed.includes(s.id);
    const isActive = activeStep && activeStep.id === s.id;
    const div = document.createElement('div');
    div.className = 'step-card' + (isDone ? ' done' : '') + (isActive ? ' active' : '') + (s.destructive ? ' destructive' : '');
    div.onclick = () => selectStep(s.id);
    div.innerHTML = `
      <div class="step-top">
        <span class="step-title">${isDone ? '✅' : (isActive ? '👉' : '⬜')} Step ${s.index}: ${s.title}</span>
        <span style="font-size:11px;color:#94a3b8;">${s.estimated_time}</span>
      </div>
      <div class="step-sub">${s.subtitle}</div>
      <div class="chips">${s.services.map(sv => `<span class="chip">${sv}</span>`).join('')}</div>
    `;
    list.appendChild(div);
  }

  const logBox = document.getElementById('logBox');
  const nearBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 60;
  logBox.textContent = logs.length ? logs.join('\n') : 'Presiona "Continuar" para iniciar el Step 0...';
  if (nearBottom || running) logBox.scrollTop = logBox.scrollHeight;

  const fe = document.getElementById('urlFrontend');
  fe.textContent = state.frontend_website_url || '—';
  fe.href = state.frontend_website_url || '#';
  const alb = document.getElementById('urlAlb');
  alb.textContent = state.alb_url || '—';
  alb.href = state.alb_url ? state.alb_url + '/api/health' : '#';
  document.getElementById('mediaHost').textContent = state.media_public_host || '—';
  document.getElementById('rdsEndpoint').textContent = state.rds_endpoint ? `${state.rds_endpoint}:${state.rds_port}` : '—';
  document.getElementById('credAdmin').textContent = `${state.admin_email} / ${state.admin_password}`;
  document.getElementById('credDemo').textContent = `${state.demo_email} / ${state.demo_password}`;
  const nodes = (state.ec2_instances || []).map(n => `${n.instance_id} (${n.az})`).join(', ');
  document.getElementById('ec2Nodes').textContent = nodes || '—';
  document.getElementById('cwAlarms').textContent = (state.cloudwatch_alarms || []).length ? `${state.cloudwatch_alarms.length} activas` : '—';
}

async function poll() {
  try {
    const r = await fetch('/api/status');
    latestData = await r.json();
    render();
  } catch (e) {}
}

setInterval(poll, 2000);
poll();
</script>
</body>
</html>
"""


class WizardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return  # silenciar logs HTTP repetitivos del polling

    def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            raw = HTML_PAGE.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/status":
            self._send_json(RUNNER.snapshot())
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_json()

        if path == "/api/run-step":
            step_id = body.get("step_id")
            ok = RUNNER.start_job(f"step:{step_id}", lambda log: run_step(step_id, log=log))
            self._send_json({"started": ok, "step_id": step_id})
        elif path == "/api/run-all":
            ok = RUNNER.start_job("all-steps", lambda log: run_all_steps(log=log))
            self._send_json({"started": ok})
        elif path == "/api/run-resilience":
            ok = RUNNER.start_job("resilience-suite", lambda log: run_all_resilience_tests(log=log))
            self._send_json({"started": ok})
        elif path == "/api/config":
            state = load_state()
            state.update(body)
            save_state(state)
            self._send_json({"saved": True})
        else:
            self._send_json({"error": "Not found"}, 404)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), WizardHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"\n============================================================")
    print(f"  EventCut AWS Wizard iniciado en: {url}")
    print(f"  Presiona Ctrl+C para detener el servidor local.")
    print(f"============================================================\n", flush=True)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Deteniendo Wizard Web...")
        server.shutdown()


if __name__ == "__main__":
    main()
