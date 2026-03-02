"""
Centralised logging configuration for the Sales Agent application.
Provides both console and rotating file logging with structured JSON formart.

Author: Ben Walker (BenRWalker@icloud.com)
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from pythonjsonlogger import jsonlogger

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

MAIN_LOG_FILE = LOGS_DIR / "sales_agent.log"
ERROR_LOG_FILE = LOGS_DIR / "sales_agent_errors.log"
AGENT_LOG_FILE = LOGS_DIR / "agent_activity.log"
GUARDRAIL_LOG_FILE = LOGS_DIR / "guardrails.log"

MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
        
        log_record['application'] = 'sales_agent'
        
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line_number'] = record.lineno

class ColoredConsoleFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        return super().format(record)
    
def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    use_json: bool = False
) -> logging.Logger:
    """
    Set up a logger with both file and console handlers
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
        use_json: Whether to use JSON format for file logs
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        console_format = ColoredConsoleFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    if log_to_file:
        if 'guardrail' in name.lower():
            log_file = GUARDRAIL_LOG_FILE
        elif any(keyword in name.lower() for keyword in ['agent', 'sales', 'email_service', 'interface']):
            log_file = AGENT_LOG_FILE
        else:
            log_file = MAIN_LOG_FILE
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        if use_json:
            json_format = CustomJsonFormatter(
                fmt='%(timestamp)s %(level)s %(name)s %(message)s'
            )
            file_handler.setFormatter(json_format)
        else:
            text_format = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(text_format)
        
        logger.addHandler(file_handler)
    
    if log_to_file:
        error_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        if use_json:
            error_handler.setFormatter(CustomJsonFormatter(
                fmt='%(timestamp)s %(level)s %(name)s %(message)s'
            ))
        else:
            error_handler.setFormatter(logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        
        logger.addHandler(error_handler)
    
    logger.propagate = False
    
    return logger


def get_log_level_from_env() -> int:
    level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
    return getattr(logging, level_name, logging.INFO)


app_logger = setup_logger(
    'sales_agent',
    level=get_log_level_from_env(),
    use_json=False
)