# Guía — Conexión al backend y lectura de logs

Servidor de producción: **Hetzner** — `novum@88.198.91.119`
Servicio systemd: **`novum`** (uvicorn) detrás de **Caddy**
Llave SSH (repo local): **`.ssh\novum_oracle`**
Health URL: https://novum-prod.duckdns.org/health

> Todos los comandos se ejecutan desde la raíz del repo (`C:\Users\HarolGiovannyManchol\source\repos\novum`) en PowerShell.

---

## 1. Conexión SSH interactiva

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119
```

Una vez dentro puedes usar directamente:
```bash
sudo journalctl -u novum -f -o cat
```

---

## 2. Logs en vivo (tail -f, streaming)

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum -f -o cat"
```

`Ctrl+C` para salir.

---

## 3. Últimas N líneas (snapshot rápido)

```powershell
# Últimas 200 líneas
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum -n 200 --no-pager -o cat"
```

---

## 4. Logs por ventana temporal

```powershell
# Última hora
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum --since '1 hour ago' --no-pager -o cat"

# Últimos 15 minutos
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum --since '15 min ago' --no-pager -o cat"

# Desde fecha/hora concreta
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum --since '2026-05-27 10:00' --no-pager -o cat"
```

---

## 5. Filtrar solo errores / tracebacks

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum -n 500 --no-pager -o cat | grep -iE 'error|traceback|exception|critical'"
```

---

## 6. Estado del servicio + health check

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "systemctl is-active novum && systemctl status novum --no-pager -l | head -n 20 && curl -s -o /dev/null -w 'health=%{http_code}\n' https://novum-prod.duckdns.org/health"
```

Esperado: `active` + `health=200`.

---

## 7. Logs de Caddy (reverse proxy)

Útil cuando `novum` está `active` pero el health devuelve 502/504.

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u caddy -n 100 --no-pager -o cat"
```

---

## 8. Guardar logs a archivo local

```powershell
# Volcar últimas 1000 líneas a un .txt local
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo journalctl -u novum -n 1000 --no-pager -o cat" > novum-prod.log
```

---

## 9. Reinicio del servicio (si está caído)

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "sudo systemctl restart novum && sleep 3 && systemctl is-active novum && curl -s -o /dev/null -w '%{http_code}\n' https://novum-prod.duckdns.org/health"
```

Esperado: `active` + `200`.

---

## 10. Deploy completo (referencia — desde `novum-deploy-discipline.md`)

```powershell
ssh -i .ssh\novum_oracle -o StrictHostKeyChecking=no novum@88.198.91.119 "cd /home/novum/novum-backend && git fetch origin && git reset --hard origin/main && sudo systemctl restart novum && sleep 3 && systemctl is-active novum && curl -s -o /dev/null -w '%{http_code}' https://novum-prod.duckdns.org/health"
```

Tail esperado: `active\n200`. Cualquier otra cosa → roll back.

---

## Tips

- **`-o cat`** quita el prefijo `hostname systemd[...]:` y deja solo el mensaje (más legible).
- **`--no-pager`** evita que journalctl se quede esperando en `less` cuando se invoca por SSH.
- Si ves `Permission denied (publickey)`, revisa que `.ssh\novum_oracle` exista y tenga permisos correctos.
- Si el comando SSH cuelga, agrega `-o ConnectTimeout=10`.
