# Kubernetes Deployment Guide for Bugsink

This document provides guidance on deploying Bugsink in a Kubernetes environment with proper health checks.

## Overview

Kubernetes uses probes to determine the health of container applications. For Bugsink, we've implemented:

- **Liveness Probes**: Determine if the application is running. If these fail, Kubernetes restarts the container.
- **Readiness Probes**: Determine if the application can receive traffic. If these fail, Kubernetes stops sending traffic to the container until it passes.

## Health Probes Implementation

Bugsink now includes dedicated endpoints for Kubernetes health checks:

1. **Liveness Probe** (`/health/live/`)
   - Checks if the application is running and responding to HTTP requests
   - If this fails, Kubernetes will restart the pod
   - Simple check that returns a 200 OK response

2. **Readiness Probe** (`/health/ready/`)
   - Checks if the application is ready to serve traffic
   - Verifies database connections (both default and snappea databases)
   - Confirms application settings are properly loaded
   - If this fails, Kubernetes will not route traffic to the pod until it passes

3. **General Health Check** (`/health/`)
   - Combines aspects of both liveness and readiness checks
   - Provides detailed health status in JSON format
   - Useful for manual checks and monitoring systems

## Kubernetes Configuration

A sample Kubernetes deployment configuration is provided in `kubernetes-deployment-example.yaml`. This configuration includes:

- Deployment with 2 replicas
- Service configuration
- Persistent volume claim for data storage
- Properly configured liveness and readiness probes

### Probe Configuration

```yaml
# Liveness probe - checks if the application is running
livenessProbe:
  httpGet:
    path: /health/live/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

# Readiness probe - checks if the application is ready to serve traffic
readinessProbe:
  httpGet:
    path: /health/ready/
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

## Probe Parameters

- `initialDelaySeconds`: Time to wait before performing the first probe
- `periodSeconds`: How often to perform the probe
- `timeoutSeconds`: Time after which the probe times out
- `failureThreshold`: Number of consecutive failures before considering the probe failed

## Implementation Details

The health check endpoints are implemented in `bugsink/health.py` and are:

1. Login-exempt - no authentication required
2. CSRF-exempt - no CSRF token required
3. GET-only - only respond to GET requests

The readiness probe checks:
- Database connections for all configured databases
- Application settings loading

## Customizing Probes

You may need to adjust the probe parameters based on your specific deployment:

- For larger applications or slower environments, increase `initialDelaySeconds`
- For more critical applications, decrease `failureThreshold`
- For applications with occasional slow responses, increase `timeoutSeconds`

## Troubleshooting

If pods are restarting frequently:

1. Check the pod events: `kubectl describe pod <pod-name>`
2. Check the logs: `kubectl logs <pod-name>`
3. Manually test the health endpoints by port-forwarding: `kubectl port-forward <pod-name> 8000:8000`
4. Access the health endpoints in your browser: `http://localhost:8000/health/`