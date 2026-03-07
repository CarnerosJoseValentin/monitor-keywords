# Keyword Monitor — GitHub Actions + RSS + Telegram

## Qué hace
- Corre cada 1 hora en GitHub Actions
- Lee feeds RSS (Google Alerts + otros)
- Monitorea Mastodon por RSS de hashtags en instancias definidas
- Filtra por keywords
- Deduplica resultados (solo nuevos) y guarda estado 30 días
- Envía un único mensaje por hora a Telegram

## Configuración
1) Crear bot en Telegram con @BotFather
2) Obtener tu CHAT_ID (ej: hablándole al bot y usando un bot helper / método que prefieras)
3) En GitHub repo: Settings → Secrets and variables → Actions → New repository secret
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

4) Editar:
- keywords.txt (1 keyword por línea)
- feeds.txt (pegar RSS de Google Alerts y/o RSS extra)
- mastodon_instances.txt (instancias Mastodon)

## Notas Mastodon
Este proyecto usa RSS de hashtags:
- https://<instancia>/tags/<hashtag>.rss

Solo funciona para keywords que sean hashtags simples (sin espacios).