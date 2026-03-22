FROM node:20.11-alpine

WORKDIR /app

COPY package.json package-lock.json* ./

# Install dependencies inside the container
RUN npm install

# Copy source code
COPY . .

# Expose Vite port
EXPOSE 5173

# Run dev server properly bound to network
CMD ["npm", "run", "dev", "--", "--host"]
