FROM node:24-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

CMD ["sh", "-c", "npm run build && rm -rf /app/build/* && cp -R out/. /app/build/"]
