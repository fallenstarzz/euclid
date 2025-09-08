#!/usr/bin/env python3
"""
Somnia Chain Connector for Native STT Balance
Simple connector untuk real-time STT balance dari Somnia network
"""

import os
import ssl
import urllib3
from web3 import Web3
import logging

# Fix SSL issues
for var in ['SSLKEYLOGFILE', 'SSL_KEY_LOG_FILE', 'WIRESHARK_SSL_KEYLOG', 'TLS_KEYLOG_FILE']:
    os.environ.pop(var, None)

os.environ['PYTHONHTTPSVERIFY'] = '0'
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context

class SomniaChainConnector:
    """Connector untuk Somnia chain - native STT balance"""
    
    def __init__(self):
        # Somnia network configuration
        self.chain_id = 50312
        self.rpc_url = "https://dream-rpc.somnia.network/"
        self.explorer_url = "https://shannon-explorer.somnia.network/"
        self.symbol = "STT"
        
        # Connection
        self.web3 = None
        self.connected = False
        
        # Stats
        self.query_count = 0
        self.error_count = 0
        
        self._connect()
    
    def _connect(self):
        """Connect to Somnia network"""
        try:
            print(f"🔗 Connecting to Somnia (Chain ID: {self.chain_id})...")
            
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            
            # Test connection
            chain_id = self.web3.eth.chain_id
            if chain_id == self.chain_id:
                self.connected = True
                print(f"✅ Connected to Somnia successfully!")
                return True
            else:
                print(f"❌ Chain ID mismatch: expected {self.chain_id}, got {chain_id}")
                
        except Exception as e:
            print(f"❌ Somnia connection failed: {e}")
            self.connected = False
            
        return False
    
    def get_stt_balance(self, address: str) -> dict:
        """Get native STT balance for address"""
        self.query_count += 1
        
        try:
            if not self.connected:
                self.error_count += 1
                return {
                    "success": False,
                    "error": "Not connected to Somnia",
                    "balance": {"raw": 0, "formatted": 0.0}
                }
            
            # Convert address to checksum
            checksum_address = self.web3.to_checksum_address(address)
            
            # Get native token balance (STT)
            balance_wei = self.web3.eth.get_balance(checksum_address)
            
            # Convert from wei to STT (18 decimals)
            balance_stt = float(self.web3.from_wei(balance_wei, 'ether'))
            
            return {
                "success": True,
                "balance": {
                    "raw": balance_wei,
                    "formatted": balance_stt
                },
                "address": checksum_address,
                "symbol": self.symbol,
                "chain_id": self.chain_id
            }
            
        except Exception as e:
            self.error_count += 1
            return {
                "success": False,
                "error": str(e),
                "balance": {"raw": 0, "formatted": 0.0}
            }
    
    def get_stats(self) -> dict:
        """Get connection stats"""
        return {
            "connected": self.connected,
            "chain_id": self.chain_id,
            "rpc_url": self.rpc_url,
            "queries": self.query_count,
            "errors": self.error_count,
            "success_rate": ((self.query_count - self.error_count) / max(self.query_count, 1)) * 100
        }
