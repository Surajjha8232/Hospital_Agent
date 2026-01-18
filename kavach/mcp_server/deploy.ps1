# deploy.ps1
# Script to deploy MCP Server to Cloud Run

$ProjectName = "hospital-mcp-server-new"
$Region = "us-central1"

# Environment variables from kavach/mcp_server/.env
# NOTE: Ensure these values are correct and the database is accessible from Cloud Run (public IP or Cloud SQL)
#$EnvVars = "PG_HOST=34.41.136.230,PG_PORT=5432,PG_DATABASE=Hospital_DB,PG_USER=postgres,PG_PASSWORD=postgre123"
$EnvVars = "PROJECT_ID=trans-opus-484315-h8,LOCATION=us-central1,EMBEDDING_MODEL=text-embedding-004,API_KEY=mpzqo-yAQB_5IygHeqwrDFoH_r3VQu6ZXV66kMb9pG4,DATABASE=hospital-db"

Write-Host "Deploying $ProjectName to Cloud Run in $Region..."
Write-Host "Using environment variables: $EnvVars"

# Check if gcloud is installed
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "gcloud CLI is not installed. Please install Google Cloud SDK."
    exit 1
}

# Deploy
# --source . builds the container using the Dockerfile in the current directory
# --allow-unauthenticated makes the service public (needed for simple Agent access without auth headers)
cmd /c "gcloud run deploy $ProjectName --source . --platform managed --region $Region --allow-unauthenticated --min-instances 1 --set-env-vars ""$EnvVars"""

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment successful!"
} else {
    Write-Host "Deployment failed. Check the logs above."
}
