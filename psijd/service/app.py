import logging
import logging.config
import importlib
import yaml
from fastapi import FastAPI
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


# Load logging configuration from YAML file
with open("./psijd/logging.yaml", "r") as f:
    config = yaml.safe_load(f)
    logging.config.dictConfig(config)

# Get the logger for this module
logger = logging.getLogger(__name__)  # Use the name defined in logging.yaml

app = FastAPI(title='PSI/J Service API', version='0.1')

# Custom 404 Not Found handler
async def custom_404_handler(request: Request, exc: Exception):
    """Custom handler for 404 Not Found errors."""
    return JSONResponse(
        status_code=404,
        content={"message": f"Oops! The endpoint '{request.url.path}' was not found. Please check the URL and try again."},
    )

app.add_exception_handler(404, custom_404_handler)

# Define the available backends and their versions
BACKEND_VERSIONS = {
    'slac': ['v0.1.0'],
    'nersc': ['v0.1.0']
}

# Import and register routers for each backend and version
for backend, versions in BACKEND_VERSIONS.items():
    for version in versions:
        # Convert version format to Python module name (v0.1.0 -> v0_1_0)
        module_version = version.replace('.', '_')
        
        try:
            # Dynamically import the router module
            import os; print(os.getcwd())  # Debugging line to check current working directory
            import sys; print(sys.path)  # Debugging line to check Python path
            module_path = f"psijd.service.routers.{backend}.{module_version}"
            router_module = importlib.import_module(module_path)
            
            # Register the router with the app using the backend and version in the path
            app.include_router(
                router_module.router,
                prefix=f"/api/{backend}/{version}",
                tags=[f"{backend}-{version}"]
            )
            logger.info(f"Registered router for {backend} {version}")
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load router for {backend} {version}: {str(e)}")


# Global health endpoint
@app.get("/health", response_model=dict)
async def health():
    """Global system health check"""
    return {
        "status": "healthy",
        "backends": list(BACKEND_VERSIONS.keys()),
        "service_version": "0.1.0"
    }

# Simple hello world endpoint for testing
@app.get("/hello", response_model=str)
async def hello():
    """Test endpoint"""
    return "Hello, world!"
