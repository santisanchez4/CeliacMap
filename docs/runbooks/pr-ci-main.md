# Ramas, PR, CI y protección de main

Estado: 02-10-2026. El workflow se incorpora con este PR; la protección de `main` la activa el responsable desde GitHub. Consulta de lectura de la API: `Branch not protected`; no se cambia esa configuración por API.

## Activar la protección

El repositorio es público; GitHub Free admite protección de ramas públicas, sin cuenta de organización. Una vez que este PR haya ejecutado CI:

1. Abrir [Settings → Branches](https://github.com/santisanchez4/CeliacMap/settings/branches) → **Add classic branch protection rule**.
2. Patrón: `main`.
3. Activar **Require a pull request before merging**. Si trabajás solo, dejar **Require approvals** desmarcado: no podés aprobar tu propio PR. Exigir una aprobación cuando exista otro revisor.
4. Activar **Require status checks to pass before merging**, elegir **CI required** (origen GitHub Actions) y **Require branches to be up to date before merging**. Si el check no aparece, esperar la primera ejecución de este PR y recargar.
5. Activar **Require conversation resolution before merging** y **Do not allow bypassing the above settings**.
6. Dejar desmarcados **Allow force pushes** y **Allow deletions**. Guardar la regla.

Fuente: [GitHub — Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule), consultada 02-10-2026.

No exigir un despliegue a producción antes del merge: Pages se ejecuta después. No habilitar merge queue con esta configuración; requeriría agregar el evento `merge_group` a CI. Verificar después que un PR con CI fallido no permita merge. Sin protección, el workflow informa fallos pero no impide por sí solo un push directo a `main`.

## Trabajo diario

1. Con el árbol limpio, actualizar `main` y crear una rama por tarea:

   ```bash
   git switch main
   git pull --ff-only origin main
   git switch -c feat/nombre-de-tarea
   ```

2. Cambiar lo necesario, probar localmente y agregar archivos explícitos al commit. No agregar `.env`, resultados locales ni datos personales.
3. Hacer commit, `git push -u origin feat/nombre-de-tarea` y abrir PR contra `main`, describiendo problema, resultado, pruebas y riesgos.
4. Esperar **Pytest**, **Deno Edge Functions**, **Frontend** y **CI required** en verde. CI corre también para PR de documentación y borradores; no hay filtros de paths.
5. Revisar el diff. Si `main` avanzó, actualizar la rama y esperar CI nuevamente. El responsable hace merge cuando esté listo; crear un PR no autoriza su merge ni un despliegue manual.
6. Después del merge, actualizar el checkout local y eliminar la rama terminada cuando corresponda.

El flujo futuro del piloto será: rama → PR → suite → merge → build PWA/APK → prueba interna. Los builds y la distribución móvil todavía no están implementados.

## Qué verifica CI

[ci.yml](../../.github/workflows/ci.yml) ejecuta tres jobs independientes: Python 3.12 con todas las pruebas de `tests/`, Deno 2.9.4 con todas las pruebas de `supabase/functions/`, y las pruebas DOM del frontend. `CI required` corre incluso si una suite falla o se omite, y solo aprueba si las tres terminaron en `success`.

No utiliza secretos ni credenciales de producción. Las APIs están simuladas; la descarga inicial de dependencias necesita red. `deno.lock` fija las dependencias y `--frozen` impide resolver versiones nuevas silenciosamente. Resend necesita leer `RESEND_BASE_URL` y `RESEND_USER_AGENT` al importar su SDK: solo esas variables reciben permiso; no se concede red a los tests Deno.

Comandos locales, después de instalar Python/dependencias y Deno:

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q
deno test --frozen --node-modules-dir=none --allow-read --allow-env=RESEND_BASE_URL,RESEND_USER_AGENT supabase/functions/
deno test --frozen --node-modules-dir=none --allow-read tests/frontend_*.test.js
```

El frontend no tiene build ni linter configurados; estos tests verifican comportamiento DOM, contratos y copy, sin reemplazar QA visual en navegador. La configuración de dependencias Python conserva los rangos existentes; una actualización puede provocar un fallo legítimo que se debe investigar, no omitir.

## Gate del despliegue

[deploy-pages.yml](../../.github/workflows/deploy-pages.yml) llama al mismo CI, desde el mismo commit, antes de preparar y publicar el sitio. `deploy` depende del resultado exitoso de `tests`. Tanto la llamada como el despliegue están restringidos a `refs/heads/main`, incluido `workflow_dispatch`. Solo el job de publicación recibe permisos `pages: write` e `id-token: write`.

Se conservan los triggers de cambios del frontend y se añade el workflow CI. Un merge de este PR puede activar Pages porque modifica sus workflows; en esta tarea se deja el PR abierto, sin merge ni dispatch. Un fallo o cancelación impide publicar. No se reutiliza un resultado verde de otro commit.

Fuente del mecanismo: [GitHub — Reuse workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows), consultada 02-10-2026.

El gate cubre GitHub Pages, no los workflows operativos de agentes ni despliegues manuales de Edge Functions; cualquier automatización futura de release móvil/Edge debe depender también de esta suite.
