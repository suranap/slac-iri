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
