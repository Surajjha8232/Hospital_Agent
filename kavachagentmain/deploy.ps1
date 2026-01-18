$ProjectName = "hospital-agent-new"
$Region = "us-central1"


# Environment variables from kavach/mcp_server/.env
# NOTE: Ensure these values are correct and the database is accessible from Cloud Run (public IP or Cloud SQL)
$EnvVars = "PROJECT_ID=trans-opus-484315-h8,LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=1,API_KEY=AIzaSyD3kEVgfsAsGVN1YAnLfseNziEZCL7wJt8"

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
