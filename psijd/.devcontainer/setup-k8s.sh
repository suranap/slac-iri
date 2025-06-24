#!/bin/bash
set -e

echo "Setting up Kubernetes development environment..."

# Check if kubectl context is available
if ! kubectl config current-context 2>/dev/null; then
    echo "No kubectl context found. Please ensure your Kubernetes cluster is accessible."
    echo "You may need to run: kubectl config use-context <your-context>"
    exit 1
fi

# Create namespace if it doesn't exist
kubectl create namespace psijd --dry-run=client -o yaml | kubectl apply -f -

# Deploy psijd using Helm (as described in README.md)
echo "Deploying psijd with Helm..."
cd /opt
helm install psijd-dev ./psijd-helm-chart -f ./psijd-helm-chart/values-dev.yaml --namespace psijd

# Wait for deployment to be ready
echo "Waiting for deployment..."
kubectl wait --for=condition=available deployment/psijd-dev --namespace=psijd --timeout=300s

# Get the service port for port forwarding
SERVICE_PORT=$(kubectl get service psijd-dev -n psijd -o jsonpath='{.spec.ports[0].port}')
POD_NAME=$(kubectl get pods -n psijd -l app.kubernetes.io/name=psijd -o jsonpath='{.items[0].metadata.name}')

echo "=================================="
echo "Setup complete!"
echo "Pod name: $POD_NAME"
echo "Service port: $SERVICE_PORT"
echo ""
echo "To access your application:"
echo "kubectl port-forward svc/psijd-dev $SERVICE_PORT:$SERVICE_PORT -n psijd"
echo ""
echo "To attach to the pod for debugging:"
echo "kubectl exec -it $POD_NAME -n psijd -- /bin/bash"
echo ""
echo "To view logs:"
echo "kubectl logs -f $POD_NAME -n psijd"
echo "=================================="
