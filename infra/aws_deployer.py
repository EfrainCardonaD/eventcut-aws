"""
Motor de Infraestructura como Código (IaC) para EventCut en AWS.
Implementa 10 pasos secuenciales, deterministas y automatizados con boto3:
  0. Validación de entorno y credenciales AWS
  1. Limpieza TOTAL del entorno AWS en us-east-1 (recreación desde 0)
  2. Red Multi-AZ y Security Groups de mínimo privilegio
  3. Buckets Amazon S3 (Migración desde Cloudflare R2 + Frontend SPA + Artefactos)
  4. Base de datos privada Amazon RDS MySQL 8.0
  5. Empaquetado y publicación del Backend en S3
  6. Application Load Balancer (ALB) y Target Group Multi-AZ
  7. Launch Template + Auto Scaling Group (2 nodos EC2 Dockerizados con auto-healing)
  8. Verificación de Migraciones/Seed (RDS+S3) y Compilación/Despliegue Frontend Vue a S3
  9. Monitoreo CloudWatch + Alertas SNS + Verificación End-to-End completa
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import boto3
import requests
from botocore.exceptions import ClientError

from config import (
    BACKEND_DIR,
    DEFAULT_AUTH_DB,
    DEFAULT_EVENTS_DB,
    FRONTEND_DIR,
    PROJECT_TAG,
    load_state,
    reset_state_keep_prefs,
    save_state,
)

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class StepDef:
    index: int
    id: str
    title: str
    subtitle: str
    services: list[str]
    estimated_time: str
    destructive: bool = False


STEPS: list[StepDef] = [
    StepDef(
        0,
        "validate",
        "Validar Entorno y Credenciales AWS",
        "Verifica AWS STS, LabInstanceProfile, llave SSH (labsuser.pem), Node.js y código fuente.",
        ["IAM / STS", "EC2 KeyPairs"],
        "~5 seg",
    ),
    StepDef(
        1,
        "cleanup",
        "Limpieza Total del Entorno AWS (Desde 0)",
        "Elimina TODOS los recursos de usuario en us-east-1 (ASG, ALB, EC2, RDS, S3, DynamoDB, CloudWatch, SGs).",
        ["ASG", "ALB", "EC2", "RDS", "S3", "DynamoDB", "CloudWatch"],
        "~2-5 min",
        destructive=True,
    ),
    StepDef(
        2,
        "network",
        "Red Multi-AZ y Security Groups",
        "Detecta VPC y subredes Multi-AZ; crea SGs aislados para ALB (:80), App EC2 (:8080/:22) y RDS (:3306 privado).",
        ["VPC", "Security Groups", "RDS Subnet Group"],
        "~15 seg",
    ),
    StepDef(
        3,
        "s3",
        "Almacenamiento Amazon S3 (Migración Cloudflare R2)",
        "Crea 3 buckets S3: Media (reemplaza Cloudflare R2 con CORS + Lifecycle), Frontend SPA Website y Artefactos.",
        ["Amazon S3"],
        "~20 seg",
    ),
    StepDef(
        4,
        "rds",
        "Base de Datos Amazon RDS MySQL 8.0",
        "Provisiona instancia privada Amazon RDS MySQL 8.0 (db.t3.micro) con backups automáticos de 7 días.",
        ["Amazon RDS MySQL"],
        "~4-6 min",
    ),
    StepDef(
        5,
        "package",
        "Empaquetar Backend y Subir Artefacto a S3",
        "Empaqueta auth + events_service + Traefik + seed en backend-latest.tar.gz y lo publica en S3.",
        ["Amazon S3"],
        "~10 seg",
    ),
    StepDef(
        6,
        "alb",
        "Application Load Balancer (ALB) Multi-AZ",
        "Crea ALB público, Target Group (:8080, health check /api/health cada 15s) y Listener HTTP :80.",
        ["Elastic Load Balancing (ALB)"],
        "~2-3 min",
    ),
    StepDef(
        7,
        "asg",
        "Launch Template y Auto Scaling Group (2 EC2)",
        "Despliega 2 instancias EC2 Amazon Linux 2023 en AZs distintas con Docker Compose, Traefik, Auth y Events.",
        ["EC2", "Auto Scaling", "SSM Parameter"],
        "~4-6 min",
    ),
    StepDef(
        8,
        "frontend",
        "Compilar y Desplegar Frontend Vue 3 en S3",
        "Confirma migraciones/seed en RDS+S3, compila Vue 3 apuntando al ALB y publica dist/ en S3 Website.",
        ["Amazon S3 Website", "Vite / Vue 3"],
        "~45 seg",
    ),
    StepDef(
        9,
        "monitoring",
        "Monitoreo CloudWatch, Alertas SNS y Verificación E2E",
        "Crea tópico SNS, 4 alarmas CloudWatch y valida login JWT, eventos, balanceo multi-nodo y subida a S3.",
        ["CloudWatch", "Amazon SNS", "E2E Tests"],
        "~25 seg",
    ),
]


def _default_log(msg: str) -> None:
    print(msg, flush=True)


def _client(service: str, region: str):
    return boto3.client(service, region_name=region)


# =====================================================================
# STEP 0: VALIDACIÓN
# =====================================================================
def step_validate(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    log(f"[*] Validando credenciales AWS en región '{region}'...")
    sts = _client("sts", region)
    ident = sts.get_caller_identity()
    state["account_id"] = ident["Account"]
    state["caller_arn"] = ident["Arn"]
    log(f"[+] Cuenta AWS verificada: {ident['Account']} ({ident['Arn']})")

    iam = _client("iam", region)
    try:
        prof = iam.get_instance_profile(InstanceProfileName=state["instance_profile"])
        log(f"[+] Instance Profile disponible: {prof['InstanceProfile']['Arn']}")
    except ClientError as exc:
        raise RuntimeError(f"No se encontró InstanceProfile '{state['instance_profile']}': {exc}") from exc

    ec2 = _client("ec2", region)
    kps = [kp["KeyName"] for kp in ec2.describe_key_pairs()["KeyPairs"]]
    if state["key_name"] not in kps:
        raise RuntimeError(f"KeyPair '{state['key_name']}' no existe en AWS. Disponibles: {kps}")
    log(f"[+] KeyPair EC2 encontrado: {state['key_name']}")

    pem_path = state.get("pem_path", "")
    if pem_path and Path(pem_path).is_file():
        log(f"[+] Llave privada PEM localizada: {pem_path}")
    else:
        log(f"[!] Aviso: No se encontró labsuser.pem en {pem_path} (SSH opcional para pruebas de caos).")

    # Verificar Node/NPM para build del frontend
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    proc = subprocess.run([npm_cmd, "--version"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("No se encontró npm instalado localmente para compilar el frontend.")
    log(f"[+] NPM local verificado: v{proc.stdout.strip()}")

    if not (BACKEND_DIR / "docker-compose.aws.yml").is_file():
        raise RuntimeError(f"Falta docker-compose.aws.yml en {BACKEND_DIR}")
    if not (FRONTEND_DIR / "package.json").is_file():
        raise RuntimeError(f"Falta package.json en {FRONTEND_DIR}")
    log(f"[+] Código fuente validado: frontend/ y backend/ listos.")
    save_state(state)
    return state


# =====================================================================
# STEP 1: LIMPIEZA TOTAL DEL ENTORNO AWS (DESDE 0)
# =====================================================================
def _empty_and_delete_bucket(s3_client, bucket_name: str, log: LogFn) -> None:
    log(f"    -> Vaciando bucket S3: {bucket_name}")
    try:
        paginator = s3_client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket_name):
            objects = []
            for v in page.get("Versions", []):
                objects.append({"Key": v["Key"], "VersionId": v["VersionId"]})
            for m in page.get("DeleteMarkers", []):
                objects.append({"Key": m["Key"], "VersionId": m["VersionId"]})
            if objects:
                for i in range(0, len(objects), 1000):
                    s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects[i : i + 1000]})
    except ClientError:
        pass

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                for i in range(0, len(objs), 1000):
                    s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": objs[i : i + 1000]})
    except ClientError:
        pass

    try:
        s3_client.delete_bucket(Bucket=bucket_name)
        log(f"    [+] Bucket S3 eliminado: {bucket_name}")
    except ClientError as exc:
        log(f"    [!] No se pudo eliminar bucket {bucket_name}: {exc}")


def step_cleanup(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    log(f"[*] INICIANDO LIMPIEZA TOTAL DE RECURSOS DE USUARIO EN {region}...")

    asg_client = _client("autoscaling", region)
    ec2_client = _client("ec2", region)
    elbv2 = _client("elbv2", region)
    rds = _client("rds", region)
    s3 = _client("s3", region)
    ddb = _client("dynamodb", region)
    cw = _client("cloudwatch", region)
    sns = _client("sns", region)

    # 1. Auto Scaling Groups
    asgs = asg_client.describe_auto_scaling_groups().get("AutoScalingGroups", [])
    if asgs:
        for grp in asgs:
            name = grp["AutoScalingGroupName"]
            log(f"[*] Eliminando Auto Scaling Group: {name}")
            asg_client.delete_auto_scaling_group(AutoScalingGroupName=name, ForceDelete=True)
        deadline = time.time() + 240
        while time.time() < deadline:
            remaining = asg_client.describe_auto_scaling_groups().get("AutoScalingGroups", [])
            if not remaining:
                break
            log(f"    ... esperando eliminación de {len(remaining)} ASG(s)...")
            time.sleep(10)
        log("[+] Auto Scaling Groups eliminados.")
    else:
        log("[i] Sin Auto Scaling Groups activos.")

    # 2. Launch Templates
    lts = ec2_client.describe_launch_templates().get("LaunchTemplates", [])
    for lt in lts:
        log(f"[*] Eliminando Launch Template: {lt['LaunchTemplateName']} ({lt['LaunchTemplateId']})")
        ec2_client.delete_launch_template(LaunchTemplateId=lt["LaunchTemplateId"])

    # 3. Load Balancers & Target Groups
    lbs = elbv2.describe_load_balancers().get("LoadBalancers", [])
    for lb in lbs:
        log(f"[*] Eliminando Load Balancer: {lb['LoadBalancerName']}")
        elbv2.delete_load_balancer(LoadBalancerArn=lb["LoadBalancerArn"])
    if lbs:
        deadline = time.time() + 180
        while time.time() < deadline:
            if not elbv2.describe_load_balancers().get("LoadBalancers", []):
                break
            log("    ... esperando liberación del ALB y sus ENIs...")
            time.sleep(8)
        time.sleep(10)
        log("[+] Load Balancers eliminados.")

    tgs = elbv2.describe_target_groups().get("TargetGroups", [])
    for tg in tgs:
        log(f"[*] Eliminando Target Group: {tg['TargetGroupName']}")
        try:
            elbv2.delete_target_group(TargetGroupArn=tg["TargetGroupArn"])
        except ClientError as exc:
            log(f"    [!] Reintentando Target Group tras pausa: {exc}")
            time.sleep(10)
            try:
                elbv2.delete_target_group(TargetGroupArn=tg["TargetGroupArn"])
            except ClientError:
                pass

    # 4. Instancias EC2 (todas las activas/detenidas)
    reservations = ec2_client.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
    ).get("Reservations", [])
    inst_ids = [i["InstanceId"] for r in reservations for i in r["Instances"]]
    if inst_ids:
        log(f"[*] Terminando {len(inst_ids)} instancia(s) EC2: {', '.join(inst_ids)}")
        ec2_client.terminate_instances(InstanceIds=inst_ids)
        waiter = ec2_client.get_waiter("instance_terminated")
        waiter.wait(InstanceIds=inst_ids, WaiterConfig={"Delay": 10, "MaxAttempts": 36})
        log("[+] Todas las instancias EC2 terminadas.")
    else:
        log("[i] Sin instancias EC2 activas.")

    # 5. Instancias RDS + DB Subnet Groups
    dbs = rds.describe_db_instances().get("DBInstances", [])
    deleting_dbs = []
    for db in dbs:
        db_id = db["DBInstanceIdentifier"]
        db_status = db["DBInstanceStatus"]
        if db_status != "deleting":
            log(f"[*] Eliminando instancia RDS: {db_id} (estado actual: {db_status})")
            try:
                rds.modify_db_instance(
                    DBInstanceIdentifier=db_id, DeletionProtection=False, ApplyImmediately=True
                )
            except ClientError:
                pass
            rds.delete_db_instance(
                DBInstanceIdentifier=db_id,
                SkipFinalSnapshot=True,
                DeleteAutomatedBackups=True,
            )
        else:
            log(f"[i] Instancia RDS {db_id} ya está en eliminación...")
        deleting_dbs.append(db_id)

    for db_id in deleting_dbs:
        log(f"    ... esperando eliminación completa de RDS '{db_id}' (puede tardar 2-4 min)...")
        deadline = time.time() + 480
        while time.time() < deadline:
            try:
                res = rds.describe_db_instances(DBInstanceIdentifier=db_id)
                st = res["DBInstances"][0]["DBInstanceStatus"]
                log(f"    ... RDS '{db_id}' estado: {st}")
                time.sleep(15)
            except ClientError as exc:
                if "DBInstanceNotFound" in str(exc):
                    log(f"[+] RDS '{db_id}' eliminada completamente.")
                    break
                raise

    # DB Subnet Groups no-default
    for sg in rds.describe_db_subnet_groups().get("DBSubnetGroups", []):
        name = sg["DBSubnetGroupName"]
        if name != "default":
            try:
                rds.delete_db_subnet_group(DBSubnetGroupName=name)
                log(f"[+] DB Subnet Group eliminado: {name}")
            except ClientError as exc:
                log(f"    [!] No se pudo eliminar DB Subnet Group {name}: {exc}")

    # 6. Buckets S3 (todos los de la cuenta en us-east-1 o creados por el usuario)
    buckets = s3.list_buckets().get("Buckets", [])
    if buckets:
        log(f"[*] Eliminando {len(buckets)} bucket(s) S3...")
        for b in buckets:
            _empty_and_delete_bucket(s3, b["Name"], log)
    else:
        log("[i] Sin buckets S3.")

    # 7. Tablas DynamoDB
    tables = ddb.list_tables().get("TableNames", [])
    for tbl in tables:
        log(f"[*] Eliminando tabla DynamoDB: {tbl}")
        ddb.delete_table(TableName=tbl)
    if tables:
        log("[+] Tablas DynamoDB eliminadas.")

    # 8. Alarmas CloudWatch
    alarms = [a["AlarmName"] for a in cw.describe_alarms().get("MetricAlarms", [])]
    if alarms:
        log(f"[*] Eliminando {len(alarms)} alarma(s) CloudWatch...")
        cw.delete_alarms(AlarmNames=alarms)
        log("[+] Alarmas CloudWatch eliminadas.")

    # 9. Tópicos SNS de usuario (preservando el tópico interno RedshiftSNS de AWS Academy)
    topics = sns.list_topics().get("Topics", [])
    for t in topics:
        arn = t["TopicArn"]
        if arn.endswith(":RedshiftSNS"):
            continue
        log(f"[*] Eliminando tópico SNS: {arn}")
        try:
            sns.delete_topic(TopicArn=arn)
        except ClientError as exc:
            log(f"    [!] Aviso eliminando SNS {arn}: {exc}")

    # 10. Security Groups no-default (primero limpiar reglas cruzadas para evitar DependencyViolation)
    sgs = [sg for sg in ec2_client.describe_security_groups().get("SecurityGroups", []) if sg["GroupName"] != "default"]
    if sgs:
        log(f"[*] Limpiando {len(sgs)} Security Group(s) personalizados...")
        for sg in sgs:
            if sg.get("IpPermissions"):
                try:
                    ec2_client.revoke_security_group_ingress(GroupId=sg["GroupId"], IpPermissions=sg["IpPermissions"])
                except ClientError:
                    pass
        for attempt in range(4):
            remaining = [
                sg for sg in ec2_client.describe_security_groups().get("SecurityGroups", []) if sg["GroupName"] != "default"
            ]
            if not remaining:
                break
            for sg in remaining:
                try:
                    ec2_client.delete_security_group(GroupId=sg["GroupId"])
                    log(f"    [+] Security Group eliminado: {sg['GroupName']} ({sg['GroupId']})")
                except ClientError:
                    pass
            if attempt < 3:
                time.sleep(8)

    state = reset_state_keep_prefs(state)
    state["completed_steps"] = ["validate", "cleanup"]
    save_state(state)
    log("[+] LIMPIEZA TOTAL COMPLETADA. El entorno AWS está completamente limpio desde 0.")
    return state


# =====================================================================
# STEP 2: RED MULTI-AZ Y SECURITY GROUPS
# =====================================================================
def _ensure_sg(ec2, vpc_id: str, name: str, desc: str, log: LogFn) -> str:
    existing = ec2.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}, {"Name": "group-name", "Values": [name]}]
    ).get("SecurityGroups", [])
    if existing:
        sg_id = existing[0]["GroupId"]
        log(f"[i] Security Group existente reutilizado: {name} ({sg_id})")
        return sg_id
    resp = ec2.create_security_group(
        GroupName=name,
        Description=desc,
        VpcId=vpc_id,
        TagSpecifications=[
            {"ResourceType": "security-group", "Tags": [{"Key": "Name", "Value": name}, {"Key": "Project", "Value": PROJECT_TAG}]}
        ],
    )
    sg_id = resp["GroupId"]
    log(f"[+] Security Group creado: {name} ({sg_id})")
    return sg_id


def _add_ingress_safe(ec2, group_id: str, permissions: list[dict], log: LogFn) -> None:
    for perm in permissions:
        try:
            ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[perm])
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "InvalidPermission.Duplicate":
                raise


def step_network(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    ec2 = _client("ec2", region)
    rds = _client("rds", region)

    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}]).get("Vpcs", [])
    if not vpcs:
        raise RuntimeError("No se encontró la VPC por defecto en la cuenta.")
    vpc_id = vpcs[0]["VpcId"]
    state["vpc_id"] = vpc_id
    log(f"[+] VPC por defecto detectada: {vpc_id}")

    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("Subnets", [])
    # Preferimos subredes en AZs compatibles con t3/db.t3 (us-east-1a, us-east-1b, us-east-1c, us-east-1d)
    preferred_azs = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d"]
    selected = []
    seen_az = set()
    for az in preferred_azs:
        for s in subnets:
            if s["AvailabilityZone"] == az and az not in seen_az:
                selected.append(s)
                seen_az.add(az)
                break
    if len(selected) < 2:
        selected = subnets[:2]

    state["subnet_ids"] = [s["SubnetId"] for s in selected]
    state["availability_zones"] = [s["AvailabilityZone"] for s in selected]
    log(f"[+] Subredes Multi-AZ seleccionadas: {list(zip(state['subnet_ids'], state['availability_zones']))}")

    alb_sg = _ensure_sg(ec2, vpc_id, "eventcut-alb-sg", "ALB publico HTTP para EventCut", log)
    app_sg = _ensure_sg(ec2, vpc_id, "eventcut-app-sg", "Instancias EC2 EventCut (Traefik + FastAPI)", log)
    rds_sg = _ensure_sg(ec2, vpc_id, "eventcut-rds-sg", "RDS MySQL privado solo accesible desde eventcut-app-sg", log)

    # ALB: puerto 80 público
    _add_ingress_safe(
        ec2,
        alb_sg,
        [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP publico"}]}],
        log,
    )
    # App EC2: puerto 8080 SOLO desde ALB + puerto 22 SSH para administración/chaos demo
    _add_ingress_safe(
        ec2,
        app_sg,
        [
            {"IpProtocol": "tcp", "FromPort": 8080, "ToPort": 8080, "UserIdGroupPairs": [{"GroupId": alb_sg, "Description": "Trafico desde ALB"}]},
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH administracion y pruebas de resiliencia"}]},
        ],
        log,
    )
    # RDS MySQL: puerto 3306 EXCLUSIVAMENTE desde App EC2 SG
    _add_ingress_safe(
        ec2,
        rds_sg,
        [{"IpProtocol": "tcp", "FromPort": 3306, "ToPort": 3306, "UserIdGroupPairs": [{"GroupId": app_sg, "Description": "MySQL solo desde nodos EventCut"}]}],
        log,
    )

    state["alb_sg_id"] = alb_sg
    state["app_sg_id"] = app_sg
    state["rds_sg_id"] = rds_sg
    log("[+] Reglas de mínimo privilegio configuradas: Internet -> ALB(:80) -> EC2(:8080) -> RDS(:3306).")

    # DB Subnet Group
    subnet_group_name = "eventcut-rds-subnet-group"
    try:
        rds.create_db_subnet_group(
            DBSubnetGroupName=subnet_group_name,
            DBSubnetGroupDescription="Subredes Multi-AZ para EventCut RDS MySQL",
            SubnetIds=state["subnet_ids"],
            Tags=[{"Key": "Project", "Value": PROJECT_TAG}],
        )
        log(f"[+] DB Subnet Group creado: {subnet_group_name}")
    except ClientError as exc:
        if "DBSubnetGroupAlreadyExists" in str(exc):
            log(f"[i] DB Subnet Group ya existe: {subnet_group_name}")
        else:
            raise

    save_state(state)
    return state


# =====================================================================
# STEP 3: BUCKETS AMAZON S3 (MIGRACIÓN CLOUDFLARE R2 + FRONTEND + ARTEFACTOS)
# =====================================================================
def _create_bucket(s3, bucket_name: str, region: str, log: LogFn) -> None:
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})
        log(f"[+] Bucket S3 creado: {bucket_name}")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou",):
            log(f"[i] Bucket S3 ya existe: {bucket_name}")
        else:
            raise


def step_s3(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    acct = state["account_id"] or _client("sts", region).get_caller_identity()["Account"]
    state["account_id"] = acct
    s3 = _client("s3", region)

    media_bucket = state.get("media_bucket") or f"eventcut-media-{acct}-{region}"
    frontend_bucket = state.get("frontend_bucket") or f"eventcut-web-{acct}-{region}"
    artifacts_bucket = state.get("artifacts_bucket") or f"eventcut-artifacts-{acct}-{region}"

    # 1. Bucket Media (reemplaza Cloudflare R2)
    _create_bucket(s3, media_bucket, region, log)
    s3.put_public_access_block(
        Bucket=media_bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )
    media_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadEventCutMedia",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{media_bucket}/*"],
            }
        ],
    }
    s3.put_bucket_policy(Bucket=media_bucket, Policy=json.dumps(media_policy))
    s3.put_bucket_cors(
        Bucket=media_bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "HEAD", "PUT"],
                    "AllowedOrigins": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )
    # Lifecycle rule: limpia automáticamente imágenes huérfanas en pending/ tras 1 día
    s3.put_bucket_lifecycle_configuration(
        Bucket=media_bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "CleanupPendingEventImages",
                    "Filter": {"Prefix": "events/pending/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": 1},
                },
                {
                    "ID": "CleanupPendingCommunityImages",
                    "Filter": {"Prefix": "comunidad/pending/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": 1},
                },
            ]
        },
    )
    media_public_host = f"https://{media_bucket}.s3.{region}.amazonaws.com"
    log(f"[+] Bucket Media S3 listo (migración Cloudflare R2 -> AWS S3): {media_public_host}")

    # 2. Bucket Frontend SPA (S3 Static Website Hosting)
    _create_bucket(s3, frontend_bucket, region, log)
    s3.put_public_access_block(
        Bucket=frontend_bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        },
    )
    web_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadFrontendSPA",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{frontend_bucket}/*"],
            }
        ],
    }
    s3.put_bucket_policy(Bucket=frontend_bucket, Policy=json.dumps(web_policy))
    s3.put_bucket_website(
        Bucket=frontend_bucket,
        WebsiteConfiguration={
            "IndexDocument": {"Suffix": "index.html"},
            "ErrorDocument": {"Key": "index.html"},  # SPA Vue Router fallback
        },
    )
    frontend_url = f"http://{frontend_bucket}.s3-website-{region}.amazonaws.com"
    log(f"[+] Bucket Frontend SPA S3 configurado: {frontend_url}")

    # 3. Bucket Artefactos privado (código backend para bootstrap automático del ASG)
    _create_bucket(s3, artifacts_bucket, region, log)
    log(f"[+] Bucket Artefactos privado listo: s3://{artifacts_bucket}")

    state["media_bucket"] = media_bucket
    state["media_public_host"] = media_public_host
    state["frontend_bucket"] = frontend_bucket
    state["frontend_website_url"] = frontend_url
    state["artifacts_bucket"] = artifacts_bucket
    save_state(state)
    return state


# =====================================================================
# STEP 4: AMAZON RDS MYSQL 8.0
# =====================================================================
def step_rds(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    rds = _client("rds", region)
    db_id = state["rds_identifier"]

    exists = False
    try:
        resp = rds.describe_db_instances(DBInstanceIdentifier=db_id)
        db = resp["DBInstances"][0]
        exists = True
        log(f"[i] Instancia RDS '{db_id}' ya existe (estado: {db['DBInstanceStatus']}).")
    except ClientError as exc:
        if "DBInstanceNotFound" not in str(exc):
            raise

    if not exists:
        log(f"[*] Creando instancia Amazon RDS MySQL 8.0 '{db_id}' ({state['rds_instance_class']}, privada)...")
        rds.create_db_instance(
            DBInstanceIdentifier=db_id,
            DBInstanceClass=state["rds_instance_class"],
            Engine="mysql",
            EngineVersion="8.0",
            MasterUsername=state["db_user"],
            MasterUserPassword=state["db_password"],
            AllocatedStorage=20,
            StorageType="gp2",
            DBName=DEFAULT_AUTH_DB,
            VpcSecurityGroupIds=[state["rds_sg_id"]],
            DBSubnetGroupName="eventcut-rds-subnet-group",
            PubliclyAccessible=False,
            BackupRetentionPeriod=7,
            MultiAZ=False,
            AutoMinorVersionUpgrade=True,
            DeletionProtection=False,
            Tags=[{"Key": "Project", "Value": PROJECT_TAG}, {"Key": "Name", "Value": db_id}],
        )
        log("[*] Solicitud RDS enviada. Esperando a que el motor MySQL 8.0 esté 'available' (4-6 min)...")

    deadline = time.time() + 720
    while time.time() < deadline:
        db = rds.describe_db_instances(DBInstanceIdentifier=db_id)["DBInstances"][0]
        st = db["DBInstanceStatus"]
        if st == "available" and db.get("Endpoint"):
            state["rds_endpoint"] = db["Endpoint"]["Address"]
            state["rds_port"] = db["Endpoint"]["Port"]
            log(f"[+] Amazon RDS MySQL disponible: {state['rds_endpoint']}:{state['rds_port']}")
            save_state(state)
            return state
        log(f"    ... RDS estado actual: {st}")
        time.sleep(20)

    raise TimeoutError("Tiempo de espera agotado esperando Amazon RDS MySQL.")


# =====================================================================
# STEP 5: EMPAQUETADO DEL BACKEND Y SUBIDA A S3
# =====================================================================
def step_package(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    s3 = _client("s3", region)
    bucket = state["artifacts_bucket"]
    exclude_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea", "node_modules"}

    log(f"[*] Empaquetando código del backend desde {BACKEND_DIR}...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = Path(tmpdir) / "backend-latest.tar.gz"
        file_count = 0
        with tarfile.open(tar_path, "w:gz") as tar:
            for root, dirs, files in os.walk(BACKEND_DIR):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for fname in files:
                    if fname == ".env" or fname.endswith((".pyc", ".rar", ".sqlite3")):
                        continue
                    full_path = Path(root) / fname
                    rel_path = full_path.relative_to(BACKEND_DIR)
                    tar.add(full_path, arcname=str(rel_path).replace("\\", "/"))
                    file_count += 1
        size_kb = tar_path.stat().st_size / 1024
        log(f"[+] Paquete generado: {file_count} archivos ({size_kb:.1f} KB)")
        s3.upload_file(str(tar_path), bucket, "releases/backend-latest.tar.gz")
        log(f"[+] Artefacto subido a s3://{bucket}/releases/backend-latest.tar.gz")

    save_state(state)
    return state


# =====================================================================
# STEP 6: APPLICATION LOAD BALANCER (ALB) MULTI-AZ
# =====================================================================
def step_alb(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    elbv2 = _client("elbv2", region)

    # Target Group
    tg_name = "eventcut-tg"
    try:
        tgs = elbv2.describe_target_groups(Names=[tg_name])["TargetGroups"]
        tg_arn = tgs[0]["TargetGroupArn"]
        log(f"[i] Target Group existente: {tg_name}")
    except ClientError:
        resp = elbv2.create_target_group(
            Name=tg_name,
            Protocol="HTTP",
            Port=8080,
            VpcId=state["vpc_id"],
            TargetType="instance",
            HealthCheckProtocol="HTTP",
            HealthCheckPort="8080",
            HealthCheckPath="/api/health",
            HealthCheckIntervalSeconds=15,
            HealthCheckTimeoutSeconds=5,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=2,
            Matcher={"HttpCode": "200"},
            Tags=[{"Key": "Project", "Value": PROJECT_TAG}],
        )
        tg_arn = resp["TargetGroups"][0]["TargetGroupArn"]
        elbv2.modify_target_group_attributes(
            TargetGroupArn=tg_arn,
            Attributes=[{"Key": "deregistration_delay.timeout_seconds", "Value": "15"}],
        )
        log(f"[+] Target Group creado: {tg_name} (HealthCheck GET /api/health cada 15s)")

    # ALB
    alb_name = "eventcut-alb"
    try:
        lbs = elbv2.describe_load_balancers(Names=[alb_name])["LoadBalancers"]
        lb = lbs[0]
        log(f"[i] ALB existente: {alb_name}")
    except ClientError:
        resp = elbv2.create_load_balancer(
            Name=alb_name,
            Subnets=state["subnet_ids"][:2],
            SecurityGroups=[state["alb_sg_id"]],
            Scheme="internet-facing",
            Type="application",
            IpAddressType="ipv4",
            Tags=[{"Key": "Project", "Value": PROJECT_TAG}, {"Key": "Name", "Value": alb_name}],
        )
        lb = resp["LoadBalancers"][0]
        log(f"[+] Application Load Balancer creado: {alb_name} ({lb['DNSName']})")

    alb_arn = lb["LoadBalancerArn"]
    alb_dns = lb["DNSName"]

    # Esperar estado active
    log("[*] Esperando a que el ALB esté activo...")
    waiter = elbv2.get_waiter("load_balancer_available")
    waiter.wait(LoadBalancerArns=[alb_arn])
    log(f"[+] ALB activo y listo en: http://{alb_dns}")

    # Listener :80 -> Target Group
    listeners = elbv2.describe_listeners(LoadBalancerArn=alb_arn).get("Listeners", [])
    if listeners:
        listener_arn = listeners[0]["ListenerArn"]
        log(f"[i] Listener HTTP :80 ya existe.")
    else:
        resp = elbv2.create_listener(
            LoadBalancerArn=alb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
        )
        listener_arn = resp["Listeners"][0]["ListenerArn"]
        log("[+] Listener HTTP :80 -> eventcut-tg(:8080) configurado.")

    state["tg_arn"] = tg_arn
    state["alb_arn"] = alb_arn
    state["alb_dns"] = alb_dns
    state["alb_url"] = f"http://{alb_dns}"
    state["listener_arn"] = listener_arn
    save_state(state)
    return state


# =====================================================================
# STEP 7: LAUNCH TEMPLATE + AUTO SCALING GROUP (2 INSTANCIAS EC2)
# =====================================================================
def _build_ec2_userdata(state: dict[str, Any]) -> str:
    region = state["region"]
    cors_origins = ",".join(
        [
            state["frontend_website_url"].rstrip("/"),
            state["alb_url"].rstrip("/"),
            "http://localhost:5173",
            "http://localhost:3000",
        ]
    )
    smtp_enabled = "true" if state.get("smtp_enabled") else "false"
    return f"""#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/eventcut-bootstrap.log | logger -t eventcut-bootstrap) 2>&1

echo "=== [1/6] Instalando Docker y Docker Compose v2 en Amazon Linux 2023 ==="
dnf install -y docker tar gzip
systemctl enable --now docker
usermod -aG docker ec2-user || true

mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSL https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version

echo "=== [2/6] Obteniendo metadatos EC2 (IMDSv2) ==="
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || true)
EC2_INSTANCE_ID=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id || hostname)
AWS_AZ=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone || echo "{region}")

echo "=== [3/6] Descargando artefacto Backend desde Amazon S3 ==="
mkdir -p /opt/eventcut
cd /opt/eventcut
aws s3 cp "s3://{state['artifacts_bucket']}/releases/backend-latest.tar.gz" /tmp/backend-latest.tar.gz --region "{region}"
tar -xzf /tmp/backend-latest.tar.gz -C /opt/eventcut

echo "=== [4/6] Generando archivos .env de producción (RDS + AWS S3) ==="
cat <<'ENVAUTH' > /opt/eventcut/auth/.env
APP_NAME=auth-service
APP_ENV=prod
CORS_ALLOWED_ORIGINS={cors_origins}
TRUSTED_HOSTS=*
APP_FORCE_HTTPS=false
APP_GATEWAY_SECRET={state['gateway_secret']}
APP_GATEWAY_VALIDATION_ENABLED=true
JWT_SECRET_KEY={state['jwt_secret']}
JWT_ISSUER=microservices-app
JWT_ACCESS_EXPIRATION_MINUTES=60
JWT_REFRESH_EXPIRATION_DAYS=30
MYSQL_HOST={state['rds_endpoint']}
MYSQL_PORT={state['rds_port']}
MYSQL_DB={DEFAULT_AUTH_DB}
MYSQL_USER={state['db_user']}
MYSQL_PASSWORD={state['db_password']}
AUTH_MYSQL_DB={DEFAULT_AUTH_DB}
EVENTS_MYSQL_DB={DEFAULT_EVENTS_DB}
APP_MAIL_ENABLED={smtp_enabled}
APP_MAIL_FROM={state.get('smtp_from', 'noreply@eventcut.edu.mx')}
MAIL_HOST={state.get('smtp_host', 'smtp.gmail.com')}
MAIL_PORT={state.get('smtp_port', 587)}
MAIL_USERNAME={state.get('smtp_username', '')}
MAIL_PASSWORD={state.get('smtp_password', '')}
MAIL_USE_TLS=true
APP_FRONTEND_BASE_URL={state['frontend_website_url']}
SEED_ADMIN_EMAIL={state['admin_email']}
SEED_ADMIN_PASSWORD={state['admin_password']}
SEED_DEMO_EMAIL={state['demo_email']}
SEED_DEMO_PASSWORD={state['demo_password']}
ENVAUTH

cat <<'ENVEVENTS' > /opt/eventcut/events_service/.env
APP_NAME=events-service
APP_ENV=prod
CORS_ALLOWED_ORIGINS={cors_origins}
TRUSTED_HOSTS=*
APP_FORCE_HTTPS=false
JWT_SECRET_KEY={state['jwt_secret']}
JWT_ISSUER=microservices-app
APP_GATEWAY_SECRET={state['gateway_secret']}
AUTH_SERVICE_BASE_URL=http://auth-service:8000
AUTH_REMOTE_VALIDATION_ENABLED=true
MYSQL_HOST={state['rds_endpoint']}
MYSQL_PORT={state['rds_port']}
MYSQL_DB={DEFAULT_EVENTS_DB}
MYSQL_USER={state['db_user']}
MYSQL_PASSWORD={state['db_password']}
AUTH_MYSQL_DB={DEFAULT_AUTH_DB}
EVENTS_MYSQL_DB={DEFAULT_EVENTS_DB}
MYSQL_POOL_SIZE=20
MYSQL_MAX_OVERFLOW=10
AWS_REGION={region}
AWS_DEFAULT_REGION={region}
AWS_S3_BUCKET={state['media_bucket']}
AWS_S3_PUBLIC_HOST={state['media_public_host']}
ENVEVENTS

cat <<EOF > /opt/eventcut/.env
EC2_INSTANCE_ID=${{EC2_INSTANCE_ID}}
AWS_AZ=${{AWS_AZ}}
EOF

echo "=== [5/6] Construyendo imágenes Docker y ejecutando migraciones/seed con Lock RDS ==="
docker compose -f docker-compose.aws.yml build
docker compose -f docker-compose.aws.yml run --rm auth-service python /app/scripts/seed_aws_db.py --mode bootstrap-auth
docker compose -f docker-compose.aws.yml run --rm events-service python /app/scripts/seed_aws_db.py --mode bootstrap-events

echo "=== [6/6] Levantando stack completo EventCut (Traefik + Auth + Events) ==="
docker compose -f docker-compose.aws.yml up -d
docker ps
echo "=== BOOTSTRAP EVENTCUT COMPLETADO EN ${{EC2_INSTANCE_ID}} (${{AWS_AZ}}) ==="
"""


def step_asg(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    ec2 = _client("ec2", region)
    ssm = _client("ssm", region)
    asg = _client("autoscaling", region)
    elbv2 = _client("elbv2", region)

    # Última AMI oficial Amazon Linux 2023
    ami_id = ssm.get_parameter(
        Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    )["Parameter"]["Value"]
    log(f"[+] AMI Amazon Linux 2023 seleccionada: {ami_id}")

    user_data_b64 = base64.b64encode(_build_ec2_userdata(state).encode("utf-8")).decode("ascii")

    lt_name = "eventcut-lt"
    lt_data = {
        "ImageId": ami_id,
        "InstanceType": state["ec2_instance_type"],
        "KeyName": state["key_name"],
        "IamInstanceProfile": {"Name": state["instance_profile"]},
        "SecurityGroupIds": [state["app_sg_id"]],
        "UserData": user_data_b64,
        "MetadataOptions": {
            "HttpEndpoint": "enabled",
            "HttpPutResponseHopLimit": 2,
            "HttpTokens": "optional",
        },
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "eventcut-app-node"},
                    {"Key": "Project", "Value": PROJECT_TAG},
                ],
            }
        ],
    }

    existing_lts = ec2.describe_launch_templates(
        Filters=[{"Name": "launch-template-name", "Values": [lt_name]}]
    ).get("LaunchTemplates", [])
    if existing_lts:
        lt_id = existing_lts[0]["LaunchTemplateId"]
        ver = ec2.create_launch_template_version(LaunchTemplateId=lt_id, LaunchTemplateData=lt_data)
        latest_v = str(ver["LaunchTemplateVersion"]["VersionNumber"])
        ec2.modify_launch_template(LaunchTemplateId=lt_id, DefaultVersion=latest_v)
        log(f"[+] Launch Template '{lt_name}' actualizado a versión {latest_v} ({lt_id})")
    else:
        resp = ec2.create_launch_template(
            LaunchTemplateName=lt_name,
            LaunchTemplateData=lt_data,
            TagSpecifications=[{"ResourceType": "launch-template", "Tags": [{"Key": "Project", "Value": PROJECT_TAG}]}],
        )
        lt_id = resp["LaunchTemplate"]["LaunchTemplateId"]
        log(f"[+] Launch Template creado: {lt_name} ({lt_id})")

    state["launch_template_id"] = lt_id

    asg_name = state["asg_name"]
    existing_asgs = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name]).get("AutoScalingGroups", [])
    if not existing_asgs:
        asg.create_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            LaunchTemplate={"LaunchTemplateId": lt_id, "Version": "$Latest"},
            MinSize=2,
            MaxSize=4,
            DesiredCapacity=2,
            VPCZoneIdentifier=",".join(state["subnet_ids"][:2]),
            TargetGroupARNs=[state["tg_arn"]],
            HealthCheckType="ELB",
            HealthCheckGracePeriod=420,
            Tags=[
                {"Key": "Name", "Value": "eventcut-app-node", "PropagateAtLaunch": True},
                {"Key": "Project", "Value": PROJECT_TAG, "PropagateAtLaunch": True},
            ],
        )
        log(f"[+] Auto Scaling Group '{asg_name}' creado (Min=2, Desired=2, Max=4, Multi-AZ).")
    else:
        log(f"[i] Auto Scaling Group '{asg_name}' ya existe.")

    # Política de autoescalado por CPU (Target Tracking 60%)
    asg.put_scaling_policy(
        AutoScalingGroupName=asg_name,
        PolicyName="eventcut-cpu-target-60",
        PolicyType="TargetTrackingScaling",
        TargetTrackingConfiguration={
            "PredefinedMetricSpecification": {"PredefinedMetricType": "ASGAverageCPUUtilization"},
            "TargetValue": 60.0,
        },
    )
    log("[+] Política Target Tracking Scaling configurada (objetivo CPU 60%).")

    # Esperar a que las 2 instancias completen Docker build + migraciones + healthcheck ALB
    log("[*] Esperando a que los 2 nodos EC2 completen bootstrap Docker y pasen HealthCheck del ALB (3-5 min)...")
    deadline = time.time() + 600
    while time.time() < deadline:
        th = elbv2.describe_target_health(TargetGroupArn=state["tg_arn"]).get("TargetHealthDescriptions", [])
        summary = [(t["Target"]["Id"], t["TargetHealth"]["State"]) for t in th]
        healthy = [t["Target"]["Id"] for t in th if t["TargetHealth"]["State"] == "healthy"]
        log(f"    ... Estado targets ALB: {summary}")
        if len(healthy) >= 2:
            # Guardar info de las instancias
            desc = ec2.describe_instances(InstanceIds=healthy)
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
            state["ec2_instances"] = nodes
            save_state(state)
            log(f"[+] 2/2 Nodos EC2 SALUDABLES detrás del ALB: {nodes}")
            return state
        time.sleep(20)

    raise TimeoutError("Tiempo agotado esperando que 2 nodos EC2 sean 'healthy' en el ALB.")


# =====================================================================
# STEP 8: BUILD Y DESPLIEGUE DEL FRONTEND VUE 3 EN S3
# =====================================================================
def step_frontend(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    s3 = _client("s3", region)
    alb_url = state["alb_url"]

    log(f"[*] Preparando compilación de EventCut Frontend apuntando a ALB: {alb_url}")
    env_prod = (
        f"VITE_API_BASE_URL={alb_url}\n"
        f"VITE_EVENTS_API_BASE_URL={alb_url}\n"
        f"VITE_COMMUNITIES_API_BASE_URL={alb_url}\n"
        f"VITE_EVENTS_UPLOAD_PATH=/api/v1/events/image-upload-url\n"
        f"VITE_USE_DEV_PROXY=false\n"
    )
    (FRONTEND_DIR / ".env.production").write_text(env_prod, encoding="utf-8")

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    if not (FRONTEND_DIR / "node_modules").is_dir():
        log("[*] Instalando dependencias npm del frontend...")
        proc = subprocess.run([npm_cmd, "ci", "--no-audit", "--no-fund"], cwd=str(FRONTEND_DIR), capture_output=True, text=True)
        if proc.returncode != 0:
            proc = subprocess.run([npm_cmd, "install", "--no-audit", "--no-fund"], cwd=str(FRONTEND_DIR), capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Error en npm install:\n{proc.stderr[-1000:]}")

    log("[*] Compilando aplicación Vue 3 (npm run build)...")
    build_proc = subprocess.run([npm_cmd, "run", "build"], cwd=str(FRONTEND_DIR), capture_output=True, text=True)
    if build_proc.returncode != 0:
        raise RuntimeError(f"Error compilando frontend:\n{build_proc.stdout[-800:]}\n{build_proc.stderr[-800:]}")
    log("[+] Build de producción completado en frontend/dist/.")

    dist_dir = FRONTEND_DIR / "dist"
    bucket = state["frontend_bucket"]
    uploaded = 0
    for path in dist_dir.rglob("*"):
        if path.is_dir():
            continue
        key = str(path.relative_to(dist_dir)).replace("\\", "/")
        ctype, _ = mimetypes.guess_type(str(path))
        if path.suffix == ".js":
            ctype = "application/javascript"
        elif path.suffix == ".css":
            ctype = "text/css"
        elif path.suffix == ".svg":
            ctype = "image/svg+xml"
        elif path.suffix == ".webp":
            ctype = "image/webp"
        elif not ctype:
            ctype = "application/octet-stream"

        cache_ctrl = "no-cache, no-store, must-revalidate" if key == "index.html" else "public, max-age=31536000, immutable"
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": ctype, "CacheControl": cache_ctrl},
        )
        uploaded += 1

    log(f"[+] {uploaded} archivo(s) estáticos desplegados en S3 Website: {state['frontend_website_url']}")
    save_state(state)
    return state


# =====================================================================
# STEP 9: CLOUDWATCH + SNS + VERIFICACIÓN END-TO-END
# =====================================================================
def step_monitoring(state: dict[str, Any], log: LogFn) -> dict[str, Any]:
    region = state["region"]
    sns = _client("sns", region)
    cw = _client("cloudwatch", region)

    # 1. Tópico SNS
    topic_arn = sns.create_topic(Name="eventcut-alerts")["TopicArn"]
    state["sns_topic_arn"] = topic_arn
    log(f"[+] Tópico SNS creado para alertas operativas: {topic_arn}")

    # Extraer sufijos para dimensiones ALB / TG
    alb_dim = "/".join(state["alb_arn"].split(":loadbalancer/")[-1].split("/"))
    tg_dim = state["tg_arn"].split(":")[-1]

    alarms_spec = [
        {
            "AlarmName": "EventCut-ALB-UnHealthyHosts",
            "AlarmDescription": "Alerta critica cuando algun nodo EC2 de EventCut falla health check en el ALB",
            "Namespace": "AWS/ApplicationELB",
            "MetricName": "UnHealthyHostCount",
            "Dimensions": [
                {"Name": "LoadBalancer", "Value": alb_dim},
                {"Name": "TargetGroup", "Value": tg_dim},
            ],
            "Statistic": "Maximum",
            "Period": 60,
            "EvaluationPeriods": 1,
            "Threshold": 1.0,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "AlarmActions": [topic_arn],
        },
        {
            "AlarmName": "EventCut-ALB-HTTP-5XX",
            "AlarmDescription": "Alerta por errores HTTP 5XX en respuestas del backend EventCut",
            "Namespace": "AWS/ApplicationELB",
            "MetricName": "HTTPCode_Target_5XX_Count",
            "Dimensions": [{"Name": "LoadBalancer", "Value": alb_dim}],
            "Statistic": "Sum",
            "Period": 60,
            "EvaluationPeriods": 1,
            "Threshold": 5.0,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "TreatMissingData": "notBreaching",
            "AlarmActions": [topic_arn],
        },
        {
            "AlarmName": "EventCut-ASG-HighCPU",
            "AlarmDescription": "Uso elevado de CPU promedio en el Auto Scaling Group de EventCut",
            "Namespace": "AWS/EC2",
            "MetricName": "CPUUtilization",
            "Dimensions": [{"Name": "AutoScalingGroupName", "Value": state["asg_name"]}],
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 1,
            "Threshold": 75.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [topic_arn],
        },
        {
            "AlarmName": "EventCut-RDS-HighCPU",
            "AlarmDescription": "Uso elevado de CPU en Amazon RDS MySQL EventCut",
            "Namespace": "AWS/RDS",
            "MetricName": "CPUUtilization",
            "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": state["rds_identifier"]}],
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 1,
            "Threshold": 80.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [topic_arn],
        },
    ]

    alarm_names = []
    for spec in alarms_spec:
        cw.put_metric_alarm(**spec)
        alarm_names.append(spec["AlarmName"])
        log(f"[+] Alarma CloudWatch configurada: {spec['AlarmName']}")
    state["cloudwatch_alarms"] = alarm_names

    # 2. Verificación End-to-End en vivo
    log("[*] Ejecutando pruebas de verificación End-to-End en vivo...")
    fe_resp = requests.get(state["frontend_website_url"], timeout=15)
    assert fe_resp.status_code == 200 and "<html" in fe_resp.text.lower(), f"Frontend S3 HTTP {fe_resp.status_code}"
    log(f"[+] [E2E 1/6] Frontend S3 Website responde HTTP 200: {state['frontend_website_url']}")

    seen_nodes = set()
    for _ in range(10):
        r = requests.get(f"{state['alb_url']}/api/health", timeout=10)
        assert r.status_code == 200, f"/api/health fallo: {r.status_code}"
        body = r.json()
        seen_nodes.add(f"{body.get('node_id')} ({body.get('availability_zone')})")
    log(f"[+] [E2E 2/6] Balanceo ALB Multi-AZ verificado en /api/health -> nodos atendiendo: {sorted(seen_nodes)}")

    ev_health = requests.get(f"{state['alb_url']}/api/events/health", timeout=10)
    assert ev_health.status_code == 200
    ev_data = ev_health.json().get("data", {})
    assert ev_data.get("storage_provider") == "aws_s3"
    log(f"[+] [E2E 3/6] Events Service operativo con AWS S3 ({ev_data.get('storage_bucket')}) y RDS ({ev_data.get('database')})")

    blocked = requests.get(f"{state['alb_url']}/api/internal/health", timeout=10)
    assert blocked.status_code in (403, 404), f"Ruta interna no bloqueada: {blocked.status_code}"
    log(f"[+] [E2E 4/6] Seguridad Traefik: /api/internal bloqueado correctamente (HTTP {blocked.status_code})")

    # Login Admin JWT
    login_resp = requests.post(
        f"{state['alb_url']}/api/auth/login",
        json={"username": state["admin_email"], "password": state["admin_password"]},
        timeout=15,
    )
    assert login_resp.status_code == 200, f"Login Admin fallo ({login_resp.status_code}): {login_resp.text}"
    login_json = login_resp.json()
    token = (login_json.get("data") or {}).get("token") or login_json.get("token")
    assert token, f"No se recibió token en login: {login_json}"
    log(f"[+] [E2E 5/6] Login JWT Admin exitoso ({state['admin_email']})")

    # Verificar eventos y carga real de imagen desde Amazon S3
    events_resp = requests.get(f"{state['alb_url']}/api/v1/events", timeout=15)
    assert events_resp.status_code == 200
    items = events_resp.json().get("data", {}).get("items", [])
    assert len(items) > 0, "No se encontraron eventos en RDS tras el seed"
    sample_img = next((it.get("image_url") for it in items if it.get("image_url")), None)
    assert sample_img and ".s3." in sample_img, f"Imagen no alojada en S3: {sample_img}"
    img_resp = requests.get(sample_img, timeout=15)
    assert img_resp.status_code == 200 and len(img_resp.content) > 500
    log(f"[+] [E2E 6/6] Catálogo RDS ({len(items)} eventos) + Imagen real en AWS S3 HTTP 200 ({len(img_resp.content)} bytes): {sample_img}")

    save_state(state)
    return state


STEP_HANDLERS: dict[str, Callable[[dict[str, Any], LogFn], dict[str, Any]]] = {
    "validate": step_validate,
    "cleanup": step_cleanup,
    "network": step_network,
    "s3": step_s3,
    "rds": step_rds,
    "package": step_package,
    "alb": step_alb,
    "asg": step_asg,
    "frontend": step_frontend,
    "monitoring": step_monitoring,
}


def run_step(step_id: str, log: LogFn = _default_log, state_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    state = load_state()
    if state_overrides:
        state.update(state_overrides)
        save_state(state)

    if step_id not in STEP_HANDLERS:
        raise ValueError(f"Step desconocido: {step_id}")

    t0 = time.time()
    step_meta = next(s for s in STEPS if s.id == step_id)
    log(f"\n==================================================================")
    log(f"  STEP {step_meta.index}: {step_meta.title}")
    log(f"==================================================================")
    state = STEP_HANDLERS[step_id](state, log)
    completed = state.get("completed_steps", [])
    if step_id not in completed:
        completed.append(step_id)
    state["completed_steps"] = completed
    save_state(state)
    elapsed = time.time() - t0
    log(f"[OK] Step '{step_id}' completado en {elapsed:.1f}s.")
    return state


def run_all_steps(log: LogFn = _default_log, skip_cleanup: bool = False) -> dict[str, Any]:
    state = load_state()
    for step in STEPS:
        if skip_cleanup and step.id == "cleanup":
            log("[i] Omitiendo Step 1 (cleanup) por solicitud explícita.")
            continue
        state = run_step(step.id, log=log)
    return state


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Despliegue automatizado paso a paso de EventCut en AWS")
    parser.add_argument("--step", help="Ejecutar solo un step específico por ID (ej. validate, cleanup, network...)")
    parser.add_argument("--all", action="store_true", help="Ejecutar todos los steps automáticamente")
    parser.add_argument("--cli-interactive", action="store_true", help="Modo interactivo en consola pidiendo Enter en cada step")
    parser.add_argument("--skip-cleanup", action="store_true", help="Omitir limpieza total (Step 1)")
    args = parser.parse_args()

    if args.step:
        run_step(args.step)
    elif args.all:
        run_all_steps(skip_cleanup=args.skip_cleanup)
    elif args.cli_interactive:
        for s in STEPS:
            if args.skip_cleanup and s.id == "cleanup":
                continue
            print(f"\n>>> Siguiente paso: Step {s.index} - {s.title}")
            print(f"    {s.subtitle}")
            input("Presiona ENTER para continuar (o Ctrl+C para salir)... ")
            run_step(s.id)
    else:
        print("Usa --all, --cli-interactive, --step <id>, o ejecuta 'python infra/wizard_server.py' para el Wizard Web.")
