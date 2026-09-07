FROM ghcr.io/cirruslabs/flutter:3.35.7 AS build

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get
COPY . .

# Render passes API_URL as a Docker build argument from the service env vars.
ARG API_URL
RUN flutter build web --release --dart-define=API_URL=${API_URL}

FROM nginx:1.27-alpine
ENV NGINX_ENVSUBST_FILTER=PORT
COPY --from=build /app/build/web /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 10000
