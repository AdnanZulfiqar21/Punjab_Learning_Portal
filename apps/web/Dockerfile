# Web image (P03.S3.T2). The API origin is read at runtime, so the same image can point at another environment.
FROM node:22-bookworm-slim

RUN corepack enable && corepack prepare pnpm@10.34.6 --activate
WORKDIR /srv

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY apps/mobile/package.json apps/mobile/package.json
COPY packages/contracts/package.json packages/contracts/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages/contracts packages/contracts
RUN pnpm --filter web build

ENV NODE_ENV=production
EXPOSE 3100
CMD ["pnpm", "--filter", "web", "start"]
