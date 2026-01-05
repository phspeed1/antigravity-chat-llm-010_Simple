FROM node:20-slim

# OpenSSL 및 필수 라이브러리 설치 (Prisma 실행에 필수)
RUN apt-get update && apt-get install -y openssl libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package*.json ./
RUN npm install

# Prisma 클라이언트 생성
COPY prisma ./prisma/
RUN npx prisma generate

COPY . .
EXPOSE 3000
CMD ["npm", "start"]
