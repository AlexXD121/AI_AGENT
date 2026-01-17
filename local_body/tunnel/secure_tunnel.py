"""Secure tunnel management using ngrok for cloud-local communication.

This module implements the SecureTunnel class that manages ngrok tunnels
with HTTPS enforcement, health monitoring, and automatic failover.
"""

import atexit
import time
from typing import Optional, Dict

from loguru import logger
from pyngrok import ngrok, conf

from local_body.core.config_manager import SystemConfig


class SecureTunnel:
    """Manages ngrok tunnel for secure cloud-local communication.
    
    Features:
    - HTTPS-only tunnels (bind_tls=True)
    - Health monitoring with auto-reconnect
    - Graceful shutdown
    - Request signature validation (placeholder for Task 5.2)
    
    Requirements:
    - Req 2.2: HTTPS tunnels
    - Req 2.3: Encrypted payloads
    - Req 6.1: Ephemeral tunnels
    - Req 6.4: Failover and reconnection
    """
    
    def __init__(self, config: SystemConfig):
        """Initialize secure tunnel manager.
        
        Args:
            config: System configuration with ngrok token
        """
        self.config = config
        self.tunnel = None
        self.public_url = None
        self.port = 8000  # Default FastAPI port
        
        # Get ngrok token from config or environment
        ngrok_token = self._get_ngrok_token()
        
        if ngrok_token:
            # Authenticate ngrok (never log the token)
            ngrok.set_auth_token(ngrok_token)
            logger.info("ngrok authenticated successfully")
        else:
            logger.warning("No ngrok token configured. Tunnel may be limited.")
        
        # Register cleanup handler
        atexit.register(self._cleanup)
        logger.debug("SecureTunnel initialized")
    
    def _get_ngrok_token(self) -> Optional[str]:
        """Get ngrok token from config or environment.
        
        Returns:
            ngrok auth token or None
        """
        import os
        
        # Try to get from config first (if field exists)
        token = getattr(self.config, 'ngrok_token', None)
        
        # Fallback to environment variable
        if not token:
            token = os.getenv('NGROK_TOKEN') or os.getenv('NGROK_AUTH_TOKEN') or os.getenv('SOVEREIGN_NGROK_TOKEN')
        
        return token
    
    def start(self, port: Optional[int] = None) -> str:
        """Start HTTPS tunnel and return public URL.
        
        Args:
            port: Local port to expose (default: 8000)
            
        Returns:
            Public HTTPS URL string
            
        Raises:
            RuntimeError: If tunnel fails to start
        """
        if port:
            self.port = port
        
        try:
            logger.info(f"Starting ngrok tunnel on port {self.port}...")
            
            # Open tunnel with HTTPS enforcement (Req 2.2)
            self.tunnel = ngrok.connect(self.port, bind_tls=True)
            self.public_url = self.tunnel.public_url
            
            # Log success (securely - don't expose sensitive info)
            logger.success(f"Tunnel established: {self.public_url}")
            
            return self.public_url
            
        except Exception as e:
            logger.error(f"Failed to start tunnel: {e}")
            raise RuntimeError(f"Tunnel start failed: {e}")
    
    def stop(self):
        """Stop tunnel and cleanup resources.
        
        This disconnects the tunnel and kills the ngrok process
        to ensure clean shutdown (Req 6.1 - Ephemeral).
        """
        try:
            if self.tunnel:
                logger.info("Stopping tunnel...")
                ngrok.disconnect(self.tunnel.public_url)
                self.tunnel = None
                self.public_url = None
            
            # Kill ngrok process completely
            ngrok.kill()
            logger.info("Tunnel stopped and cleaned up")
            
        except Exception as e:
            logger.error(f"Error stopping tunnel: {e}")
    
    def monitor_health(self) -> bool:
        """Check tunnel health and auto-reconnect if down.
        
        This method checks if the tunnel is still active and
        attempts to reconnect if it's down (Req 6.4 - Failover).
        
        Returns:
            True if tunnel is healthy, False otherwise
        """
        try:
            # Get active tunnels
            tunnels = ngrok.get_tunnels()
            
            # Check if our tunnel is in the list
            if not tunnels:
                logger.warning("Tunnel connection lost. Attempting reconnect...")
                self.restart()
                return False
            
            # Verify our specific tunnel exists
            tunnel_exists = any(
                t.public_url == self.public_url for t in tunnels
            ) if self.public_url else False
            
            if not tunnel_exists and self.public_url:
                logger.warning(f"Tunnel {self.public_url} not found. Reconnecting...")
                self.restart()
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def restart(self):
        """Restart tunnel after connection loss.
        
        Implements failover logic (Req 6.4).
        """
        logger.info("Restarting tunnel...")
        
        try:
            # Save current port
            port = self.port
            
            # Stop existing tunnel
            self.stop()
            
            # Wait briefly before reconnecting
            time.sleep(2)
            
            # Start new tunnel
            self.start(port)
            
            logger.success("Tunnel restarted successfully")
            
        except Exception as e:
            logger.error(f"Failed to restart tunnel: {e}")
            raise
    
    def validate_request_signature(self, headers: Dict[str, str]) -> bool:
        """Validate incoming request signature.
        
        Placeholder for cryptographic validation (Task 5.2).
        Currently checks for presence of security header.
        
        Args:
            headers: Request headers dictionary
            
        Returns:
            True if request appears valid, False otherwise
        """
        # Check for security header (placeholder)
        signature_header = headers.get('X-Sovereign-Signature')
        
        if not signature_header:
            logger.warning("Request missing security signature header")
            return False
        
        # TODO: Implement actual cryptographic validation in Task 5.2
        # For now, just check presence
        logger.debug("Request signature header present")
        return True
    
    def _cleanup(self):
        """Cleanup handler called on exit.
        
        Ensures tunnel is stopped gracefully even if app crashes.
        """
        if self.tunnel:
            logger.info("Cleanup: Stopping tunnel on exit")
            self.stop()
    
    def get_status(self) -> Dict[str, any]:
        """Get current tunnel status information.
        
        Returns:
            Dictionary with tunnel status details
        """
        return {
            'active': self.tunnel is not None,
            'public_url': self.public_url,
            'port': self.port,
            'tunnels_count': len(ngrok.get_tunnels())
        }
