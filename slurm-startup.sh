#!/bin/bash

# Start Slurm and related services in Kubernetes
set -e

echo "Adding Helm repositories..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add jetstack https://charts.jetstack.io
helm repo update

echo "Installing cert-manager..."
helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace --set crds.enabled=true

echo "Installing prometheus..."
helm install prometheus prometheus-community/kube-prometheus-stack --namespace prometheus --create-namespace --set installCRDs=true --values=prometheus-values.yaml

echo "Installing Slinky operator..."
if [ ! -f slinky-values.yaml ]; then
  curl -L https://raw.githubusercontent.com/SlinkyProject/slurm-operator/refs/tags/v0.3.0/helm/slurm-operator/values.yaml -o slinky-values.yaml
else
  echo "slinky-values.yaml already exists, skipping download."
fi
helm install slurm-operator oci://ghcr.io/slinkyproject/charts/slurm-operator --values=slinky-values.yaml --version=0.3.0 --namespace=slinky --create-namespace

echo "Waiting for Slinky operator webhook to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=slurm-operator -n slinky --timeout=300s
echo "Waiting additional time for webhook service to be fully ready..."
sleep 10

echo "Checking available storage classes..."
kubectl get storageclass

if [ ! -f slurm-values.yaml ]; then
  curl -L https://raw.githubusercontent.com/SlinkyProject/slurm-operator/refs/tags/v0.3.0/helm/slurm/values.yaml -o slurm-values.yaml
else
  echo "slurm-values.yaml already exists, skipping download."
fi

# Check if we're running on Docker Desktop (hostpath storage class available)
if kubectl get storageclass hostpath >/dev/null 2>&1; then
    echo "Detected hostpath storage class - deploying with Docker Desktop configuration..."
    helm install slurm oci://ghcr.io/slinkyproject/charts/slurm \
      --version=0.3.0 --namespace=slurm --create-namespace --values=slurm-values.yaml \
      --set mariadb.primary.persistence.storageClass=hostpath \
      --set controller.persistence.statesave.storageClass=hostpath
else
    echo "Using standard storage class for production deployment..."
    helm install slurm oci://ghcr.io/slinkyproject/charts/slurm --values=slurm-values.yaml \
      --version=0.3.0 --namespace=slurm --create-namespace
fi

echo "Waiting for Slurm pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=slurmrestd -n slurm --timeout=300s

echo "Verifying deployment..."
kubectl get pods -n slurm

echo "Testing slurmrestd ping endpoint..."
kubectl run curl-test --image=curlimages/curl --rm -i --restart=Never -- \
  curl -H "X-SLURM-USER-TOKEN: auth/none" \
  http://slurm-restapi.slurm.svc.cluster.local:6820/slurm/v0.0.43/ping

echo "Slurm cluster startup complete!"
echo "To test the REST API, you can run:"
echo "  SLURM_RESTAPI_IP=\"\$(kubectl get services -n slurm -l app.kubernetes.io/name=slurmrestd -o jsonpath=\"{.items[0].spec.clusterIP}\")\""
echo "  curl -H \"X-SLURM-USER-TOKEN: auth/none\" http://\${SLURM_RESTAPI_IP}:6820/slurm/v0.0.43/ping"
