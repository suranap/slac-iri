
# PSI/J Service

## Overview

The PSI/J Service is a RESTful API that allows you to submit jobs to remote services. Currently implemented are SlurmRESTd and Superfacility API.


## Using the devcontainer to connect to k8s

TODO: The devcontainer still doesn't work right. Notes below, it's not a smooth process. 

- Once the devcontainer is running, use this command to forward a port from Slurm's REST pod to the localhost
`kubectl port-forward -n slurm svc/slurm-restapi 6820:6820`
- Get a Slurm access token. This should be improved with a better Authentication system.
```
kubectl exec -n slurm $(kubectl get pods -n slurm -l app.kubernetes.io/component=compute -o jsonpath='{.items[0].metadata.name}') -- /usr/bin/bash -c "scontrol token"
```
- Within the devcontainer, you can reach localhost via this docker escape route. Tell PSI/Jd to use this for Slurm.
```
export SLURM_RESTD_URL=http://host.docker.internal:6820
curl -H "X-SLURM-USER-TOKEN: auth/none" $SLURM_REST_URL/slurm/v0.0.40/diag
```
- Start PSI/J with FastAPI. There's some issue with port forwarding via 5000. 
`fastapi dev --host 0.0.0.0 --port 5000 psijd/service/app.py`
- From a devcontainer terminal you can hit an endpoint list this: 
```
curl http://localhost:5000/api/slac/v0.1.0/health
```
- Set the token above to SLURM_JWT. Use this command for Slurm
```
curl -H "Authorization: Bearer $SLURM_JWT" http://localhost:5000/api/slac/v0.1.0/jobs
```

