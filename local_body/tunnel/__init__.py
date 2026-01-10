"""Secure tunneling module for cloud-local communication.

This module provides the SecureTunnel class for managing ngrok tunnels
to expose the Local Body to the Cloud Brain securely.
"""

from local_body.tunnel.secure_tunnel import SecureTunnel

__all__ = ["SecureTunnel"]
