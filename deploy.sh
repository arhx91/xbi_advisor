# What it does:
# Automates the deployment of the main XBI Advisor application and the relay function to Google Cloud Run. Handles building the Docker images, pushing them to the Google Container Registry, and deploying them as Cloud Run services.
#
# Why it does it:
# - Consistent and repeatable
# - Separates deployment logic of main app and relay function, allowing them to be deployed independently or together.
# - Centralizes stuff: deployment config (incl. environment variables)
#
# How it does it:
# - The `deploy_main_app` function builds the Docker image for the main application using the root `Dockerfile`, pushes it to GCR, and deploys it as a private Cloud Run service with a GCS bucket.
# - The `deploy_cloud_function` function builds the Docker image for the relay function using `cloud_function/Dockerfile`, pushes it to GCR, and deploys it as a public Cloud Run service.
# - It dynamically retrieves the URL of the private main service and passes it as an environment variable to the relay function, enabling them to communicate.
#
# How it ties into the bigger picture:
# Functions as orchestrator for the deployment process.
#
# What about it is necessary for deployment:
# - The `gcloud run deploy` commands are the core of the deployment process, creating and updating the Cloud Run services.
# - The `docker buildx build` commands are essential for building the container images for the correct platform (linux/amd64).

set -euo pipefail  # Exit on error, unset var, or failed pipe

# Load .env if present
if [ -f .env ]; then
  # shellcheck source=.env
  source .env
fi

PROJECT_ID="${PROJECT_ID:-xbi-advisor-test}"
REGION="${REGION:-europe-west1}"
BUCKET_NAME="${BUCKET_NAME:-xbi-advisor-bucket}"
RELAY_SERVICE_ACCOUNT="${RELAY_SERVICE_ACCOUNT:-test-cf-relay-invoker@xbi-advisor-test.iam.gserviceaccount.com}"

# ----------------------------
# Shared Environment Variables
# ----------------------------
COMMON_ENV_VARS="GCS_BUCKET_PATH=/mnt/gcs"
COMMON_ENV_VARS="$COMMON_ENV_VARS,TMP_DIR=/tmp/xbi_advisor"

# ----------------------------
# Submit a Cloud Build job and wait for it to complete.
# Avoids relying on log streaming (fails under VPC-SC restrictions).
# Usage: cloud_build_submit [gcloud builds submit args...]
# ----------------------------
cloud_build_submit() {
  local BUILD_ID
  BUILD_ID=$(gcloud builds submit "$@" --async --format='value(id)')
  echo "  Build submitted: $BUILD_ID"
  while true; do
    local STATUS
    STATUS=$(gcloud builds describe "$BUILD_ID" --format='value(status)')
    case "$STATUS" in
      SUCCESS)
        echo "  Build succeeded."
        return 0
        ;;
      FAILURE|CANCELLED|TIMEOUT|INTERNAL_ERROR)
        echo "  Build failed with status: $STATUS"
        echo "  Logs: https://console.cloud.google.com/cloud-build/builds/$BUILD_ID"
        return 1
        ;;
      *)
        echo "  Build status: $STATUS — waiting..."
        sleep 10
        ;;
    esac
  done
}

# ----------------------------
# Deploy Main App (Private)
# ----------------------------
deploy_main_app() {
  SERVICE_NAME="xbi-advisor"
  IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

  ENV_VARS="$COMMON_ENV_VARS"
  ENV_VARS="$ENV_VARS,LAST_ID_BUCKET=$BUCKET_NAME"
  # Ensure required secrets are set
  : "${TYPEFORM_TOKEN:?TYPEFORM_TOKEN is required}"
  : "${AZURE_OPENAI_API_KEY:?AZURE_OPENAI_API_KEY is required}"
  : "${POWER_AUTOMATE_WEBHOOK_URL:?POWER_AUTOMATE_WEBHOOK_URL is required}"

  ENV_VARS="$ENV_VARS,TYPEFORM_FORM_ID=${TYPEFORM_FORM_ID:-Cz5qhQMm}"
  ENV_VARS="$ENV_VARS,TYPEFORM_TOKEN=${TYPEFORM_TOKEN}"
  ENV_VARS="$ENV_VARS,AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2025-01-01-preview}"
  ENV_VARS="$ENV_VARS,AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-https://xbi-openai-france.openai.azure.com}"
  ENV_VARS="$ENV_VARS,AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT:-o4-mini}"
  ENV_VARS="$ENV_VARS,AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}"
  ENV_VARS="$ENV_VARS,POWER_AUTOMATE_WEBHOOK_URL=${POWER_AUTOMATE_WEBHOOK_URL}"
  ENV_VARS="$ENV_VARS,TRANSFORMERS_OFFLINE=1"
  ENV_VARS="$ENV_VARS,HF_HUB_OFFLINE=1"
  ENV_VARS="$ENV_VARS,HF_DATASETS_OFFLINE=1"

  echo "🚀 Building and pushing MAIN APP via Cloud Build: $SERVICE_NAME"
  cloud_build_submit \
    --config cloudbuild.yaml \
    --project "$PROJECT_ID" \
    .

  gcloud run deploy "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --image "$IMAGE" \
    --platform managed \
    --region "$REGION" \
    --no-allow-unauthenticated \
    --memory=2Gi \
    --execution-environment=gen2 \
    --add-volume=name=gcs-bucket,type=cloud-storage,bucket="$BUCKET_NAME" \
    --add-volume-mount=volume=gcs-bucket,mount-path=/mnt/gcs \
    --set-env-vars "$ENV_VARS"
}

# ----------------------------
# Deploy Relay Function (Public)
# ----------------------------
deploy_cloud_function() {
  SERVICE_NAME="xbi-advisor-cloud-function"
  IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

  # Get private main app URL
  MAIN_APP_URL=$(gcloud run services describe xbi-advisor \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --format 'value(status.url)')

  ENV_VARS="$COMMON_ENV_VARS"
  ENV_VARS="$ENV_VARS,MAIN_SERVICE_URL=$MAIN_APP_URL"

  echo "🚀 Building and pushing CLOUD FUNCTION RELAY via Cloud Build: $SERVICE_NAME"
  cloud_build_submit \
    --config cloud_function/cloudbuild.yaml \
    --project "$PROJECT_ID" \
    .

  gcloud run deploy "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --image "$IMAGE" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory=512Mi \
    --execution-environment=gen2 \
    --service-account="$RELAY_SERVICE_ACCOUNT" \
    --set-env-vars "$ENV_VARS"
}


# ----------------------------
# CLI Options
# ----------------------------
case "${1:-}" in
  main)
    deploy_main_app
    ;;
  cloud_function)
    deploy_cloud_function
    ;;
  all)
    deploy_main_app
    deploy_cloud_function
    ;;
  *)
    echo "Usage: $0 {main|cloud_function|all}"
    exit 1
    ;;
esac
