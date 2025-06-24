# slac-iri

## Start the services

This script shows how to start each docker-compose service. There are also some quick health checks in there too. 

```
./start.sh
```

## Test Slurm REST API

```
export $(docker compose exec c2 scontrol token)
curl -k -vvvv -H X-SLURM-USER-TOKEN:${SLURM_JWT} -H X-SLURM-USER-NAME:root -X GET 'http://localhost:9200/slurm/v0.0.41/diag' 
```

## Stop the services

```
./stop.sh
```

## REST API for PSI

POST job/submit {job details}  start a job
DELETE job/jobid  -- cancel a job
GET job/jobid     -- get job status or info
GET jobs          -- get list of all job ids for this user

The way the JobExecutor works is more procedural. You have to attach
to a job, which makes a call to get all the current info. Then you can
do some operations.

## Kubernetes Deployment with Helm

The project includes a Helm chart for deploying psijd to Kubernetes.

### Install for Development
```bash
helm install psijd-dev ./psijd-helm-chart -f ./psijd-helm-chart/values-dev.yaml
```

### Install for Production
```bash
helm install psijd-prod ./psijd-helm-chart -f ./psijd-helm-chart/values-prod.yaml
```

### Test endpoints 

```bash
kubectl port-forward service/psijd-dev 10050:10050 -n psijd &
curl -H "X-SLURM-USER-TOKEN: auth/none" http://localhost:10050/slurm/v0.0.40/ping
```

### Upgrade Deployment
```bash
# Development
helm upgrade psijd-dev ./psijd-helm-chart -f ./psijd-helm-chart/values-dev.yaml

# Production
helm upgrade psijd-prod ./psijd-helm-chart -f ./psijd-helm-chart/values-prod.yaml
```

### Uninstall
```bash
# Development
helm uninstall psijd-dev

# Production
helm uninstall psijd-prod
```
