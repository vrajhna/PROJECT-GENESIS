# Genesis editor (Next.js) on Railway.
# Build-time: NEXT_PUBLIC_GENESIS_API is baked in (set as build arg).
FROM node:20-alpine AS build
WORKDIR /web
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_GENESIS_API
ENV NEXT_PUBLIC_GENESIS_API=$NEXT_PUBLIC_GENESIS_API
RUN npm run build

FROM node:20-alpine
WORKDIR /web
ENV NODE_ENV=production
COPY --from=build /web ./
EXPOSE 3101
CMD ["sh", "-c", "npx next start -p ${PORT:-3101}"]
