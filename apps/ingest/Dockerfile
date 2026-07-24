FROM oven/bun:1.3.13-alpine

WORKDIR /app

COPY package.json ./
COPY src ./src

ENV PORT=8080
EXPOSE 8080

CMD ["bun", "src/server.ts"]
