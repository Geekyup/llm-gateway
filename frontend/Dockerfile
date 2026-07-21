FROM nginx:1.27-alpine

# Собери фронтенд на хосте перед докер-сборкой (см. README):
#   cd frontend && npm install && npm run build
# Так Docker не тянет npm-пакеты внутри контейнера — актуально, если
# сеть Docker (WSL2/vpnkit) не может достучаться до npm registry, хотя
# сам хост в интернет выходит нормально.

COPY dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
