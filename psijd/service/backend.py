from typing import Dict, Any, Optional
from psij import JobExecutor
import os
import logging
import importlib

logger = logging.getLogger(__name__)

# Backend configuration
BACKEND_CONFIGS = {
    'slac': {
        'v0.1.0': {
            'class': 'psijd.executors.psij_slurmrestd.psij_slurmrestd.slurmrestd.SlurmRestAPIExecutor',
            'url': os.getenv('SLURM_RESTD_URL', 'http://slurmrestd:9200'),
            'config_class': 'psijd.executors.psij_slurmrestd.psij_slurmrestd.slurmrestd.SlurmRestAPIExecutorConfig',
            'config': {
                'verify_ssl': False
            }
        }
    },
    'nersc': {
        'v0.1.0': {
            'class': 'psijd.executors.psij_nersc.psij_nersc.nersc.NERSCExecutor',
            'url': 'https://api.nersc.gov/v1',
            'config_class': 'psijd.executors.psij_nersc.psij_nersc.nersc.NERSCExecutorConfig',
            'config': {}
        }
    }
}

def get_executor(backend: str, version: str, access_token: Optional[str] = None) -> JobExecutor:
    """Factory function to create the appropriate executor based on backend and version"""
    logger.info(f"get_executor called with: backend='{backend}', version='{version}'")
    
    if backend not in BACKEND_CONFIGS:
        logger.warning(f"Backend '{backend}' not found in BACKEND_CONFIGS")
        raise ValueError(f"Unknown backend: {backend}")
    
    if version not in BACKEND_CONFIGS[backend]:
        logger.warning(f"Version '{version}' not found for backend '{backend}'")
        raise ValueError(f"Unknown version {version} for backend {backend}")
    
    config = BACKEND_CONFIGS[backend][version]
    logger.info(f"Found config for {backend}/{version}: {config}")
    
    # Dynamically import and instantiate the executor class
    try:
        # Import the executor class
        module_path, class_name = config['class'].rsplit('.', 1)
        logger.info(f"Attempting to import {class_name} from {module_path}")
        module = importlib.import_module(module_path)
        executor_class = getattr(module, class_name)
        logger.info(f"Successfully imported {class_name}")
        
        # Import and instantiate the config class if needed
        executor_config_params = config.get('config', {}).copy() # Start with default config values
        executor_config = None

        if 'config_class' in config and config['config_class']:
            logger.info(f"Config class specified: {config['config_class']}")
            # If an access token is provided, add it to the config parameters.
            if access_token is not None:
                executor_config_params['token'] = access_token
            
            config_module_path, config_class_name = config['config_class'].rsplit('.', 1)
            logger.info(f"Attempting to import config class {config_class_name} from {config_module_path}")
            config_module = importlib.import_module(config_module_path)
            config_class_ref = getattr(config_module, config_class_name)
            executor_config = config_class_ref(**executor_config_params)
            logger.info("Successfully created config instance")
        
        # Create and return the executor instance
        logger.info("Creating executor instance")
        executor_instance = executor_class(url=config['url'], config=executor_config)
        logger.info("Successfully created executor instance.")
        return executor_instance
    except (ImportError, AttributeError) as e:
        logger.error(f"Error during executor instantiation: {e}")
        logger.error(f"Failed to instantiate executor for {backend} {version}: {str(e)}")
        raise RuntimeError(f"Failed to instantiate executor: {str(e)}")
