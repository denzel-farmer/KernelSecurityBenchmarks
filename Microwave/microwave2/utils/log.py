import os
import datetime
from enum import IntEnum

class LogLevel(IntEnum):
    """Enumeration for log levels"""
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3

# Global configuration variables
current_print_level = LogLevel.DEBUG  # Default print level
current_write_level = LogLevel.DEBUG  # Default write level
log_file_path = "microwave.log"  # Default log file path

def configure_logging(print_level=None, write_level=None, log_path=None):
    """Configure the logging settings
    
    Args:
        print_level (LogLevel, optional): Level threshold for console output
        write_level (LogLevel, optional): Level threshold for file output
        log_path (str, optional): Path to log file
    """
    global current_print_level, current_write_level, log_file_path
    
    if print_level is not None:
        current_print_level = print_level
    
    if write_level is not None:
        current_write_level = write_level
    
    if log_path is not None:
        log_file_path = log_path

def log(message, level=LogLevel.INFO, end="\n", format_message=True):
    """Log a message at the specified level
    
    Args:
        message (str): The message to log
        level (LogLevel, optional): The log level for this message
        end (str, optional): String appended after the message, default is newline
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if format_message:
        formatted_message = f"[{timestamp}] [{level.name}] {message}"
    else:
        formatted_message = message
    
    # Print to stdout if level meets threshold
    if level <= current_print_level:
        print(formatted_message, end=end)
    
    # Write to log file if level meets threshold
    if level <= current_write_level:
        try:
            # Ensure directory exists
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            with open(log_file_path, "a") as f:
                f.write(formatted_message + end)
        except Exception as e:
            print(f"[ERROR] Failed to write to log file: {e}")

# Convenience functions
def error(*messages, end="\n"):
    """Log a message at ERROR level
    
    Args:
        *messages: Variable number of message parts to be joined with spaces
        end (str, optional): String appended after the message, default is newline
    """
    message = " ".join(str(msg) for msg in messages)
    log(message, LogLevel.ERROR, end=end)

def warn(*messages, end="\n"):
    """Log a message at WARN level
    
    Args:
        *messages: Variable number of message parts to be joined with spaces
        end (str, optional): String appended after the message, default is newline
    """
    message = " ".join(str(msg) for msg in messages)
    log(message, LogLevel.WARN, end=end)

def info(*messages, end="\n"):
    """Log a message at INFO level
    
    Args:
        *messages: Variable number of message parts to be joined with spaces
        end (str, optional): String appended after the message, default is newline
    """
    message = " ".join(str(msg) for msg in messages)
    log(message, LogLevel.INFO, end=end)

def debug(*messages, end="\n"):
    """Log a message at DEBUG level
    
    Args:
        *messages: Variable number of message parts to be joined with spaces
        end (str, optional): String appended after the message, default is newline
    """
    message = " ".join(str(msg) for msg in messages)
    log(message, LogLevel.DEBUG, end=end, format_message=False)


def debug_pause(message):
    """Log a message at DEBUG level and pause execution"""
    debug(message)
    input("Press Enter to continue...")