FROM node:22-alpine AS dependencies
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS development
ENV NODE_ENV=development NEXT_TELEMETRY_DISABLED=1
RUN addgroup -S -g 10001 appgroup && adduser -S -u 10001 -G appgroup appuser
COPY --chown=appuser:appgroup . .
RUN mkdir -p .next && chown appuser:appgroup /app /app/.next
USER appuser
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM dependencies AS build
COPY . .
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build && mkdir -p public

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
ARG VCS_REF=unknown
LABEL org.opencontainers.image.revision=$VCS_REF
RUN addgroup -S -g 10001 appgroup && adduser -S -u 10001 -G appgroup appuser
COPY --from=build --chown=appuser:appgroup /app/.next/standalone ./
COPY --from=build --chown=appuser:appgroup /app/.next/static ./.next/static
COPY --from=build --chown=appuser:appgroup /app/public ./public
USER appuser
EXPOSE 3000
CMD ["node", "server.js"]
