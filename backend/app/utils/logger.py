import logging
import sys
import os
import structlog

def setup_logger():
    """Configures structured logging for the application"""
    
    # Check environment
    is_production = os.getenv("ENV", "development").lower() == "production"
    
    # Processors pipeline
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if is_production:
        # JSON formatting for production (fluentd, datadog, etc.)
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty printing for console in local development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
        
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure root standard library logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

# Run setup when imported
setup_logger()

# Export log wrapper
logger = structlog.get_logger("rca_system")
