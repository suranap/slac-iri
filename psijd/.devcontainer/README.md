# Kubernetes Development with Dev Containers

This setup allows you to develop your PSI/J service with Kubernetes using VS Code Dev Containers and Helm.

## Prerequisites

1. A Kubernetes cluster (kind, minikube, or remote cluster)
2. kubectl configured to access your cluster
3. Docker Desktop or Docker daemon running
4. VS Code with Dev Containers extension

## Quick Start

1. **Open in Dev Container**: Use `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"

2. **Build and Deploy**: The setup script will automatically:
   - Build your Docker image
   - Deploy using Helm with `values-dev.yaml`
   - Create the `psijd` namespace
   - Wait for the deployment to be ready

## Available VS Code Tasks

Access these via `Ctrl+Shift+P` → "Tasks: Run Task":

- **Build and Deploy to K8s**: Full rebuild and redeploy
- **Port Forward Service**: Forward port 10050 to access your service
- **Helm Upgrade**: Update deployment with latest code changes
- **View Pod Logs**: Stream logs from your pod
- **Get Pod Shell**: Open a bash shell in your pod

## Development Workflow

### 1. Code Changes
1. Edit your code in VS Code
2. Run "Build and Deploy to K8s" task to redeploy
3. Use "Port Forward Service" to access your app at `localhost:10050`

### 2. Debugging
1. Add `import debugpy; debugpy.listen(5678); debugpy.wait_for_client()` to your Python code
2. Run the "Debug Pod (Port Forward)" launch configuration
3. Set breakpoints and debug normally

### 3. Live Editing (Alternative)
For faster iteration, you can:
1. Run "Get Pod Shell" to get terminal access
2. Edit files directly in the pod
3. Restart the service process

## Manual Commands

```bash
# Port forward your service
kubectl port-forward svc/psijd-dev 10050:10050 -n psijd

# Get pod logs
kubectl logs -f -l app.kubernetes.io/name=psijd -n psijd

# Execute commands in pod
kubectl exec -it $(kubectl get pods -n psijd -l app.kubernetes.io/name=psijd -o jsonpath='{.items[0].metadata.name}') -n psijd -- /bin/bash

# Update deployment
helm upgrade --install psijd-dev ./psijd-helm-chart --namespace psijd --values ./psijd-helm-chart/values-dev.yaml
```

## Helm Configuration

The deployment uses:
- Chart: `psijd-helm-chart/`
- Values: `values-dev.yaml` (for development)
- Image: `psijd:latest` (built locally)
- Namespace: `psijd`

## Troubleshooting

1. **Pod not starting**: Check logs with "View Pod Logs" task
2. **Image not found**: Ensure Docker image was built and loaded into cluster
3. **Can't connect**: Verify port forwarding is active
4. **Permission issues**: Check if your kubectl context has proper permissions

## File Sync Alternative

For even faster development, consider:
1. Using a volume mount in your Helm values
2. Using Skaffold for automatic rebuilds
3. Using Telepresence for local development with cluster services


