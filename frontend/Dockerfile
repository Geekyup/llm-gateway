FROM nginx:1.31-alpine

# Собери фронтенд на хосте перед докер-сборкой (см. README):
#   cd frontend && npm install && npm run build
# Так Docker не тянет npm-пакеты внутри контейнера — актуально, если
# сеть Docker (WSL2/vpnkit) не может достучаться до npm registry, хотя
# сам хост в интернет выходит нормально.

COPY dist /usr/share/nginx/html

# Templated so $PORT (Railway injects this) picks the listen port; nginx's
# entrypoint runs envsubst on any *.template file automatically. Defaults
# to 80 for plain `docker run`/docker-compose, where $PORT isn't set.
ENV PORT=80
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
