FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (separate layer for caching)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source and build
COPY . .
# svelte-kit sync generates .svelte-kit/ (including tsconfig.json) before build
RUN npx svelte-kit sync && npm run build

# ── Production image ──────────────────────────────────
FROM node:20-alpine

WORKDIR /app

# Only copy the built output and node_modules needed at runtime
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json ./

# Install only production dependencies
RUN npm install --production

EXPOSE 3000

ENV HOST=0.0.0.0
ENV PORT=3000

CMD ["node", "build"]
