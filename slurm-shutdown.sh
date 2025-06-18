#!/bin/bash

# Shutdown Slurm and related services
set -e

echo "Uninstalling Slurm cluster..."
helm uninstall slurm -n slurm || true

echo "Uninstalling slurm-operator..."
helm uninstall slurm-operator -n slinky || true

echo "Uninstalling prometheus..."
helm uninstall prometheus -n prometheus || true

echo "Uninstalling cert-manager..."
helm uninstall cert-manager -n cert-manager || true

echo "Deleting namespaces..."
kubectl delete namespace slurm --ignore-not-found=true
kubectl delete namespace slinky --ignore-not-found=true  
kubectl delete namespace prometheus --ignore-not-found=true
kubectl delete namespace cert-manager --ignore-not-found=true

echo "Cleaning up CRDs..."
kubectl delete crd clusters.slinky.slurm.net --ignore-not-found=true
kubectl delete crd nodesets.slinky.slurm.net --ignore-not-found=true

# Clean up any cert-manager CRDs
kubectl get crd | grep cert-manager | cut -d' ' -f1 | xargs kubectl delete crd --ignore-not-found=true || true

echo "All services stopped and cleaned up."