#!/bin/bash
# ROCKIT Demo Deployment — One-command launch
# Usage: ./start-demo.sh
#
# Prerequisites: Docker installed
# Optional: Set GEMINI_API_KEY in environment before running

set -e

echo "🚀 Building ROCKIT Demo Container..."
echo "   This bundles SurrealDB + API + Frontend into a single image."
echo ""

# Build the demo image
docker build -f Dockerfile.demo -t rockit-demo .

echo ""
echo "🔧 Starting ROCKIT Demo..."

# Run the container
# Pass GEMINI_API_KEY from host environment (required for LLM chat)
docker run -d \
    --name rockit-demo \
    -p 8502:8502 \
    -p 5055:5055 \
    -e GEMINI_API_KEY="${GEMINI_API_KEY}" \
    -e DEMO_MODE=true \
    --restart unless-stopped \
    rockit-demo

echo ""
echo "✅ ROCKIT Demo is starting up!"
echo ""
echo "   🌐 Frontend:  http://localhost:8502"
echo "   🔧 API:       http://localhost:5055"
echo "   📚 API Docs:  http://localhost:5055/docs"
echo ""
echo "   ⚠️  DEMO MODE is active — uploads, deletions, and project creation are disabled."
echo ""
echo "   To view logs:    docker logs -f rockit-demo"
echo "   To stop:         docker stop rockit-demo && docker rm rockit-demo"
echo ""
