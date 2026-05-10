#!/bin/bash
echo "🚀 Starting ARIA in CPU mode (Linux)..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env not found. Copying from .env.example..."
    cp .env.example .env
fi

# Bring up Docker containers
echo "Building and starting Docker containers..."
docker compose -f docker-compose.dev.yml -f docker-compose.cpu.yml up -d --build

echo "✅ ARIA (CPU) is starting up!"
echo "   Frontend: http://localhost:8502"
echo "   API:      http://localhost:5055"
echo "   Elyra:    http://localhost:8888/elyra/lab"
echo ""
echo "You can view logs with: docker compose -f docker-compose.dev.yml -f docker-compose.cpu.yml logs -f"
