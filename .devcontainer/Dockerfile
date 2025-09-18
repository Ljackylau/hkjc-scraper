FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# 安裝 Google Chrome（提供 headless 環境給 Selenium）
RUN apt-get update && apt-get install -y wget gnupg2 ca-certificates && \
    wget -qO- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-linux.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable xvfb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99
