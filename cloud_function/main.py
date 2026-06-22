"""
main.py - Cloud Function Relay for XBI Advisor

Acts as a secure gateway to the private main XBI Advisor Cloud Run application.

What it does:
- Exposes a public HTTP POST endpoint `/relay` that accepts JSON payloads (from TypeForm)
- Generates a Google-signed OpenID Connect (OIDC) ID token using the service account
  attached to this Cloud Run service.
- Forwards the incoming request payload to the private main XBI Advisor Cloud Run
  service, including the generated ID token in the Authorization header.
- Returns the response from the main service back to the original caller.

Why it does it:
- The main XBI Advisor service is deployed privately and requires authentication
  to be invoked, ensuring security and limiting access.
- The relay provides a public entry point that handles authentication so external callers (i.e. TypeForm) don't need direct credentials. TypeForm webhook requires a public endpoint.

How it does it:
- Uses FastAPI for HTTP server and routing.
- Uses `google.oauth2.id_token` and `google.auth.transport.requests` to generate
  the required ID token to authenticate with the private Cloud Run service.
- Forwards requests using the Python `requests` library with the appropriate headers.
- Includes robust error handling and logs for observability.
- Uses cf-relay-invoker service account during deployment (see deploy.sh) for authentication and get_id_token

How it ties into the bigger picture:
- The relay service acts as a public facade for the private main service, enabling
  secure, authenticated access without exposing the main service publicly.
- This enables flexible integration scenarios (e.g., webhooks, third-party clients)
  without compromising security.
- It leverages Google Cloud’s identity and access management to enforce strong security.
"""

import logging
import os
import uuid

import google.auth.transport.requests
import google.oauth2.id_token
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ----------------------------
# Logging Setup
# ----------------------------

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ----------------------------
# Configuration
# ----------------------------
# The URL of your PRIVATE main Cloud Run service (no trailing slash)

MAIN_SERVICE_URL = os.getenv(
    "MAIN_SERVICE_URL", "https://xbi-advisor-541526129736.europe-west1.run.app"
)
# Audience for the ID token (must match service URL)
AUDIENCE = MAIN_SERVICE_URL

app = FastAPI(title="XBI Advisor Relay Service")


# ----------------------------
# Auth: Create an ID token for Cloud Run
# ----------------------------
def get_id_token(audience: str) -> str:
    """
    Generates a Google-signed ID token for authenticating to Cloud Run,
    using the Cloud Run service's own attached service account.
    """
    logger.info(f"Generating ID token for audience: {audience}")
    auth_request = google.auth.transport.requests.Request()
    return google.oauth2.id_token.fetch_id_token(auth_request, audience)


# ----------------------------
# FastAPI App
# ----------------------------


@app.get("/")
async def health_check():
    """Simple health check endpoint."""
    logger.info("Health check ping received")
    return {"status": "ok", "service": "xbi-advisor-relay"}


@app.post("/relay")
async def relay_endpoint(request: Request):
    """
    Relay endpoint: receives JSON payload, forwards it to the private service.
    """
    request_id = str(uuid.uuid4())
    try:
        # 1. Read incoming payload
        logger.info(f"[{request_id}] Incoming relay request received.")
        payload = await request.json()
        logger.info(f"[{request_id}] Payload: {payload}")
        # 2. Generate ID token using Cloud Run's identity
        id_token = get_id_token(AUDIENCE)
        logger.info(f"[{request_id}] ID token generated successfully.")
        # 3. Forward request to main Cloud Run service
        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
        }
        url = f"{MAIN_SERVICE_URL}/webhook"
        logger.info(f"[{request_id}] Forwarding request to {url}")

        response = requests.post(url, json=payload, headers=headers)
        # 4. Return the response from main service
        try:
            logger.info(f"[{request_id}] Received response: {response.status_code}")
            return JSONResponse(
                status_code=response.status_code, content=response.json()
            )
        except Exception:
            logger.warning(f"[{request_id}] Response is not JSON: {response.text}")
            return JSONResponse(
                status_code=response.status_code, content={"text": response.text}
            )

    except Exception as e:
        logger.exception(f"[{request_id}] Error processing relay request")
        return JSONResponse(status_code=500, content={"error": str(e)})
