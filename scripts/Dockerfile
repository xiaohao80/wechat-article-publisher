FROM node:18-slim

WORKDIR /app

# 安装sharp系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libvips-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY package.json package-lock.json* ./

# 安装依赖
RUN npm install --production

# 复制源码
COPY server.js ./

EXPOSE 80

CMD ["node", "server.js"]
