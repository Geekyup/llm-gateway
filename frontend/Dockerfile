FROM nginx:1.27-alpine

COPY dist /usr/share/nginx/html

ENV PORT=80
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
