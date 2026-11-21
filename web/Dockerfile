# PICO-8 Percept web (Astro SSR on Node). The API lives on the same origin
# under /api, routed by the ingress to the server container.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG PUBLIC_SITE_URL=https://pico8-bh.giow.dev
ARG PUBLIC_CONTACT_EMAIL=
ENV PUBLIC_SITE_URL=$PUBLIC_SITE_URL PUBLIC_CONTACT_EMAIL=$PUBLIC_CONTACT_EMAIL
RUN npm run build && npm prune --omit=dev

FROM node:24-alpine
ENV NODE_ENV=production HOST=0.0.0.0 PORT=4321
WORKDIR /app
COPY --from=build --chown=root:root /app/dist ./dist
COPY --from=build --chown=root:root /app/node_modules ./node_modules
COPY --from=build --chown=root:root /app/package.json ./package.json
USER node
EXPOSE 4321
CMD ["node", "dist/server/entry.mjs"]
