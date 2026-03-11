"""
Main application for Euroflex Prequalification Services.
Sets up FastAPI app, database connection, static file serving,
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from energydeskapi.auth.auth_fastapi import FastAPIOIDCAuth
from energydeskapi.sdk.common_utils import get_environment_value
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer

from venserver.ven_api import app as ven_app
from venserver.datamodel.database import engine, SessionLocal, get_db, build_db_url
from venserver.datamodel.models import Base

logger = logging.getLogger(__name__)
# Security - make it optional to get better error messages
security = HTTPBearer(auto_error=False)

# Custom function to extract and validate bearer token
def get_bearer_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract bearer token from Authorization header manually for better error handling
    """
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    return authorization[7:]  # Remove "Bearer " prefix


mainapp= FastAPI(
    title="VEN Services",
    description="API for managing the flexibility at a local site (VEN)",
    version="1.0.0"
)
# Admin appv

@mainapp.middleware("http")
async def add_root_path(request: Request, call_next):
    """Handle X-Forwarded-Prefix header for reverse proxy path rewriting"""
    prefix = request.headers.get("X-Forwarded-Prefix", "")
    original_path = request.url.path

    if prefix:
        # Store prefix for URL generation but DON'T set root_path in scope
        # because it breaks FastAPI mounted sub-applications
        request.state.prefix = prefix
        logger.info(f"Request: {original_path} | Prefix: {prefix}")

        if original_path.startswith(f"{prefix}/"):
            # Path still has prefix - this means Ingress is NOT stripping it
            # So we need to strip it ourselves
            new_path = original_path[len(prefix):]
            logger.info(f"✅ Path rewrite (prefix not stripped by Ingress): {original_path} -> {new_path}")
            request.scope["path"] = new_path
        else:
            # Path already has prefix stripped by Ingress - no rewrite needed
            logger.debug(f"Path already stripped by Ingress: {original_path}")
    else:
        # No prefix header - direct access
        request.state.prefix = ""
        if original_path.startswith("/static"):
            logger.debug(f"Request without prefix: {original_path}")

    response = await call_next(request)
    # Log 404s to help debug routing issues
    if response.status_code == 404:
        if "/static/" in original_path:
            logger.error(f"❌ 404 for static file: {original_path}")
            logger.error(f"   Static mount expects files at: {static_path.absolute()}")
        else:
            # Log other 404s to help debug routing
            current_path = request.scope.get("path", original_path)
            logger.warning(f"❌ 404 Not Found: {original_path} (current path: {current_path}, prefix: {prefix})")
    return response


# Root route - redirect to portal

@mainapp.get("/")
async def root(request: Request):
    """Redirect root to portal - respects X-Forwarded-Prefix"""
    prefix = getattr(request.state, 'prefix', '')
    redirect_url = f"{prefix}/portal/"
    logger.info(f"Root redirect: {redirect_url} (prefix: {prefix})")
    return RedirectResponse(url=redirect_url)

@mainapp.get("/readiness")
async def readiness():
    """Health check endpoint"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "Euroflex Prequalification",
        "version": "1.0.0"
    })

@mainapp.get("/liveness")
async def liveness():
    """Health check endpoint"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "Euroflex Prequalification",
        "version": "1.0.0"
    })


@mainapp.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "Euroflex Prequalification",
        "version": "1.0.0"
    })





# namespace for the programmatic API surface.
mainapp.mount("/api", ven_app)


# Helper function to get current user (can be used as dependency in routes)
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current authenticated user if OIDC is enabled"""

    return None


def require_auth(request: Request) -> Dict[str, Any]:
    """Require authentication if OIDC is enabled"""

    return {"email": "anonymous", "name": "Anonymous User", "authenticated": False}
