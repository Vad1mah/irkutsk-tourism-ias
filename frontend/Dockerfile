FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# Vite-переменные нужно прокинуть через build args: .dockerignore
# исключает .env*, поэтому Vite во время npm run build не видит .env.
# Без этого apikey Yandex Maps попадает в bundle как `undefined`
# и карта не загружается (api-maps.yandex.ru возвращает 401).
ARG VITE_API_URL
ARG VITE_YANDEX_MAPS_API_KEY
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_YANDEX_MAPS_API_KEY=${VITE_YANDEX_MAPS_API_KEY}

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
