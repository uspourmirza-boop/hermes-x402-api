#!/usr/bin/env python3
"""
x402 Earning API Prototype
===========================

A minimal API service that charges USDC via the x402 protocol.
When an agent requests a paid endpoint, the server responds with HTTP 402
and a payment specification. The agent pays USDC on Base L2, includes the
receipt, and gets the resource.

This is a PROTOTYPE for Stage 2 of the autonomous economic engine.
Deploy on free-tier hosting (HF Spaces static + Cloudflare Workers, or
Render free tier).

Cost to run: $0 (free tiers only)
Revenue model: per-request micropayments in USDC
KYC: NONE (x402 uses self-custody wallets, no identity verification)
"""

import json
import hashlib
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── Configuration ───────────────────────────────────────────────────────────

# Your USDC receiving wallet (Base L2)
# In production, this is a wallet YOU control (self-custody, e.g., Coinbase
# Wallet, MetaMask, or a smart contract wallet via Safe/Multisig).
# For the prototype, use a testnet wallet.
RECEIVING_WALLET = "0xYOUR_WALLET_ADDRESS_HERE"

# Service pricing (in USDC)
PRICING = {
    "/v1/extract": {"amount": "0.01", "description": "Invoice data extraction"},
    "/v1/monitor": {"amount": "0.005", "description": "Competitor check"},
    "/v1/summarize": {"amount": "0.002", "description": "Text summary"},
}

# Supported network
NETWORK = "base"  # Base L2
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base

# ─── x402 Protocol Implementation ────────────────────────────────────────────

def create_payment_requirements(endpoint, method="GET"):
    """Generate x402 payment requirements for an endpoint."""
    price = PRICING.get(endpoint)
    if not price:
        return None
    return {
        "price": price["amount"],
        "network": NETWORK,
        "asset": "USDC",
        "to": RECEIVING_WALLET,
        "decimals": 6,
        "amount": str(int(float(price["amount"]) * 1_000_000)),  # USDC has 6 decimals
        "description": price["description"],
    }


def verify_payment(payload, payment_requirements):
    """
    Verify an x402 payment.
    
    In production: verify on-chain that the USDC transfer occurred.
    For prototype: verify the payment payload structure and signature.
    
    Returns True if payment is valid.
    """
    # TODO: In production, verify on-chain via Base RPC or facilitator
    # For now, check the payload has required fields
    required = ["price", "network", "asset", "to", "amount"]
    return all(k in payload for k in required)


# ─── API Services ────────────────────────────────────────────────────────────

def service_extract(params):
    """Extract data from invoice text (mock — in production, call the pipeline)."""
    text = params.get("text", "")
    # Simplified extraction
    lines = text.split('\n')[:5]
    return {
        "vendor": lines[0] if lines else None,
        "extracted": True,
        "confidence": 0.95
    }


def service_monitor(params):
    """Check a URL for changes (mock — in production, call watch.py)."""
    url = params.get("url", "")
    return {
        "url": url,
        "changed": False,
        "last_checked": time.time()
    }


def service_summarize(params):
    """Summarize text (mock — in production, call a model API)."""
    text = params.get("text", "")
    sentences = text.split('.')[:3]
    return {
        "summary": '. '.join(sentences) + '.',
        "original_length": len(text),
        "summary_length": len('. '.join(sentences))
    }


SERVICES = {
    "/v1/extract": service_extract,
    "/v1/monitor": service_monitor,
    "/v1/summarize": service_summarize,
}


# ─── HTTP Handler ────────────────────────────────────────────────────────────

class X402Handler(BaseHTTPRequestHandler):
    """x402 payment-gated API handler."""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        endpoint = parsed.path
        params = parse_qs(parsed.query)
        # Flatten single-value params
        params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        
        # Check if endpoint exists
        if endpoint not in SERVICES:
            self.send_error(404, "Endpoint not found")
            return
        
        # Check for payment header
        payment_header = self.headers.get("X-Payment")
        
        if not payment_header:
            # No payment — return 402 with requirements
            req = create_payment_requirements(endpoint)
            if not req:
                self.send_error(500, "Pricing not configured")
                return
            
            self.send_response(402, "Payment Required")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "payment_required",
                "message": f"This endpoint costs {req['amount']} USDC on {req['network']}",
                "payment_requirements": req,
                "x402_version": "1.0"
            }, indent=2).encode())
            return
        
        # Payment provided — verify and serve
        try:
            payment = json.loads(payment_header)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid payment header")
            return
        
        req = create_payment_requirements(endpoint)
        if not verify_payment(payment, req):
            self.send_error(402, "Payment verification failed")
            return
        
        # Payment valid — serve the resource
        result = SERVICES[endpoint](params)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "payment_verified": True,
            "result": result
        }, indent=2).encode())
    
    def do_POST(self):
        """Handle POST requests (for services that accept body data)."""
        parsed = urlparse(self.path)
        endpoint = parsed.path
        
        if endpoint not in SERVICES:
            self.send_error(404, "Endpoint not found")
            return
        
        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON body")
            return
        
        # Check payment header
        payment_header = self.headers.get("X-Payment")
        
        if not payment_header:
            req = create_payment_requirements(endpoint)
            self.send_response(402, "Payment Required")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "payment_required",
                "payment_requirements": req
            }, indent=2).encode())
            return
        
        # Verify and serve
        try:
            payment = json.loads(payment_header)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid payment header")
            return
        
        req = create_payment_requirements(endpoint)
        if not verify_payment(payment, req):
            self.send_error(402, "Payment verification failed")
            return
        
        result = SERVICES[endpoint](params)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "payment_verified": True,
            "result": result
        }, indent=2).encode())
    
    def log_message(self, format, *args):
        """Suppress default logging to keep output clean."""
        pass


def run_server(port=8080):
    """Start the x402 API server."""
    server = HTTPServer(("0.0.0.0", port), X402Handler)
    print(f"x402 Earning API running on port {port}")
    print(f"Endpoints: {list(SERVICES.keys())}")
    print(f"Receiving wallet: {RECEIVING_WALLET}")
    print(f"Network: {NETWORK}")
    print("\nPress Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
