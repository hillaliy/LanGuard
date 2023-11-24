
FROM node:20.9.0-alpine

WORKDIR /frontend

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

RUN npm install -g serve

CMD ["serve", "-s", "build"]