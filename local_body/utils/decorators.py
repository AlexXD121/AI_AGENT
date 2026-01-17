"""Error handling decorators for safe execution and tracing.

Provides decorators to wrap critical functions with comprehensive
error handling, logging, and state propagation.
"""

import functools
from typing import Callable, Any
from loguru import logger

from local_body.core.exceptions import ProcessingError


def trace_and_handle(func: Callable) -> Callable:
    """Decorator to trace function execution and handle errors gracefully.
    
    This decorator:
    1. Logs function entry and exit
    2. Captures full tracebacks on errors
    3. Converts exceptions to ProcessingError with context
    4. Ensures errors are never silently swallowed
    
    Usage:
        @trace_and_handle
        async def my_critical_function():
            # Your code here
            pass
    
    Args:
        func: Function to wrap (sync or async)
        
    Returns:
        Wrapped function with error handling
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"Entering {func_name}")
        
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Exiting {func_name} successfully")
            return result
            
        except ProcessingError:
            # Already a ProcessingError, just re-raise
            logger.exception(f"PROCESSING ERROR in {func_name}")
            raise
            
        except Exception as e:
            # Capture full traceback
            logger.exception(f"CRITICAL FAILURE in {func_name}: {type(e).__name__}: {e}")
            
            # Convert to ProcessingError with context
            raise ProcessingError(
                message=f"Step '{func_name}' failed: {str(e)}",
                step=func_name,
                original_error=e
            ) from e
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"Entering {func_name}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting {func_name} successfully")
            return result
            
        except ProcessingError:
            # Already a ProcessingError, just re-raise
            logger.exception(f"PROCESSING ERROR in {func_name}")
            raise
            
        except Exception as e:
            # Capture full traceback
            logger.exception(f"CRITICAL FAILURE in {func_name}: {type(e).__name__}: {e}")
            
            # Convert to ProcessingError with context
            raise ProcessingError(
                message=f"Step '{func_name}' failed: {str(e)}",
                step=func_name,
                original_error=e
            ) from e
    
    # Return appropriate wrapper based on function type
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def safe_node_execution(node_name: str):
    """Decorator for workflow nodes with state-aware error handling.
    
    This decorator:
    1. Catches all exceptions in workflow nodes
    2. Updates state with error information
    3. Sets processing_stage to FAILED
    4. Preserves partial results when possible
    
    Args:
        node_name: Name of the workflow node for logging
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        import inspect
        
        if inspect.iscoroutinefunction(func):
            # Async wrapper for async nodes
            @functools.wraps(func)
            async def async_wrapper(state: dict, *args, **kwargs):
                try:
                    logger.info(f"Executing node: {node_name}")
                    result = await func(state, *args, **kwargs)
                    logger.success(f"Node {node_name} completed successfully")
                    return result
                    
                except Exception as e:
                    # Capture full traceback
                    import traceback
                    error_msg = f"Node '{node_name}' failed: {str(e)}"
                    traceback_str = traceback.format_exc()
                    
                    logger.error(error_msg, exc_info=True)
                    
                    # Update state with error information
                    error_log = state.get('error_log', [])
                    error_log.append({
                        'node': node_name,
                        'error': str(e),
                        'type': type(e).__name__
                    })
                    
                    # Mark state as failed instead of crashing
                    return {
                        **state,  # Preserve all existing state
                        'processing_stage': 'FAILED',
                        'error_message': error_msg,
                        'traceback_info': traceback_str,
                        'error_log': error_log,
                        'failed_node': node_name
                    }
            
            return async_wrapper
        else:
            # Sync wrapper for sync nodes (like validation_node)
            @functools.wraps(func)
            def sync_wrapper(state: dict, *args, **kwargs):
                try:
                    logger.info(f"Executing node: {node_name}")
                    result = func(state, *args, **kwargs)
                    logger.success(f"Node {node_name} completed successfully")
                    return result
                    
                except Exception as e:
                    # Capture full traceback
                    import traceback
                    error_msg = f"Node '{node_name}' failed: {str(e)}"
                    traceback_str = traceback.format_exc()
                    
                    logger.error(error_msg, exc_info=True)
                    
                    # Update state with error information
                    error_log = state.get('error_log', [])
                    error_log.append({
                        'node': node_name,
                        'error': str(e),
                        'type': type(e).__name__
                    })
                    
                    # Mark state as failed instead of crashing
                    return {
                        **state,  # Preserve all existing state
                        'processing_stage': 'FAILED',
                        'error_message': error_msg,
                        'traceback_info': traceback_str,
                        'error_log': error_log,
                        'failed_node': node_name
                    }
            
            return sync_wrapper
            
    return decorator
