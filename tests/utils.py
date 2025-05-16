import os
import time
import jwt
import requests
import subprocess

def fetch_nersc_token():
    try:
        token_url = "https://oidc.nersc.gov/c2id/token"
        client_id = os.getenv("NERSC_CLIENT_ID")
        if not client_id:
            raise ValueError("NERSC_CLIENT_ID environment variable not set")
            
        private_key_file = os.getenv("NERSC_PRIVATE_KEY_FILE", "nersc_private_key.pem")
        with open(private_key_file) as f:
            private_key = f.read()

        # Create JWT assertion
        now = int(time.time())
        claims = {
            'iss': client_id,
            'sub': client_id,
            'aud': token_url,
            'iat': now,
            'exp': now + 300  # 5 minutes expiration
        }
        
        assertion = jwt.encode(claims, private_key, algorithm='RS256')
        
        # Request access token
        data = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': assertion
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        access_token_json = response.json()
        access_token = access_token_json['access_token']
        return access_token
    except Exception as e:
        print(f"Error fetching NERSC token: {str(e)}")
        return None

def fetch_slurm_token():
    try:
        # Run the docker command to fetch the SLURM_JWT token
        result = subprocess.run(
            ["docker", "compose", "--file", "slurm/docker-compose.yml", "exec", "slurmrestd", "scontrol", "token", "lifespan=300"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        # Parse the output to extract the token
        output = result.stdout.strip()
        for line in output.splitlines():
            if line.startswith("SLURM_JWT="):
                return line.split("=", 1)[1]
    except subprocess.CalledProcessError as e:
        print(f"Error fetching SLURM_JWT token: {e.stderr}")
        return None
