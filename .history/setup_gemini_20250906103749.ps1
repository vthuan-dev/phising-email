# setup_gemini.ps1 - Quick setup script for Gemini-only phishing detection

Write-Host "🚀 Setting up Phishing Detection with Google Gemini..." -ForegroundColor Green

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  No .env file found, copying from .env.example" -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "📝 Please update .env with your Gemini API key and other settings" -ForegroundColor Cyan
}

# Check Docker
try {
    docker --version | Out-Null
    docker-compose --version | Out-Null
}
catch {
    Write-Host "❌ Docker or Docker Compose not found. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

Write-Host "🔧 Building and starting services..." -ForegroundColor Blue

# Build and start core services
docker-compose up -d elasticsearch kibana logstash filebeat elastalert

Write-Host "⏳ Waiting for Elasticsearch to be ready..." -ForegroundColor Yellow
Start-Sleep 30

# Check Elasticsearch health
$maxAttempts = 12
$attempt = 0
do {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:9200/_cluster/health" -Method Get
        if ($response.status -eq "green" -or $response.status -eq "yellow") {
            break
        }
    }
    catch {
        # Continue waiting
    }
    
    Write-Host "⏳ Still waiting for Elasticsearch..." -ForegroundColor Yellow
    Start-Sleep 10
    $attempt++
} while ($attempt -lt $maxAttempts)

if ($attempt -ge $maxAttempts) {
    Write-Host "❌ Elasticsearch failed to start properly" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Elasticsearch is ready!" -ForegroundColor Green

# Start the main application services
docker-compose up -d agent api

Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Services running:" -ForegroundColor Cyan
Write-Host "   - Kibana: http://localhost:5601"
Write-Host "   - API: http://localhost:8000"
Write-Host "   - Elasticsearch: http://localhost:9200"
Write-Host ""
Write-Host "🔍 To check logs:" -ForegroundColor Cyan
Write-Host "   docker-compose logs -f agent"
Write-Host ""
Write-Host "🎮 To start the Gradio demo:" -ForegroundColor Cyan
Write-Host "   docker-compose --profile dev up -d gradio_demo"
Write-Host "   Demo will be available at: http://localhost:7860"
Write-Host ""
Write-Host "⚙️  Configuration:" -ForegroundColor Yellow
Write-Host "   - Update .env file with your Gemini API key"
Write-Host "   - Set IMAP settings for email monitoring"
Write-Host "   - Configure alert settings in .env"
