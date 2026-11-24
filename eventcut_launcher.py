"""
EventCut AWS — Lanzador Portable de 1 Solo Archivo (Standalone Launcher)
========================================================================
Este es el UNICO archivo que necesitas llevar contigo (USB / laptop / PC del salon)
junto con tus credenciales temporales de AWS Academy y tu llave labsuser.pem.

¿Que hace automaticamente al ejecutarlo?
  1. Detecta si el repositorio 'eventcut-aws' ya existe localmente; si no, lo clona
     automaticamente desde GitHub (https://github.com/EfrainCardonaD/eventcut-aws.git).
  2. Verifica o crea un entorno virtual (.venv) e instala las dependencias de infra/requirements.txt.
  3. Verifica que existan credenciales validas de AWS (~/.aws/credentials o variables de entorno).
  4. Inicia el Wizard Web Interactivo paso a paso en http://127.0.0.1:8765 con botones de
     'Continuar (Ejecutar Step)', 'Limpiar Todo AWS (Desde 0)' y 'Pruebas de Resiliencia'.

Uso:
  python eventcut_launcher.py
  python eventcut_launcher.py --cli          # Modo consola interactivo (Enter por step)
  python eventcut_launcher.py --auto         # Limpieza total + despliegue completo automatico
  python eventcut_launcher.py --resilience   # Ejecutar suite de pruebas de resiliencia en vivo
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/EfrainCardonaD/eventcut-aws.git"
REPO_DIR_NAME = "eventcut-aws"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def locate_or_clone_repo() -> Path:
    here = Path(__file__).resolve().parent

    # Caso 1: ejecutado dentro del propio repositorio eventcut-aws/
    if (here / "infra" / "wizard_server.py").is_file() and (here / "backend").is_dir():
        print(f"[+] Repositorio local detectado en: {here}")
        return here

    # Caso 2: carpeta eventcut-aws/ al lado del script
    sibling = here / REPO_DIR_NAME
    if (sibling / "infra" / "wizard_server.py").is_file():
        print(f"[+] Repositorio encontrado en: {sibling}")
        try:
            _run(["git", "pull", "--ff-only"], cwd=sibling)
        except Exception:
            print("[i] No se pudo hacer git pull automatico; se continuara con la copia local.")
        return sibling

    # Caso 3: PC nueva en el salon -> clonar automaticamente desde GitHub
    print(f"[*] Repositorio no encontrado localmente. Clonando desde GitHub ({REPO_URL})...")
    _run(["git", "clone", REPO_URL, str(sibling)])
    print(f"[+] Repositorio clonado en: {sibling}")
    return sibling


def ensure_python_env(repo_dir: Path) -> Path:
    # Revisar si el Python actual ya tiene boto3 y requests
    check = subprocess.run(
        [sys.executable, "-c", "import boto3, requests, matplotlib, PIL"],
        capture_output=True,
    )
    if check.returncode == 0:
        print(f"[+] Entorno Python actual listo: {sys.executable}")
        return Path(sys.executable)

    # Revisar si existe un .venv en la carpeta padre (ej. py-aws/.venv) o dentro del repo
    is_win = os.name == "nt"
    rel_py = Path("Scripts/python.exe") if is_win else Path("bin/python")
    for candidate_venv in (repo_dir / ".venv", repo_dir.parent / ".venv"):
        py_bin = candidate_venv / rel_py
        if py_bin.is_file():
            chk = subprocess.run([str(py_bin), "-c", "import boto3, requests"], capture_output=True)
            if chk.returncode == 0:
                print(f"[+] Entorno virtual existente detectado: {py_bin}")
                return py_bin

    # Crear .venv propio dentro del repo e instalar infra/requirements.txt
    venv_dir = repo_dir / ".venv"
    py_bin = venv_dir / rel_py
    if not py_bin.is_file():
        print(f"[*] Creando entorno virtual en {venv_dir}...")
        _run([sys.executable, "-m", "venv", str(venv_dir)])

    print("[*] Instalando dependencias de infra/requirements.txt...")
    _run([str(py_bin), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(py_bin), "-m", "pip", "install", "-r", str(repo_dir / "infra" / "requirements.txt")])
    return py_bin


def check_aws_credentials(py_bin: Path) -> None:
    print("[*] Verificando credenciales AWS (~/.aws/credentials o variables de entorno)...")
    proc = subprocess.run(
        [
            str(py_bin),
            "-c",
            "import boto3; i=boto3.client('sts', region_name='us-east-1').get_caller_identity(); print(i['Account'], i['Arn'])",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print("\n[!] ATENCION: No se detectaron credenciales validas de AWS Academy.")
        print("    1. Abre tu AWS Academy Learner Lab -> boton 'AWS Details' -> 'AWS CLI: Show'.")
        print("    2. Copia el bloque [default] en:")
        print(f"       {Path.home() / '.aws' / 'credentials'}")
        print("    3. Vuelve a ejecutar este script.\n")
        sys.exit(1)
    print(f"[+] AWS verificado: {proc.stdout.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lanzador portable de EventCut AWS")
    parser.add_argument("--cli", action="store_true", help="Ejecutar modo CLI interactivo paso a paso")
    parser.add_argument("--auto", action="store_true", help="Limpiar y desplegar los 10 steps automaticamente")
    parser.add_argument("--resilience", action="store_true", help="Ejecutar las 4 pruebas de resiliencia en vivo")
    parser.add_argument("--pem", help="Ruta explicita a tu archivo labsuser.pem")
    args = parser.parse_args()

    print("==================================================================")
    print("  EVENTCUT AWS — LANZADOR PORTABLE DE INFRAESTRUCTURA (IaC)")
    print("==================================================================")

    repo_dir = locate_or_clone_repo()
    py_bin = ensure_python_env(repo_dir)
    check_aws_credentials(py_bin)

    env = os.environ.copy()
    if args.pem:
        env["EVENTCUT_PEM_PATH"] = str(Path(args.pem).resolve())

    if args.resilience:
        target = [str(py_bin), str(repo_dir / "infra" / "resilience_tests.py")]
    elif args.auto:
        target = [str(py_bin), str(repo_dir / "infra" / "aws_deployer.py"), "--all"]
    elif args.cli:
        target = [str(py_bin), str(repo_dir / "infra" / "aws_deployer.py"), "--cli-interactive"]
    else:
        target = [str(py_bin), str(repo_dir / "infra" / "wizard_server.py")]

    print(f"\n[*] Iniciando: {' '.join(target)}\n", flush=True)
    subprocess.run(target, cwd=str(repo_dir), env=env, check=True)


if __name__ == "__main__":
    main()
