# Server Backend Configuration — Novum

> Estado actual de la VM de backend en Hetzner. Documento operativo: cómo acceder, qué quedó instalado, dónde vive cada cosa.
>
> **Última actualización:** 2026-05-26
>
> ⚠️ Este archivo NO debe contener secretos (passwords, tokens). Los secretos viven en `api_key_services.txt` (gitignored).

---

## 0. Cheatsheet · comandos rápidos

> Todos requieren `sudo` (o ejecutar como `root`). Pegar y listo.

### Conectarse al server

```powershell
# Como novum (uso normal)
ssh -i C:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle novum@88.198.91.119

# Como root (administración)
ssh -i C:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle root@88.198.91.119
```

### Estado global

```bash
# Ver todos los servicios de Novum de un vistazo
sudo systemctl status postgresql@16-main caddy novum fail2ban ssh --no-pager

# Uso de recursos
free -h
df -h
htop                    # Ctrl+C para salir
```

### PostgreSQL

```bash
sudo systemctl start    postgresql@16-main
sudo systemctl stop     postgresql@16-main
sudo systemctl restart  postgresql@16-main
sudo systemctl reload   postgresql@16-main      # recarga config sin cortar conexiones
sudo systemctl status   postgresql@16-main --no-pager

sudo journalctl -u postgresql@16-main -f         # logs live (Ctrl+C para salir)
sudo tail -f /var/log/postgresql/postgresql-16-main.log

sudo -u postgres psql                            # entrar como superuser
```

### Caddy (reverse proxy + TLS)

```bash
sudo systemctl start    caddy
sudo systemctl stop     caddy
sudo systemctl restart  caddy
sudo systemctl reload   caddy                    # recarga Caddyfile (preferido)
sudo systemctl status   caddy --no-pager

sudo caddy validate --config /etc/caddy/Caddyfile
sudo journalctl -u caddy -f
```

### Backend Novum (uvicorn / FastAPI)

```bash
sudo systemctl start    novum
sudo systemctl stop     novum
sudo systemctl restart  novum
sudo systemctl status   novum --no-pager

sudo journalctl -u novum -f
```

### fail2ban

```bash
sudo systemctl start    fail2ban
sudo systemctl stop     fail2ban
sudo systemctl restart  fail2ban
sudo systemctl status   fail2ban --no-pager

sudo fail2ban-client status                      # lista jails activas
sudo fail2ban-client status sshd
sudo fail2ban-client status postgresql
sudo fail2ban-client set postgresql unbanip <IP>
sudo fail2ban-client set sshd unbanip <IP>
```

### ufw (firewall host)

```bash
sudo ufw status verbose
sudo ufw status numbered
sudo ufw reload
sudo ufw allow <port>/tcp
sudo ufw delete <number>
sudo ufw disable                                 # ⚠️ usar solo si te dejas fuera
sudo ufw enable
```

### SSH

```bash
sudo systemctl restart  ssh
sudo systemctl status   ssh --no-pager
sudo journalctl -u ssh -f
```

### Reinicio completo del stack

```bash
sudo systemctl restart postgresql@16-main
sudo systemctl restart novum
sudo systemctl reload  caddy
```

### Reinicio del server completo

```bash
sudo reboot
```

---

## 1. Provider y VM

| Item | Valor |
|---|---|
| Proveedor | **Hetzner Cloud** |
| Tipo | **CAX11** (ARM Ampere) |
| vCPU / RAM / Disco | 2 ARM / 4 GB / 40 GB SSD |
| Datacenter | **Ashburn, VA (US East)** |
| OS | **Ubuntu 26.04 LTS ARM64** |
| Hostname | `novum-prod` |
| IPv4 pública | `88.198.91.119` |
| Coste mensual | ~€3.29 (~$4 USD) |

---

## 2. Acceso SSH

### Llave SSH

| Item | Valor |
|---|---|
| Algoritmo | ED25519 |
| Archivo privado | `c:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle` |
| Archivo público | `c:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle.pub` |
| Passphrase | (sin passphrase en V1) |

### Comandos de conexión

Como **root** (administración del sistema):
```powershell
ssh -i C:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle root@88.198.91.119
```

Como **novum** (uso normal de la app):
```powershell
ssh -i C:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle novum@88.198.91.119
```

### Alias recomendado en `~/.ssh/config`

Para no escribir la ruta cada vez:

```sshconfig
Host novum
  HostName 88.198.91.119
  User novum
  IdentityFile C:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle

Host novum-root
  HostName 88.198.91.119
  User root
  IdentityFile C:\Users\HarolGiovannyManchol\source\repos\novum\.ssh\novum_oracle
```

Después: `ssh novum` o `ssh novum-root`.

---

## 3. Firewall (dos capas)

### Capa 1 · Hetzner Cloud Firewall (`novum-fw`)

Asociado al server `novum-prod`. Filtra antes de que el paquete llegue a la VM.

#### Inbound rules

| # | Protocol | Port | Source IPs | Propósito |
|---|---|---|---|---|
| 1 | TCP | 22 | `181.51.0.0/16` | SSH solo desde mi ISP |
| 2 | TCP | 80 | `0.0.0.0/0, ::/0` | HTTP (redirect a HTTPS por Caddy) |
| 3 | TCP | 443 | `0.0.0.0/0, ::/0` | HTTPS público |
| 4 | TCP | 5432 | `0.0.0.0/0, ::/0` | Postgres público (admin con pgAdmin, TLS forzado) |
| 5 | ICMP | — | `0.0.0.0/0, ::/0` | Ping (debug) |

#### Outbound rules

**Sin reglas** → todo el tráfico saliente está permitido (necesario para GitHub Models, Tavily, Wikipedia, apt, Let's Encrypt).

> Si tu IP pública cambia (`181.51.x.x` deja de funcionar), edita la regla 1 en el panel de Hetzner.

### Capa 2 · `ufw` en la VM (defense in depth)

Filtra dentro del kernel del host. Política por defecto: `deny incoming`, `allow outgoing`.

```bash
sudo ufw status verbose
```

| Port | Protocol | Source | Propósito |
|---|---|---|---|
| 22 | TCP | `181.51.0.0/16` | SSH |
| 80 | TCP | Any | HTTP |
| 443 | TCP | Any | HTTPS |
| 5432 | TCP | Any | Postgres (TLS forzado a nivel de pg_hba) |

Comandos típicos:
```bash
sudo ufw status numbered
sudo ufw allow <port>/tcp
sudo ufw delete <number>
sudo ufw reload
```

---

## 4. Usuarios del sistema

### `root`
- Acceso SSH habilitado con la misma llave pública.
- Usar solo para: instalar paquetes, editar archivos en `/etc/`, gestionar `systemd`.

### `novum`
- Usuario sin password (`--disabled-password`).
- Miembro del grupo `sudo` → puede `sudo <cmd>` sin pedir contraseña (porque no tiene).
- Home: `/home/novum/`
- Shell: `/bin/bash`
- Llave SSH copiada de root → `/home/novum/.ssh/authorized_keys`
- Es el **usuario que ejecuta uvicorn y posee el código de la app**.

---

## 5. Swap

Configurado para dar margen a Postgres + uvicorn en 4 GB de RAM.

| Item | Valor |
|---|---|
| Archivo | `/swapfile` |
| Tamaño | 2 GB |
| Persistencia | Sí (`/etc/fstab`) |

Verificar:
```bash
swapon --show
free -h
```

---

## 6. PostgreSQL 16

### Instalación

- Repo: **PGDG oficial** (`https://apt.postgresql.org/pub/repos/apt`).
- Paquetes: `postgresql-16`, `postgresql-client-16`.
- Servicio systemd real: `postgresql@16-main.service`.
- Wrapper: `postgresql.service` (siempre aparece "exited", es normal).

### Cluster

| Item | Valor |
|---|---|
| Versión | 16.x |
| Cluster name | `main` |
| Puerto | `5432` (expuesto en `0.0.0.0` con TLS forzado) |
| Data dir | `/var/lib/postgresql/16/main/` |
| Config | `/etc/postgresql/16/main/postgresql.conf` |
| HBA | `/etc/postgresql/16/main/pg_hba.conf` |
| Socket | `/var/run/postgresql/.s.PGSQL.5432` |

### Tuning aplicado (final del `postgresql.conf`)

```conf
# === Novum tuning (CAX11 4GB) ===
listen_addresses = '*'
ssl = on
shared_buffers = 512MB
work_mem = 8MB
maintenance_work_mem = 64MB
effective_cache_size = 1500MB
max_connections = 30
wal_buffers = 8MB

# Logging (necesario para fail2ban + auditoría)
log_connections = on
log_line_prefix = '%m [%p] %q%u@%d host=%h '
```

### Acceso remoto (pg_hba.conf)

Reglas relevantes añadidas al final:

```
hostssl  novum   novum   0.0.0.0/0   scram-sha-256
hostssl  novum   novum   ::/0        scram-sha-256
```

- `hostssl` → rechaza conexiones sin TLS.
- `scram-sha-256` → hashing moderno del password.
- Cliente debe conectarse con `sslmode=require` (o superior).

### Conexión desde pgAdmin (admin remoto)

| Campo | Valor |
|---|---|
| Host | `88.198.91.119` |
| Port | `5432` |
| Maintenance DB | `novum` |
| Username | `novum` |
| Password | en `api_key_services.txt` |
| SSL Mode | **Require** (mínimo) |
| SSH Tunnel | **OFF** |

> ⚠️ El password actual (`Universal.00`) es débil. Pendiente rotarlo a aleatorio de 32 chars antes de demo day.

### Base de datos y usuario

| Item | Valor |
|---|---|
| Database | `novum` |
| Owner | `novum` |
| Encoding | UTF8 |
| Password | en `api_key_services.txt` (NO commitear) |

### Connection strings

Para la app (en la misma VM, vía socket/localhost):
```
postgresql+asyncpg://novum:<PASSWORD>@localhost:5432/novum
```

Para herramientas externas (pgAdmin, psql desde otra máquina):
```
postgresql://novum:<PASSWORD>@88.198.91.119:5432/novum?sslmode=require
```

### Comandos útiles

```bash
# Estado
sudo systemctl status postgresql@16-main --no-pager

# Reiniciar
sudo systemctl restart postgresql@16-main

# Logs
sudo journalctl -u postgresql@16-main -f
sudo tail -f /var/log/postgresql/postgresql-16-main.log

# psql como superuser
sudo -u postgres psql

# psql como app user
PGPASSWORD='<password>' psql -h localhost -U novum -d novum
```

---

## 7. Python / uv

### Python del sistema (NO usar para la app)
- Ubuntu 26.04 trae **Python 3.14.4** como `python3` por defecto.
- Lo dejamos intacto: varios paquetes del sistema dependen de él.

### Python del proyecto (lo que usa la app)
- Instalado por **uv** como binario standalone (no toca apt).
- Versión: **3.12** (locked en `tech-stack.md`).

### `uv` (instalado para el usuario `novum`)

| Item | Valor |
|---|---|
| Binario | `/home/novum/.local/bin/uv` |
| Instalación | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (como `novum`) |

Comandos típicos como `novum`:
```bash
cd ~/novum-backend
uv sync           # instala dependencias
uv run uvicorn app:app --host 127.0.0.1 --port 8000
uv add <package>  # añade dependencia
```

---

## 8. Caddy v2

Reverse proxy + TLS automático (Let's Encrypt).

### Instalación
- Repo Cloudsmith oficial de Caddy.
- Paquete: `caddy`.

### Archivos

| Path | Propósito |
|---|---|
| `/etc/caddy/Caddyfile` | Configuración principal |
| `/var/lib/caddy/` | Estado interno (certificados, autosave) |
| `/etc/systemd/system/caddy.service` | systemd unit (provista por el paquete) |

> **No usar `log { output file ... }` en el Caddyfile** — el systemd unit tiene `ProtectSystem=full` y bloquea escritura a `/var/log/`. Para ver logs usar `journalctl -u caddy -f`.

### Caddyfile actual

```caddy
novum-prod.duckdns.org {
    encode gzip

    @sse path /events/* /api/runs/*/stream
    handle @sse {
        reverse_proxy localhost:8000 {
            flush_interval -1
            transport http {
                read_timeout 24h
            }
        }
    }

    handle /api/* {
        reverse_proxy localhost:8000
    }

    handle /health {
        reverse_proxy localhost:8000
    }

    handle {
        respond "Not found" 404
    }
}
```

### Comandos útiles

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
sudo journalctl -u caddy -f
```

---

## 9. Dominio (DuckDNS)

| Item | Valor |
|---|---|
| Subdominio | `novum-prod.duckdns.org` |
| Apunta a | `88.198.91.119` |
| Login | GitHub OAuth |
| Token | en `api_key_services.txt` (para script de auto-update si fuera necesario) |
| Renovación TLS | automática vía Caddy (Let's Encrypt) |

> La IP de Hetzner no cambia, así que no necesitamos cron de auto-update por ahora.

---

## 10. Aplicación FastAPI (estado actual: dummy)

### Ubicación

| Item | Valor |
|---|---|
| Dueño | usuario `novum` |
| Path | `/home/novum/novum-backend/` |
| Entrypoint | `app:app` (objeto FastAPI en `app.py`) |
| Bind | `127.0.0.1:8000` (solo localhost; Caddy proxea) |
| Workers | 1 (locked por RF-05) |

### Estado actual

App **mínima** con solo `/health`. Se reemplazará por el código real en cuanto comencemos el build del backend.

```python
from fastapi import FastAPI
from datetime import datetime, timezone

app = FastAPI()
START_TS = datetime.now(timezone.utc)

@app.get("/health")
def health():
    return {"ok": True, "service": "novum-backend", "started_at": START_TS.isoformat()}
```

### systemd unit · `/etc/systemd/system/novum.service`

```ini
[Unit]
Description=Novum FastAPI backend
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=novum
Group=novum
WorkingDirectory=/home/novum/novum-backend
Environment="PATH=/home/novum/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/novum/.local/bin/uv run uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Comandos útiles

```bash
sudo systemctl status novum --no-pager
sudo systemctl restart novum
sudo systemctl stop novum
sudo journalctl -u novum -f
```

---

## 11. Verificación end-to-end

Desde cualquier cliente externo:

```powershell
curl https://novum-prod.duckdns.org/health
```

**Respuesta esperada:**
```json
{"ok":true,"service":"novum-backend","started_at":"2026-05-26T07:25:55+00:00"}
```

Cadena que recorre el request:

```
Cliente → DNS (DuckDNS) → 88.198.91.119:443 → Caddy (TLS) → 127.0.0.1:8000 → uvicorn → FastAPI
```

---

## 12. fail2ban

Mitiga fuerza bruta sobre SSH y Postgres. Detecta IPs con muchos fallos seguidos y las banea con `iptables`.

### Configuración

#### `/etc/fail2ban/jail.local`

```ini
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5
backend  = systemd

[sshd]
enabled = true
port    = ssh
logpath = %(sshd_log)s

[postgresql]
enabled  = true
port     = 5432
filter   = postgresql
logpath  = /var/log/postgresql/postgresql-16-main.log
backend  = auto
maxretry = 5
bantime  = 1h
findtime = 10m
```

#### `/etc/fail2ban/filter.d/postgresql.conf`

```ini
[Definition]

failregex = ^.*host=<HOST>\s+FATAL:\s+password authentication failed for user.*$
            ^.*host=<HOST>\s+FATAL:\s+no pg_hba\.conf entry.*$

ignoreregex =

datepattern = ^%%Y-%%m-%%d %%H:%%M:%%S
```

> Requisito: `log_line_prefix` debe incluir `host=%h` para que el regex encuentre la IP en cada línea FATAL.

### Comandos útiles

```bash
sudo systemctl status fail2ban --no-pager
sudo fail2ban-client status                  # lista de jails activas
sudo fail2ban-client status sshd
sudo fail2ban-client status postgresql
sudo fail2ban-client set postgresql unbanip <IP>
sudo fail2ban-regex /var/log/postgresql/postgresql-16-main.log /etc/fail2ban/filter.d/postgresql.conf
```

---

## 13. Servicios systemd · resumen

| Servicio | Estado esperado | Logs |
|---|---|---|
| `postgresql@16-main.service` | active (running) | `journalctl -u postgresql@16-main` |
| `caddy.service` | active (running) | `journalctl -u caddy` |
| `novum.service` | active (running) | `journalctl -u novum` |
| `ssh.service` | active (running) | `journalctl -u ssh` |
| `fail2ban.service` | active (running) | `journalctl -u fail2ban` |
| `ufw.service` | active | `sudo ufw status verbose` |

Todos están con `enable` → arrancan al boot.

---

## 14. Puntos abiertos / mejoras V2

- [x] **`ufw` interno** como segunda capa de firewall (defense in depth).
- [x] **fail2ban** para SSH y Postgres (mitigación de fuerza bruta).
- [ ] **Rotar password de Postgres** a aleatorio de 32 chars (actual `Universal.00` es débil).
- [ ] **`PasswordAuthentication no`** en `/etc/ssh/sshd_config` (solo llaves).
- [ ] **Backups de Postgres** (cron diario con `pg_dump` → `/backup/`).
- [ ] **Off-host backup** (rsync a Hetzner Storage Box, ~€3/mes por 1 TB).
- [ ] **Cron de auto-update DuckDNS** (innecesario hoy, util si migramos a IP dinámica).
- [ ] **Snapshot semanal** del volumen (servicio Hetzner, ~€0.66/mes).
- [ ] **CI/CD** GitHub Actions → `rsync` + `systemctl restart novum` (decisión pendiente #2 en `infrastructure.md`).
- [ ] **Monitoring externo** (UptimeRobot free) antes de demo day.

---

## 15. Procedimientos de recuperación

### Si SSH se cae (firewall mal configurado)
1. Entrar a Hetzner Cloud Console → Server → **Console** (web VNC).
2. Login con root + password (si lo tienes) o usar **rescue mode**.
3. Editar `/etc/ufw/...` o el firewall del panel de Hetzner.

### Si uvicorn deja de arrancar
```bash
sudo journalctl -u novum --no-pager -n 50
sudo systemctl restart novum
```

### Si Postgres deja de arrancar
```bash
sudo journalctl -u postgresql@16-main --no-pager -n 50
# Causa típica: typo en postgresql.conf → revertir al último valor conocido bueno
```

### Si Caddy no levanta TLS
- Verifica que DuckDNS resuelve a `88.198.91.119`: `nslookup novum-prod.duckdns.org`
- Verifica que el firewall tiene 80 y 443 abiertos a `0.0.0.0/0`.
- Logs: `journalctl -u caddy -f`.

### Reinicio completo del stack
```bash
sudo systemctl restart postgresql@16-main
sudo systemctl restart novum
sudo systemctl reload caddy
```

---

## 16. Costo mensual recurrente

| Concepto | Coste |
|---|---|
| Hetzner CAX11 | €3.29 |
| IPv4 pública | incluida |
| Tráfico (20 TB incluidos) | €0 |
| Snapshots | €0 (sin activar) |
| Backups Hetzner | €0 (sin activar) |
| DuckDNS | €0 |
| Let's Encrypt (vía Caddy) | €0 |
| **Total** | **~€3.29 / mes** |
