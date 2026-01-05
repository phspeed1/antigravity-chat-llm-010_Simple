FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
# Copy prisma schema and generate client
COPY prisma ./prisma/
RUN npx prisma generate

EXPOSE 3000
CMD ["npm", "start"]
