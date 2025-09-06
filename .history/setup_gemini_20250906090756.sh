#!/bin/bash
# setup_gemini.sh - Quick setup script for Gemini-only phishing detection

echo "🚀 Setting up Phishing Detection with Google Gemini..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found, copying from .env.example"
    cp .env.example .env
    echo "📝 Please update .env with your Gemini API key and other settings"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

echo "🔧 Building and starting services..."

# Build and start core services
docker-compose up -d elasticsearch kibana logstash filebeat elastalert

echo "⏳ Waiting for Elasticsearch to be ready..."
sleep 30

# Check Elasticsearch health
until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
    echo "⏳ Still waiting for Elasticsearch..."
    sleep 10
done

echo "✅ Elasticsearch is ready!"

# Start the main application services
docker-compose up -d agent api

echo "🎉 Setup complete!"
echo ""
echo "📊 Services running:"
echo "   - Kibana: http://localhost:5601"
echo "   - API: http://localhost:8000"
echo "   - Elasticsearch: http://localhost:9200"
echo ""
echo "🔍 To check logs:"
echo "   docker-compose logs -f agent"
echo ""
echo "🎮 To start the Gradio demo:"
echo "   docker-compose --profile dev up -d gradio_demo"
echo "   Demo will be available at: http://localhost:7860"
echo ""
echo "⚙️  Configuration:"
echo "   - Update .env file with your Gemini API key"
echo "   - Set IMAP settings for email monitoring"
echo "   - Configure alert settings in .env"
