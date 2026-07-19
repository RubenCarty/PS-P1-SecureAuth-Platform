# Guía de Contribución — PS-P1 SecureAuth Platform

## Regla fundamental

> **TODOS los integrantes del grupo DEBEN abrir su propio Pull Request cada semana.**
> Si no hay PR tuyo → no tienes entrega → no tienes nota esa semana.
> El líder no puede subir el trabajo de todos. Cada uno sube el suyo.

---

## Estructura de tu entrega semanal

Cada semana trabajas en la carpeta:

```
semana-XX/TU_APELLIDO_NOMBRE/
```

Ejemplo para la semana 3:
```
semana-03/
├── GARCIA_JUAN/
│   ├── avance_s03.md          ← Tu aporte específico esta semana
│   ├── codigo/                ← Tu código (si te tocó desarrollar)
│   └── evidencia/             ← Capturas de lo que hiciste
├── LOPEZ_MARIA/
│   └── ...
```

---

## Flujo para hacer tu PR semanal

```bash
# 1. Clona el repo (solo la primera vez)
git clone https://github.com/TU_USUARIO/PS-P1-SecureAuth-Platform.git
cd PS-P1-SecureAuth-Platform

# 2. Conecta con el repo del grupo (solo la primera vez)
git remote add upstream https://github.com/[LIDER]/PS-P1-SecureAuth-Platform.git

# 3. Antes de empezar cada semana, actualiza tu copia
git fetch upstream
git merge upstream/main
git push origin main

# 4. Crea tu carpeta y trabaja
mkdir -p semana-03/APELLIDO_NOMBRE

# 5. Guarda tu avance
git add semana-03/APELLIDO_NOMBRE/
git commit -m "feat(s03): [descripción de tu aporte] - APELLIDO NOMBRE"
git push origin main

# 6. Abre el PR hacia el repo del grupo
# → GitHub.com → Pull Request → base: repo del grupo
```

---

## Convención de commits

```
feat(s02): implementa endpoint de login con bcrypt - GARCIA JUAN
fix(s03): corrige SQL injection en búsqueda de usuarios - LOPEZ MARIA
docs(s04): documenta arquitectura de sesiones - QUISPE CARLOS
test(s05): agrega tests de cifrado AES-GCM - TORRES ANA
```

---

## División de roles sugerida por semana

| Semana | Rol 1 (Lider) | Rol 2 (DB) | Rol 3 (API) | Rol 4 (QA) | Rol 5 (Docs) |
|:---:|---|---|---|---|---|
| S01 | Arquitectura | Esquema BD | Endpoints draft | Test plan | README + Spec |
| S02 | Login core | User model | Auth endpoints | Tests login | Documentar API |
| S03 | Validación | Migrations | Input sanitization | Tests inyección | Actualizar docs |
| S04 | Session mgmt | Session store | RBAC endpoints | Tests sesión | Diagrama RBAC |
| S05 | TOTP integración | MFA model | MFA endpoints | Tests MFA | Guía de usuario |
| S06 | JWT service | Token store | JWT endpoints | Tests JWT | API reference |
| S07 | CI/CD setup | DB security | API hardening | SAST/DAST | Reporte técnico |
| S08 | Auditoría | Revisión BD | Revisión API | Pen test | Presentación |

---

## Lo que NO se permite

- Subir contraseñas, API keys o tokens reales
- Subir archivos `.env` con datos reales
- Subir claves privadas (`.key`, `.pem`, `.p12`)
- Hacer push directo a `main` (todo va por PR)
- Hacer el PR por otro compañero

---

## Checklist de tu PR semanal

Antes de abrir el PR, verifica:

- [ ] Mi carpeta: `semana-XX/APELLIDO_NOMBRE/`
- [ ] Incluye `avance_s03.md` con descripción de lo que hice
- [ ] El código tiene comentarios de seguridad
- [ ] No incluyo archivos sensibles
- [ ] El commit message sigue la convención
- [ ] Completé el formulario del PR

---

*DD281 Programación Segura — Universidad Autónoma del Perú — 2026-1*
