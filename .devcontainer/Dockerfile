FROM mcr.microsoft.com/devcontainers/python:3.12

RUN usermod -l dev vscode \
    && groupmod -n dev vscode \
    && usermod -d /home/dev -m dev \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev \
    && chmod 0440 /etc/sudoers.d/dev

RUN pip install --no-cache-dir --upgrade pip