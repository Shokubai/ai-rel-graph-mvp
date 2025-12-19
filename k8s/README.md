# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the AIRelGraph backend.

## Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured to access your cluster
- Container registry access (GitHub Container Registry)

## Quick Start

### 1. Ensure .env file exists

The Kubernetes secrets are automatically generated from `backend/.env` at deploy time using Kustomize's `secretGenerator`. Make sure your `backend/.env` file contains:

- `POSTGRES_PASSWORD`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `NEXTAUTH_SECRET`
- `OPENAI_API_KEY`

### 2. Deploy

```bash
# Preview what will be applied (including generated secrets)
kubectl apply -k k8s/backend --dry-run=client -o yaml

# Apply the manifests
kubectl apply -k k8s/backend

# Watch the deployment
kubectl -n airelgraph get pods -w
```

### 3. Run database migrations

```bash
# Get a backend pod name
POD=$(kubectl -n airelgraph get pods -l component=backend -o jsonpath='{.items[0].metadata.name}')

# Run migrations
kubectl -n airelgraph exec -it $POD -- alembic upgrade head
```

## Customization

### Using a specific image tag

Option 1: Edit the kustomization.yaml:

```yaml
images:
  - name: ghcr.io/shokubai/airelgraph/backend
    newTag: "abc123"
```

Option 2: Use kustomize CLI:

```bash
kubectl apply -k k8s/backend --set image=ghcr.io/shokubai/airelgraph/backend:v1.0.0
```

### Scaling

```bash
# Scale backend replicas
kubectl -n airelgraph scale deployment backend --replicas=3

# Scale celery workers
kubectl -n airelgraph scale deployment celery-worker --replicas=4
```

### Updating configuration

```bash
# Edit configmap
kubectl -n airelgraph edit configmap backend-config

# Restart deployments to pick up changes
kubectl -n airelgraph rollout restart deployment backend celery-worker
```

## Components

| Component | Description |
|-----------|-------------|
| `backend` | FastAPI application (2 replicas) |
| `celery-worker` | Celery workers for async tasks (2 replicas) |
| `postgres` | PostgreSQL 15 with pgvector extension |
| `redis` | Redis 7 for Celery broker/result backend |

## Monitoring

```bash
# View all resources
kubectl -n airelgraph get all

# View logs
kubectl -n airelgraph logs -l component=backend -f
kubectl -n airelgraph logs -l component=celery-worker -f

# Check pod health
kubectl -n airelgraph describe pods

# Check events
kubectl -n airelgraph get events --sort-by='.lastTimestamp'
```

## Cleanup

```bash
kubectl delete -k k8s/backend
```

## Production Considerations

1. **Secrets Management**: Use External Secrets Operator, Sealed Secrets, or similar
2. **Ingress**: Configure an Ingress controller (nginx, traefik) for external access
3. **TLS**: Use cert-manager for automatic TLS certificates
4. **Storage**: Configure appropriate StorageClass for your cloud provider
5. **PostgreSQL**: Consider using a managed database service (RDS, Cloud SQL, etc.)
6. **Redis**: Consider using managed Redis (ElastiCache, Memorystore, etc.)
7. **Resource Limits**: Tune resource requests/limits based on actual usage
8. **Autoscaling**: Configure HorizontalPodAutoscaler for backend and celery workers
