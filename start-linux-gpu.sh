#!/bin/bash
echo "🚀 Starting ARIA in GPU mode (AMD ROCm)..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env not found. Copying from .env.example..."
    cp .env.example .env
fi

# Check if ROCm SMI is available
if ! command -v rocm-smi &> /dev/null; then
    echo "⚠️ Warning: rocm-smi not found. Ensure AMD ROCm drivers are installed on the host."
fi

# Bring up Docker containers
echo "Building and starting Docker containers with GPU passthrough..."
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d --build

echo "✅ ARIA (GPU) is starting up!"
echo "   Frontend: http://localhost:8502"
echo "   API:      http://localhost:5055"
echo "   Elyra:    http://localhost:8888/elyra/lab"
echo ""
echo "You can view logs with: docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml logs -f"
