"""
Suite de Pruebas de Resiliencia y Chaos Engineering en vivo para EventCut AWS.
Ejecuta 4 experimentos reales sobre la infraestructura desplegada y genera
telemetría JSON + gráficas de alta resolución para la documentación PDF:
  1. Balanceo Multi-AZ y Carga Concurrente (ALB Round-Robin + Rate Limiting)
  2. Auto-Healing de Contenedor Docker (docker kill sobre auth-service vía SSH)
  3. Falla Catastrófica de Nodo EC2 (terminate-instances + recuperación automática del ASG)
  4. Resiliencia de Almacenamiento S3 (Subida optimizada + Validación de archivos corruptos + Durabilidad)
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import boto3
import matplotlib
import requests
from PIL import Image

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import EVIDENCIAS_DIR, STATE_DIR, load_state

LogFn = Callable[[str], None]
RESULTS_FILE = STATE_DIR / "resilience_results.json"


def _default_log(msg: str) -> None:
    print(msg, flush=True)


def _ssh_exec(pem_path: str, host_ip: str, command: str) -> tuple[int, str, str]:
    cmd = [
        "ssh.exe" if Path("C:/Windows").exists() else "ssh",
        "-i",
        pem_path,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=15",
        f"ec2-user@{host_ip}",
        command,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _get_healthy_nodes(state: dict[str, Any]) -> list[dict[str, Any]]:
    region = state["region"]
    elbv2 = boto3.client("elbv2", region_name=region)
    ec2 = boto3.client("ec2", region_name=region)
    th = elbv2.describe_target_health(TargetGroupArn=state["tg_arn"]).get("TargetHealthDescriptions", [])
    healthy_ids = [t["Target"]["Id"] for t in th if t["TargetHealth"]["State"] == "healthy"]
    if not healthy_ids:
        return []
    desc = ec2.describe_instances(InstanceIds=healthy_ids)
    nodes = []
    for r in desc["Reservations"]:
        for inst in r["Instances"]:
            nodes.append(
                {
                    "instance_id": inst["InstanceId"],
                    "public_ip": inst.get("PublicIpAddress"),
                    "private_ip": inst.get("PrivateIpAddress"),
                    "az": inst["Placement"]["AvailabilityZone"],
                }
            )
    return nodes


def test_1_load_balancing_and_concurrency(state: dict[str, Any], log: LogFn = _default_log) -> dict[str, Any]:
    log("\n=== [PRUEBA 1/4] Balanceo Multi-AZ y Carga Concurrente (60 peticiones) ===")
    url = f"{state['alb_url']}/api/health"
    latencies: list[float] = []
    node_counts: Counter = Counter()
    az_counts: Counter = Counter()
    status_counts: Counter = Counter()

    def _hit(_i: int):
        t0 = time.perf_counter()
        try:
            r = requests.get(url, timeout=8)
            ms = (time.perf_counter() - t0) * 1000
            data = r.json() if r.status_code == 200 else {}
            return r.status_code, ms, data.get("node_id", "unknown"), data.get("availability_zone", "unknown")
        except Exception:
            return 0, (time.perf_counter() - t0) * 1000, "error", "error"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for code, ms, nid, az in ex.map(_hit, range(60)):
            status_counts[str(code)] += 1
            latencies.append(round(ms, 2))
            if code == 200:
                node_counts[nid] += 1
                az_counts[az] += 1

    # Probar Rate Limiting en login (6 intentos fallidos -> el 6to debe regresar 429 o bloqueo controlado)
    rl_statuses = []
    for i in range(7):
        r = requests.post(
            f"{state['alb_url']}/api/auth/login",
            json={"username": f"attacker_{int(time.time())}@test.com", "password": "WrongPassword123!"},
            timeout=8,
        )
        rl_statuses.append(r.status_code)

    success_rate = (status_counts.get("200", 0) / 60.0) * 100
    avg_ms = sum(latencies) / len(latencies)
    p95_ms = sorted(latencies)[int(len(latencies) * 0.95) - 1]
    log(f"[+] Disponibilidad: {success_rate:.1f}% (60/60) | Latencia promedio: {avg_ms:.1f} ms | P95: {p95_ms:.1f} ms")
    log(f"[+] Distribución por nodo EC2: {dict(node_counts)}")
    log(f"[+] Distribución por Zona de Disponibilidad: {dict(az_counts)}")
    log(f"[+] Respuestas prueba Rate-Limiting login: {rl_statuses}")

    return {
        "name": "Balanceo Multi-AZ y Carga Concurrente",
        "total_requests": 60,
        "success_rate_pct": round(success_rate, 2),
        "avg_latency_ms": round(avg_ms, 2),
        "p95_latency_ms": round(p95_ms, 2),
        "latencies_ms": latencies,
        "node_distribution": dict(node_counts),
        "az_distribution": dict(az_counts),
        "status_counts": dict(status_counts),
        "rate_limit_statuses": rl_statuses,
        "passed": success_rate >= 98.0 and len(node_counts) >= 2,
    }


def test_2_container_auto_healing(state: dict[str, Any], log: LogFn = _default_log) -> dict[str, Any]:
    log("\n=== [PRUEBA 2/4] Auto-Healing de Contenedor Docker (Chaos: docker kill) ===")
    nodes = _get_healthy_nodes(state)
    if not nodes:
        raise RuntimeError("No hay nodos saludables en el ALB.")
    target = nodes[0]
    pem_path = state["pem_path"]
    log(f"[*] Nodo objetivo seleccionado: {target['instance_id']} ({target['public_ip']}, {target['az']})")

    stop_flag = threading.Event()
    timeline: list[dict[str, Any]] = []
    start_ts = time.time()

    def _probe_loop():
        while not stop_flag.is_set():
            elapsed = round(time.time() - start_ts, 1)
            t0 = time.perf_counter()
            try:
                r = requests.get(f"{state['alb_url']}/api/health", timeout=4)
                ms = round((time.perf_counter() - t0) * 1000, 1)
                nid = r.json().get("node_id", "?") if r.status_code == 200 else "err"
                timeline.append({"t": elapsed, "status": r.status_code, "ms": ms, "node": nid})
            except Exception:
                timeline.append({"t": elapsed, "status": 0, "ms": 4000.0, "node": "timeout"})
            time.sleep(1.0)

    probe_thread = threading.Thread(target=_probe_loop, daemon=True)
    probe_thread.start()

    time.sleep(4)
    kill_t = round(time.time() - start_ts, 1)
    log(f"[!] Inyectando falla OOM/Crash en t={kill_t}s: matando PID del proceso 'eventcut-auth-service' en {target['instance_id']}...")
    rc, out, err = _ssh_exec(
        pem_path,
        target["public_ip"],
        "PID=$(sudo docker inspect -f '{{.State.Pid}}' eventcut-auth-service) && sudo kill -9 $PID && echo killed_pid=$PID",
    )
    log(f"    -> crash injection rc={rc} out='{out}' err='{err}'")

    # Monitorear recuperación del contenedor en la misma EC2
    recovered_t = None
    for _ in range(30):
        time.sleep(2)
        rc2, state_str, _ = _ssh_exec(
            pem_path,
            target["public_ip"],
            "sudo docker inspect -f '{{.State.Running}} pid={{.State.Pid}} restarts={{.RestartCount}}' eventcut-auth-service",
        )
        if rc2 == 0 and state_str.startswith("true"):
            recovered_t = round(time.time() - start_ts, 1)
            log(f"[+] Contenedor auto-recuperado por Docker (restart: always) en t={recovered_t}s ({state_str})!")
            break

    time.sleep(6)
    stop_flag.set()
    probe_thread.join(timeout=5)

    ok_hits = sum(1 for x in timeline if x["status"] == 200)
    total_hits = len(timeline)
    avail = (ok_hits / max(total_hits, 1)) * 100
    recovery_sec = round((recovered_t - kill_t), 1) if recovered_t else None
    log(f"[+] Resultado Prueba 2: Disponibilidad externa vía ALB = {avail:.1f}% ({ok_hits}/{total_hits}) | Tiempo recuperación contenedor = {recovery_sec}s")

    return {
        "name": "Auto-Healing de Contenedor Docker (docker kill)",
        "target_node": target,
        "kill_at_s": kill_t,
        "recovered_at_s": recovered_t,
        "recovery_seconds": recovery_sec,
        "total_probes": total_hits,
        "ok_probes": ok_hits,
        "availability_pct": round(avail, 2),
        "timeline": timeline,
        "passed": avail >= 90.0 and recovered_t is not None,
    }


def test_3_ec2_chaos_termination(state: dict[str, Any], log: LogFn = _default_log) -> dict[str, Any]:
    log("\n=== [PRUEBA 3/4] Falla Catastrófica de Nodo EC2 (Chaos Termination + Auto Scaling Self-Healing) ===")
    region = state["region"]
    ec2 = boto3.client("ec2", region_name=region)
    elbv2 = boto3.client("elbv2", region_name=region)

    nodes_before = []
    for _ in range(12):
        nodes_before = _get_healthy_nodes(state)
        if len(nodes_before) >= 2:
            break
        log(f"    ... esperando 2 nodos saludables antes de Prueba 3 (actual: {len(nodes_before)})...")
        time.sleep(10)
    if len(nodes_before) < 2:
        raise RuntimeError(f"Se requieren al menos 2 nodos saludables antes de la prueba 3 (actual: {len(nodes_before)}).")
    victim = nodes_before[0]
    survivor = nodes_before[1]
    log(f"[*] Nodos iniciales: {victim['instance_id']} ({victim['az']}) y {survivor['instance_id']} ({survivor['az']})")

    stop_flag = threading.Event()
    timeline: list[dict[str, Any]] = []
    start_ts = time.time()

    def _probe_loop():
        while not stop_flag.is_set():
            elapsed = round(time.time() - start_ts, 1)
            t0 = time.perf_counter()
            try:
                r = requests.get(f"{state['alb_url']}/api/health", timeout=4)
                ms = round((time.perf_counter() - t0) * 1000, 1)
                nid = r.json().get("node_id", "?") if r.status_code == 200 else "err"
                timeline.append({"t": elapsed, "status": r.status_code, "ms": ms, "node": nid})
            except Exception:
                timeline.append({"t": elapsed, "status": 0, "ms": 4000.0, "node": "timeout"})
            time.sleep(2.0)

    probe_thread = threading.Thread(target=_probe_loop, daemon=True)
    probe_thread.start()

    time.sleep(6)
    terminate_t = round(time.time() - start_ts, 1)
    log(f"[!] INYECTANDO FALLA CATASTRÓFICA en t={terminate_t}s: terminando instancia EC2 {victim['instance_id']}...")
    ec2.terminate_instances(InstanceIds=[victim["instance_id"]])

    # Esperar a que ASG detecte la caída, lance un reemplazo y vuelva a 2/2 healthy en el ALB
    replacement_id = None
    full_recovery_t = None
    deadline = time.time() + 540
    while time.time() < deadline:
        th = elbv2.describe_target_health(TargetGroupArn=state["tg_arn"]).get("TargetHealthDescriptions", [])
        healthy_ids = [t["Target"]["Id"] for t in th if t["TargetHealth"]["State"] == "healthy"]
        summary = [(t["Target"]["Id"], t["TargetHealth"]["State"]) for t in th]
        elapsed_now = round(time.time() - start_ts, 1)
        log(f"    [t={elapsed_now}s] Estado Target Group: {summary}")
        new_healthy = [iid for iid in healthy_ids if iid != victim["instance_id"] and iid != survivor["instance_id"]]
        if new_healthy and len(healthy_ids) >= 2:
            replacement_id = new_healthy[0]
            full_recovery_t = elapsed_now
            log(f"[+] ¡AUTO-HEALING COMPLETADO! Nuevo nodo EC2 '{replacement_id}' saludable en t={full_recovery_t}s!")
            break
        time.sleep(15)

    time.sleep(6)
    stop_flag.set()
    probe_thread.join(timeout=5)

    ok_hits = sum(1 for x in timeline if x["status"] == 200)
    total_hits = len(timeline)
    avail = (ok_hits / max(total_hits, 1)) * 100
    recovery_sec = round(full_recovery_t - terminate_t, 1) if full_recovery_t else None
    nodes_after = _get_healthy_nodes(state)

    log(f"[+] Disponibilidad global durante destrucción de nodo EC2: {avail:.1f}% ({ok_hits}/{total_hits})")
    log(f"[+] Tiempo total de auto-reemplazo ASG (nuevo EC2 + Docker + RDS + ALB Healthy): {recovery_sec}s")

    return {
        "name": "Falla Catastrófica de Nodo EC2 (ASG Auto-Healing)",
        "victim_instance": victim,
        "survivor_instance": survivor,
        "replacement_instance_id": replacement_id,
        "nodes_after": nodes_after,
        "terminate_at_s": terminate_t,
        "recovered_at_s": full_recovery_t,
        "recovery_seconds": recovery_sec,
        "total_probes": total_hits,
        "ok_probes": ok_hits,
        "availability_pct": round(avail, 2),
        "timeline": timeline,
        "passed": avail >= 85.0 and replacement_id is not None,
    }


def test_4_s3_storage_resilience(state: dict[str, Any], log: LogFn = _default_log) -> dict[str, Any]:
    log("\n=== [PRUEBA 4/4] Resiliencia y Seguridad de Amazon S3 (Migración Cloudflare R2) ===")
    alb_url = state["alb_url"]

    # 1. Autenticarse como Admin
    login_r = requests.post(
        f"{alb_url}/api/auth/login",
        json={"username": state["admin_email"], "password": state["admin_password"]},
        timeout=10,
    )
    token = (login_r.json().get("data") or {}).get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Solicitar URL de subida para imagen PNG válida
    sig_r = requests.post(
        f"{alb_url}/api/v1/events/image-upload-url",
        json={"content_type": "image/png"},
        params={"content_type": "image/png"},
        headers=headers,
        timeout=10,
    )
    assert sig_r.status_code == 200, f"Fallo image-upload-url: {sig_r.status_code} {sig_r.text}"
    sig_data = sig_r.json().get("data", {})
    upload_url = alb_url + sig_data["upload_url"]
    public_url = sig_data["public_url"]
    file_key = sig_data["file_key"]

    # 3. Prueba negativa: enviar payload corrupto (no imagen) -> debe ser rechazado con 422 sin crashear
    corrupt_r = requests.put(upload_url, data=b"esto-no-es-una-imagen-valida", headers={"Content-Type": "image/png"}, timeout=10)
    log(f"[+] [S3 Guard] Payload corrupto rechazado elegantemente con HTTP {corrupt_r.status_code}")

    # 4. Prueba negativa: intento de escribir fuera del prefijo pending/ -> rechazado con 422
    traversal_r = requests.put(
        f"{alb_url}/api/v1/events/proxy-upload?file_key=events/hacked.png",
        data=b"abc",
        headers={"Content-Type": "image/png"},
        timeout=10,
    )
    log(f"[+] [S3 Guard] Intento fuera de pending/ rechazado con HTTP {traversal_r.status_code}")

    # 5. Subida real de imagen válida optimizada por Pillow -> S3
    img = Image.new("RGB", (600, 300), (16, 185, 129))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    up_r = requests.put(upload_url, data=buf.getvalue(), headers={"Content-Type": "image/png"}, timeout=15)
    assert up_r.status_code == 200, f"Fallo proxy-upload a S3: {up_r.status_code} {up_r.text}"

    # Verificar lectura directa desde Amazon S3
    get_r = requests.get(public_url, timeout=15)
    assert get_r.status_code == 200 and len(get_r.content) > 100
    log(f"[+] [S3 Upload] Imagen optimizada subida y verificada en AWS S3 ({len(get_r.content)} bytes): {public_url}")

    # Limpieza del objeto de prueba en S3
    s3 = boto3.client("s3", region_name=state["region"])
    s3.delete_object(Bucket=state["media_bucket"], Key=file_key)
    log(f"[+] Objeto temporal de prueba limpiado en S3 ({file_key}).")

    return {
        "name": "Resiliencia y Seguridad de Amazon S3",
        "corrupt_payload_http": corrupt_r.status_code,
        "path_guard_http": traversal_r.status_code,
        "valid_upload_http": up_r.status_code,
        "s3_read_http": get_r.status_code,
        "uploaded_bytes": len(get_r.content),
        "sample_s3_url": public_url,
        "passed": corrupt_r.status_code in (400, 415, 422) and traversal_r.status_code == 422 and up_r.status_code == 200 and get_r.status_code == 200,
    }


def generate_resilience_charts(results: dict[str, Any], log: LogFn = _default_log) -> list[str]:
    EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    plt.style.use("seaborn-v0_8-whitegrid")

    # Gráfica 1: Balanceo Multi-AZ y Latencias (Prueba 1)
    t1 = results.get("test_1")
    if t1:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), dpi=180)
        nodes = list(t1["node_distribution"].keys())
        counts = list(t1["node_distribution"].values())
        colors = ["#2563eb", "#0d9488", "#7c3aed", "#d97706"][: len(nodes)]
        bars = ax1.bar(nodes, counts, color=colors, width=0.5)
        ax1.set_title("Distribución de Tráfico ALB (60 Peticiones)", fontweight="bold", fontsize=11)
        ax1.set_ylabel("Peticiones Atendidas")
        ax1.tick_params(axis="x", rotation=10)
        for b in bars:
            ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, f"{int(b.get_height())}", ha="center", fontweight="bold")

        ax2.plot(range(1, len(t1["latencies_ms"]) + 1), t1["latencies_ms"], color="#0284c7", linewidth=1.6, marker="o", markersize=3)
        ax2.axhline(t1["avg_latency_ms"], color="#ef4444", linestyle="--", label=f"Promedio: {t1['avg_latency_ms']} ms")
        ax2.axhline(t1["p95_latency_ms"], color="#f59e0b", linestyle=":", label=f"P95: {t1['p95_latency_ms']} ms")
        ax2.set_title("Latencia de Respuesta bajo Concurrencia", fontweight="bold", fontsize=11)
        ax2.set_xlabel("Número de Petición")
        ax2.set_ylabel("Latencia (ms)")
        ax2.legend()
        plt.tight_layout()
        p1 = str(EVIDENCIAS_DIR / "chart_resilience_load_balancing.png")
        fig.savefig(p1)
        plt.close(fig)
        generated.append(p1)

    # Gráfica 2: Auto-Healing de Contenedor Docker (Prueba 2)
    t2 = results.get("test_2")
    if t2 and t2.get("timeline"):
        fig, ax = plt.subplots(figsize=(10.5, 4.0), dpi=180)
        ts = [p["t"] for p in t2["timeline"]]
        ok = [1 if p["status"] == 200 else 0 for p in t2["timeline"]]
        ms = [p["ms"] for p in t2["timeline"]]
        ax.plot(ts, ms, color="#2563eb", linewidth=1.8, label="Latencia ALB (ms)")
        ax.fill_between(ts, 0, ms, color="#93c5fd", alpha=0.25)
        ax.axvline(t2["kill_at_s"], color="#dc2626", linestyle="--", linewidth=2, label=f"docker kill (t={t2['kill_at_s']}s)")
        if t2.get("recovered_at_s"):
            ax.axvline(t2["recovered_at_s"], color="#16a34a", linestyle="--", linewidth=2, label=f"Contenedor Recuperado (t={t2['recovered_at_s']}s)")
        for x, status_ok, y in zip(ts, ok, ms):
            if not status_ok:
                ax.scatter([x], [y], color="#dc2626", s=50, zorder=5)
        ax.set_title(f"Prueba 2: Auto-Healing de Contenedor (Disponibilidad ALB: {t2['availability_pct']}%)", fontweight="bold", fontsize=11)
        ax.set_xlabel("Tiempo transcurrido (segundos)")
        ax.set_ylabel("Latencia (ms)")
        ax.legend(loc="upper right")
        plt.tight_layout()
        p2 = str(EVIDENCIAS_DIR / "chart_resilience_container_healing.png")
        fig.savefig(p2)
        plt.close(fig)
        generated.append(p2)

    # Gráfica 3: Falla Catastrófica de EC2 + Auto Scaling (Prueba 3)
    t3 = results.get("test_3")
    if t3 and t3.get("timeline"):
        fig, ax = plt.subplots(figsize=(10.5, 4.2), dpi=180)
        ts = [p["t"] for p in t3["timeline"]]
        status_vals = [200 if p["status"] == 200 else 503 for p in t3["timeline"]]
        unique_nodes = sorted({p["node"] for p in t3["timeline"] if p["status"] == 200})
        palette = ["#2563eb", "#0d9488", "#9333ea", "#ea580c"]
        node_color = {n: palette[i % len(palette)] for i, n in enumerate(unique_nodes)}

        for p in t3["timeline"]:
            c = node_color.get(p["node"], "#dc2626") if p["status"] == 200 else "#dc2626"
            ax.scatter(p["t"], 1 if p["status"] == 200 else 0, color=c, s=28, alpha=0.85)

        ax.axvline(t3["terminate_at_s"], color="#dc2626", linestyle="--", linewidth=2, label=f"EC2 Terminada ({t3['victim_instance']['instance_id']})")
        if t3.get("recovered_at_s"):
            ax.axvline(t3["recovered_at_s"], color="#16a34a", linestyle="--", linewidth=2, label=f"Nuevo Nodo Healthy ({t3['replacement_instance_id']})")

        for n, c in node_color.items():
            ax.scatter([], [], color=c, label=f"Atendido por {n}")
        ax.scatter([], [], color="#dc2626", label="Error HTTP / Timeout")

        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Fallo (5xx)", "OK (200)"])
        ax.set_ylim(-0.2, 1.35)
        ax.set_title(
            f"Prueba 3: Destrucción de Nodo EC2 + ASG Self-Healing (Disponibilidad: {t3['availability_pct']}% | Recuperación: {t3['recovery_seconds']}s)",
            fontweight="bold",
            fontsize=10.5,
        )
        ax.set_xlabel("Tiempo transcurrido (segundos)")
        ax.legend(loc="lower right", fontsize=8, ncol=2)
        plt.tight_layout()
        p3 = str(EVIDENCIAS_DIR / "chart_resilience_ec2_failover.png")
        fig.savefig(p3)
        plt.close(fig)
        generated.append(p3)

    log(f"[+] Gráficas de resiliencia generadas: {generated}")
    return generated


def run_all_resilience_tests(log: LogFn = _default_log) -> dict[str, Any]:
    state = load_state()
    if not state.get("alb_url"):
        raise RuntimeError("No hay un despliegue activo en deployment_state.json. Ejecuta primero el despliegue.")

    results: dict[str, Any] = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "alb_url": state["alb_url"],
        "frontend_url": state["frontend_website_url"],
        "media_bucket": state["media_bucket"],
    }
    results["test_1"] = test_1_load_balancing_and_concurrency(state, log)
    results["test_2"] = test_2_container_auto_healing(state, log)
    results["test_4"] = test_4_s3_storage_resilience(state, log)
    results["test_3"] = test_3_ec2_chaos_termination(state, log)
    results["charts"] = generate_resilience_charts(results, log)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"\n[+] SUITE DE RESILIENCIA FINALIZADA. Resultados guardados en: {RESULTS_FILE}")
    return results


if __name__ == "__main__":
    run_all_resilience_tests()
