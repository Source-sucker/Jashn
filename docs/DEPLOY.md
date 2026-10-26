# Jashn — Production Deployment Guide (Google Cloud Run)

This guide walks through deploying the Jashn FastAPI container to Google Cloud Run. The container listens on `$PORT` and runs as an unprivileged non-root user (`appuser`).

> **Note:** As specified in the challenge brief, do not deploy automatically. Run these steps manually when ready to release.

---

## 1. Prerequisites
- Google Cloud SDK (`gcloud`) installed and authenticated.
- A Google Cloud Project with the **Cloud Run API** and **Artifact Registry API** enabled:
  ```bash
  gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
  ```

---

## 2. Store Secrets in Secret Manager
Store your Gemini API key in Google Secret Manager to avoid plain-text environment variables:
```bash
echo -n "your-gemini-api-key" | gcloud secrets create GEMINI_API_KEY \
  --data-file=- \
  --replication-policy="automatic"
```

---

## 3. Build & Push Docker Image
Set your project ID and region:
```bash
PROJECT_ID="your-gcp-project-id"
REGION="asia-south1"  # Mumbai region for lowest latency in India
IMAGE_NAME="gcr.io/${PROJECT_ID}/jashn:v1"

# Build image using Cloud Build
gcloud builds submit --tag ${IMAGE_NAME} .
```

---

## 4. Deploy to Cloud Run
Deploy the container to Cloud Run with automatic scaling, secret injection, and listening on `$PORT`:
```bash
gcloud run deploy jashn \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "GEMINI_MODEL=gemini-flash-latest,AI_TIMEOUT_SECONDS=15,RATE_LIMIT_PER_MIN=60" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"
```

---

## 5. Local Docker Testing
To test the Docker container locally before deploying:
```bash
# Build local container
docker build -t jashn:local .

# Run container on port 8000 (with or without API key)
docker run -p 8000:8000 -e GEMINI_API_KEY="" jashn:local

# Open http://localhost:8000
```
