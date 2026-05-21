# 📰 Keyword Monitor — GitHub Actions + RSS + Telegram + REP

Monitor automatizado de noticias regionales con filtrado por keywords, deduplicación, alertas horarias por Telegram y generación de un **Reporte de Explotación de Prensa (REP)** en formato `.docx` asistido por Inteligencia Artificial (Google Gemini).

---

## ¿Qué hace?

| Función | Detalle |
|---|---|
| ⏱️ **Ejecución automática** | Corre cada 1 hora vía GitHub Actions (sin servidor) |
| 📡 **Fuentes RSS** | Lee feeds RSS de medios regionales y Google Alerts |
| 🐘 **Mastodon** | Monitorea hashtags por RSS en instancias definidas |
| 🔍 **Filtrado por keywords** | Filtra noticias usando `keywords.txt` |
| 🧹 **Deduplicación** | Evita repetidos; guarda estado por 30 días |
| 🔔 **Alerta horaria** | Envía resumen cada hora a Telegram |
| 📄 **Reporte REP diario** | A las 10:00 hs (hora Argentina) genera un `.docx` institucional |
| 🤖 **IA con Gemini** | Resume cada noticia con tono policial/institucional formal |

---

## Flujo general

```
feeds.txt / keywords.txt
        │
        ▼
   Fetch RSS feeds
        │
        ▼
  Filtrado keywords ──► sin matches → descarta
        │
        ▼
  Deduplicación (state.json)
        │
   ┌────┴─────────────────────────┐
   ▼                              ▼
Alerta horaria             Acumulación diaria
 (Telegram)                 (state.json)
                                  │
                          cada día 10:00 AM (ARG)
                                  │
                                  ▼
                        Gemini resume cada noticia
                                  │
                                  ▼
                        Genera reporte REP (.docx)
                                  │
                                  ▼
                        Envía por Telegram + limpia buffer
```

---

## Estructura del repositorio

```
monitor-keywords/
├── .github/
│   └── workflows/
│       └── monitor.yml          # Workflow de GitHub Actions
├── src/
│   └── monitor.py               # Script principal
├── feeds.txt                    # URLs de feeds RSS a monitorear
├── keywords.txt                 # Palabras clave a detectar
├── keywords_mastodon.txt        # Keywords/hashtags para Mastodon
├── requirements.txt             # Dependencias Python
├── state.json                   # Estado de deduplicación (auto-generado)
└── README.md
```

---

## Configuración inicial

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/monitor-keywords.git
cd monitor-keywords
```

### 2. Crear el bot de Telegram

1. Hablar con [@BotFather](https://t.me/BotFather) en Telegram
2. Ejecutar `/newbot` y seguir las instrucciones
3. Guardar el **token** que te entrega
4. Obtener tu **CHAT_ID** hablándole al bot y usando [@userinfobot](https://t.me/userinfobot)

### 3. Obtener una API Key de Google Gemini

1. Ir a [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Crear una API Key
3. Guardarla como secret (ver sección siguiente)

### 4. Configurar los GitHub Secrets

En tu repositorio: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Descripción |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `TELEGRAM_CHAT_ID` | ID del chat o grupo donde enviar alertas |
| `GEMINI_API_KEY` | API Key de Google AI Studio para generar resúmenes |
| `GOOGLE_ALERT_FEED_1` | URL del primer feed de Google Alerts *(ver sección de feeds)* |
| `GOOGLE_ALERT_FEED_2` | URL del segundo feed de Google Alerts *(opcional)* |
| `GOOGLE_ALERT_FEED_3` | URL del tercer feed de Google Alerts *(opcional)* |

> ⚠️ Las URLs de Google Alerts contienen tu ID de cuenta de Google. **No las subas al repositorio.** Usá los Secrets para mantenerlas privadas.

### 5. Cómo obtener tu URL de Google Alerts

1. Ir a [google.com/alerts](https://www.google.com/alerts)
2. Crear una alerta con los términos que te interesen
3. En la alerta creada, hacer clic en el ícono ✏️ (editar)
4. Al final de la página, hacer clic en **"RSS"** para ver la URL del feed
5. Copiar esa URL (tendrá la forma `https://www.google.com/alerts/feeds/TU_ID/ALERTA_ID`)
6. Guardarla como `GOOGLE_ALERT_FEED_1` en los Secrets

### 6. Editar los feeds RSS en `feeds.txt`

El archivo `feeds.txt` incluye feeds RSS nativos de medios regionales. Podés agregar o quitar URLs libremente. Las líneas que empiezan con `#` son comentarios y se ignoran.

```
# feeds.txt — un feed por línea, # para comentarios

# Medios con RSS nativo
https://www.mdzol.com/rss
https://www.cadena3.com/rss.asp

# Los feeds de Google Alerts se configuran como GitHub Secrets
# y se inyectan automáticamente en el workflow (no ponerlos aquí)
```

### 7. Editar las keywords en `keywords.txt`

Una keyword por línea. Podés usar frases de más de una palabra. Las líneas con `#` son categorías/comentarios.

```
# Narcotráfico
narcotráfico
cocaína
secuestro de drogas

# Seguridad Aeroportuaria
aeropuerto
PSA
vuelo clandestino
```

---

## Reporte de Explotación de Prensa (REP)

Todos los días a las **10:00 hs (hora Argentina)** el sistema:

1. Toma todas las noticias acumuladas desde el último reporte
2. Por cada noticia, llama a **Google Gemini** para generar un resumen con tono institucional policial
3. Genera un archivo `.docx` con el siguiente formato por noticia:

```
REPORTE DE EXPLOTACIÓN DE PRENSA – (REP)
          15 MAYO 2026

──────────────────────────────────────────────────

Ámbito:           URSA II DEL CENTRO
Fecha del hecho:  15/05/2026
Hora:             09:30 hs
Provincia:        Córdoba
Delito:           Narcotráfico, Estupefacientes
Título:           [Título de la noticia]
Resumen:
[Párrafo generado por Gemini con tono institucional]
Fuente: https://...
```

4. Envía el `.docx` por Telegram con una nota de cabecera
5. Limpia el buffer para comenzar a acumular el día siguiente

> Si no hubo noticias en las últimas 24 horas, no se genera ni envía ningún reporte.

---

## Variables de entorno opcionales

| Variable | Default | Descripción |
|---|---|---|
| `RETENTION_DAYS` | `30` | Días que se mantiene el historial de noticias vistas |
| `MAX_SNIPPET_CHARS` | `300` | Longitud máxima del fragmento en alertas Telegram |

Podés configurarlas también como GitHub Secrets si querés cambiarlas sin modificar el código.

---

## Notas sobre Mastodon

El proyecto monitorea instancias de Mastodon usando sus feeds RSS de hashtags:

```
https://<instancia>/tags/<hashtag>.rss
```

Solo funciona con keywords que sean **hashtags simples** (sin espacios ni caracteres especiales). Configurá las instancias en `keywords_mastodon.txt`.

---

## Dependencias

```
feedparser==6.0.11
requests==2.32.3
python-dateutil==2.9.0.post0
python-docx==1.1.0
google-generativeai==0.4.1
```

Instalación local:

```bash
pip install -r requirements.txt
```

---

## Ejecución local (para pruebas)

```bash
export TELEGRAM_BOT_TOKEN="tu_token"
export TELEGRAM_CHAT_ID="tu_chat_id"
export GEMINI_API_KEY="tu_api_key"
export GOOGLE_ALERT_FEED_1="https://www.google.com/alerts/feeds/..."

python src/monitor.py
```

---

## Licencia

MIT
