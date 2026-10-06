# APK de demostración (Android) — compilar, firmar, instalar y probar

La app Android es la misma web empaquetada con Capacitor (`apps/mobile/`). Se distribuye como archivo APK para demos:
**sin Play Store, sin CI y sin publicar el archivo en una URL pública.** Decisión y alcance: [DECISIONS](../DECISIONS.md#android-demo-app-with-capacitor-2026-10-03).

## 1. Qué hay instalado en la PC (opción «línea de comandos», sin Android Studio)

| Qué | Dónde | Peso aprox. |
|---|---|---:|
| Android SDK: cmdline-tools, platform-tools (`adb`), plataforma 36, build-tools 35 y 36 | `%LOCALAPPDATA%\Android\Sdk` | 0,6 GB |
| Gradle 8.14.3 y dependencias descargadas en el primer build | `%USERPROFILE%\.gradle` | 1–1,5 GB |
| Paquetes de Capacitor | `apps/mobile/node_modules` | 30 MB |
| JDK 21 (ya estaba) | `C:\Program Files\Android\openjdk\jdk-21.0.8` | — |

Node ≥ 22 (Capacitor 8). El `java` del PATH puede ser otro: el build usa `JAVA_HOME` apuntando al JDK 21.

## 2. Compilar

Desde `apps/mobile/`, en Git Bash:

```bash
export JAVA_HOME="/c/Program Files/Android/openjdk/jdk-21.0.8"
export ANDROID_HOME="$LOCALAPPDATA/Android/Sdk"
npm ci                 # solo la primera vez o si cambia package-lock.json
npm run build:release  # copia la web a www/, sincroniza Capacitor y compila
```

Resultado: `apps/mobile/android/app/build/outputs/apk/release/app-release.apk`, firmado si existe la clave (§3).
`npm run build:debug` genera `…/debug/app-debug.apk`, que permite inspeccionar la app con `chrome://inspect`; lleva otra
firma, así que **no se instala encima del release** (hay que desinstalar antes).

`www/` es una copia generada (nunca se versiona): `index.html` sin el beacon de Cloudflare ni el enlace al manifest,
`privacidad.html` y `terminos.html` tal cual (no cargan scripts), `css/`, `js/`, `assets/` y `native.js`. Si el beacon o el manifest cambian de lugar en `index.html`, el build se detiene.

Antes de cada APK nuevo: subir `versionCode` (entero, siempre mayor) y `versionName` en `apps/mobile/android/app/build.gradle`.

## 3. Clave de firma — fuera del repo

Generada el 2026-10-03. **Sin estos dos archivos no se puede actualizar la app ya instalada** (habría que desinstalarla y
reinstalar con otra firma):

| Archivo | Qué es |
|---|---|
| `%USERPROFILE%\celiacmap-signing\celiacmap-release.jks` | La clave (PKCS12, RSA 2048, alias `celiacmap`, válida 10 000 días) |
| `%USERPROFILE%\celiacmap-signing\keystore.properties` | Ruta de la clave, alias y contraseña (aleatoria de 32 caracteres; solo está en este archivo) |

Respaldar **los dos** en un lugar fuera de esta PC (gestor de contraseñas con adjuntos o un pendrive guardado). No
mandarlos por mail ni chat, no copiarlos al repo: `.gitignore` rechaza `*.jks`, `*.keystore` y `keystore.properties`.
Huella SHA-256 del certificado: `43:7C:77:60:12:02:86:AE:0F:6F:4B:26:7D:31:01:82:8F:FD:79:07:9A:BB:56:D6:60:0C:45:82:0C:DA:4B:03`.

El build busca `keystore.properties` en esa carpeta, o en la ruta de la variable `CELIACMAP_KEYSTORE_PROPERTIES`. Si no
existe, `assembleRelease` deja un APK sin firmar que Android no instala.

Verificar la firma de un APK:

```bash
"$ANDROID_HOME/build-tools/36.0.0/apksigner.bat" verify --print-certs app-release.apk
```

## 4. Instalar en un Android sin Play Store

**Por archivo (cualquier teléfono, Android 7 o superior):**

1. Pasar el APK al teléfono: cable USB (copiar a Descargas), Google Drive propio o un chat con uno mismo.
2. Abrirlo desde la app Archivos. Android avisa que esa app no puede instalar apps desconocidas: *Configuración* →
   activar *Permitir de esta fuente* → volver atrás → *Instalar*.
3. Si Play Protect dice que no reconoce la app: *Más detalles* → *Instalar de todos modos* (es esperable: no está en la tienda).
4. Queda «CeliacMap» con el pin verde en el cajón de apps.

**Por cable (teléfono propio):** activar *Opciones de desarrollador* (7 toques en «Número de compilación») y *Depuración USB*,
conectar, aceptar la huella de la PC y:

```bash
"$ANDROID_HOME/platform-tools/adb.exe" install -r app-release.apk
```

**Actualizar:** instalar un APK con `versionCode` mayor y la misma firma; no se pierde nada. No hay actualización automática.
**Quitar:** desinstalar como cualquier app; no deja datos (no hay cuentas y `allowBackup` está desactivado).

## 5. Lista de pruebas en el teléfono

Marcar cada punto; ante una falla, anotar qué se vio y en qué paso.

**Arranque y mapa**
1. Abre con fondo crema y el pin; la cabecera no queda tapada por la barra de estado ni el pie por la barra de gestos.
2. El mapa dibuja sus mosaicos (clave de CARTO aceptada dentro de la app) y aparecen los pines sin recargar.
3. Buscar por nombre, filtrar por categoría y nivel, abrir una ficha, «Expandir mapa».

**Botón Atrás**
4. Con el chat abierto, Atrás cierra el chat. Con una ficha abierta, cierra la ficha. Con el mapa expandido, lo contrae.
5. Sin nada abierto, Atrás manda la app al fondo (no la cierra de golpe ni queda en blanco).

**«Cerca mío»**
6. Primer toque: explicación propia y después el permiso de Android (*precisa / aproximada*, *solo esta vez / mientras se usa*).
7. Concedido: marcador azul, lista de cercanos y distancia dentro de la ficha.
8. Aproximada: aviso de ubicación aproximada y kilómetros enteros.
9. Rechazado: ofrece elegir ciudad; mapa y chat siguen funcionando.
10. Ir a otra app y volver: la ubicación ya no está (hay que tocar de nuevo).
11. Ajustes → Apps → CeliacMap → Permisos: solo «Ubicación», nunca «todo el tiempo».

**Chat y formularios**
12. El asistente responde (`chat` v25, desplegado el 2026-10-03, acepta el origen `https://localhost` de la app).
13. El teclado no tapa el campo del chat ni los formularios; el atajo «Lugares cerca mío» abre el flujo de cercanía.
14. No enviar sugerencias, reportes ni votos de prueba: escriben en producción.

**Enlaces e idioma**
15. «Cómo llegar», el sitio web y las redes de una ficha abren fuera de la app (Maps / navegador); el teléfono abre el marcador.
16. Cambiar a inglés y volver a español.

**Sin conexión**
17. En modo avión aparece el aviso de sin conexión; al volver la red, desaparece.

**Privacidad (con el APK debug y la PC):** `chrome://inspect` → pestaña Network → tocar «Cerca mío» y usar el chat: ningún
pedido lleva las coordenadas del teléfono, y no hay pedidos a `cloudflareinsights.com`.

## 6. Límites conocidos

- La app necesita internet: Leaflet, las fuentes, los lugares, los mosaicos y el chat se piden en línea, igual que la web.
- El proveedor de mosaicos puede deducir la zona que se mira; no recibe el GPS.
- Los datos de Google siguen como riesgo abierto ([auditoría](../legal/auditoria-datos-google.md)): el APK no cambia esa
  situación ni es una excepción. Decidir antes de mostrarlo a instituciones o de publicar en una tienda.
- iOS no está compilado ni probado.
