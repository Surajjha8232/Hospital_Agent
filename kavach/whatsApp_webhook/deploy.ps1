$ProjectName = "whatsapp-webhook-server"
$Region = "us-central1"

# Environment variables from kavach/mcp_server/.env
# NOTE: Ensure these values are correct and the database is accessible from Cloud Run (public IP or Cloud SQL)
$EnvVars = "PROJECT_ID=trans-opus-484315-h8,LOCATION=us-central1,REASONING_ENGINE_ID=5049575320282202112,VERIFY_TOKEN=kumarai_secret_token1,ACCESS_TOKEN=EAAfzY7SMj7sBRCwGFUnKog5Yoe2sXLTMDGGZCAqS89fg7DdzX2BF3i4EAZBxm4pBqotPqv2ZBhqyZCE4HR6uWFd58sVYgwAWuZBEDaurAxoduXZCIt01wIEW3EjwYH36nhNkT1aWZBR5fc79UBt0sZA8Dr03TvGZBE1FGu67qRsZAfgBZB1Q8kInGiGphPJZBmSpWZAq99QZDZD,PHONE_NUMBER_ID=1020683591127740,ADK_BASE_URL=https://hospital-agent-new-368264317554.us-central1.run.app, APP_NAME=bhaktivedantaagent"


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
#cmd /c "gcloud run deploy $ProjectName --source . --platform managed --region $Region --allow-unauthenticated --min-instances 1 --set-env-vars ""$EnvVars"""

& gcloud run deploy $ProjectName --source . --platform managed --region $Region --allow-unauthenticated --min-instances 1 --set-env-vars $EnvVars

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment successful!"
} else {
    Write-Host "Deployment failed. Check the logs above."
}
