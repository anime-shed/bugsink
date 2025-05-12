import logging
from django.http import JsonResponse, HttpResponse
from django.db import connections, OperationalError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.conf import settings

from bugsink.decorators import login_exempt
from bugsink.app_settings import get_settings

logger = logging.getLogger(__name__)


@require_GET
@csrf_exempt
@login_exempt
def liveness_probe(request):
    """
    Kubernetes liveness probe endpoint.
    
    This endpoint checks if the application is running and responding to HTTP requests.
    If this fails, Kubernetes will restart the pod.
    
    Returns:
        HttpResponse: 200 OK if the application is running
    """
    return HttpResponse("OK", content_type="text/plain")


@require_GET
@csrf_exempt
@login_exempt
def readiness_probe(request):
    """
    Kubernetes readiness probe endpoint.
    
    This endpoint checks if the application is ready to serve traffic by verifying:
    1. Database connections are working
    2. Required services are available
    
    If this fails, Kubernetes will not route traffic to the pod until it passes.
    
    Returns:
        JsonResponse: Status of various application components
    """
    from bugsink.version import __version__
    
    status = {
        "status": "ok",
        "databases": {},
        "version": __version__,
    }
    
    # Check database connections
    all_databases_ok = True
    for db_name in connections:
        try:
            # Test if database connection is working
            connections[db_name].cursor()
            status["databases"][db_name] = "ok"
        except OperationalError as e:
            status["databases"][db_name] = f"error: {str(e)}"
            all_databases_ok = False
            logger.error(f"Database {db_name} connection failed: {e}")
    
    # Check if application settings are properly loaded
    try:
        app_settings = get_settings()
        status["app_settings"] = "ok"
    except Exception as e:
        status["app_settings"] = f"error: {str(e)}"
        all_databases_ok = False
        logger.error(f"Failed to load application settings: {e}")
    
    # Set overall status
    if not all_databases_ok:
        status["status"] = "error"
        return JsonResponse(status, status=503)
    
    return JsonResponse(status)


@require_GET
@csrf_exempt
@login_exempt
def health_check(request):
    """
    General health check endpoint that combines aspects of both liveness and readiness.
    
    This endpoint is useful for manual checks and monitoring systems that don't
    distinguish between liveness and readiness.
    
    Returns:
        JsonResponse: Detailed health status of the application
    """
    from bugsink.version import __version__
    
    status = {
        "status": "ok",
        "databases": {},
        "version": __version__,
    }
    
    # Check database connections
    all_databases_ok = True
    for db_name in connections:
        try:
            # Test if database connection is working
            connections[db_name].cursor()
            status["databases"][db_name] = "ok"
        except OperationalError as e:
            status["databases"][db_name] = f"error: {str(e)}"
            all_databases_ok = False
    
    # Check if application settings are properly loaded
    try:
        app_settings = get_settings()
        status["app_settings"] = "ok"
    except Exception as e:
        status["app_settings"] = f"error: {str(e)}"
        all_databases_ok = False
    
    # Set overall status
    if not all_databases_ok:
        status["status"] = "error"
        return JsonResponse(status, status=503)
    
    return JsonResponse(status)