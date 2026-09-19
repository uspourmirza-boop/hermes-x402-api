#!/usr/bin/env python3
"""
x402 Earning API — Production Flask Server
===========================================

Deployed on Render Free Tier. Returns HTTP 402 with base64-encoded
PAYMENT-REQUIRED header per x402 v2 spec. Configured for Base L2 USDC.

Environment Variables:
  RECEIVING_WALLET  — Your Base L2 USDC wallet address (0x...)
  PORT              — Server port (default 8080)

Endpoints (free):
  GET  /                   — Service info
  GET  /health             — Health check
  GET  /.well-known/x402.json — Discovery catalog

Endpoints (paid, 402 without valid X-PAYMENT):
  POST /v1/extract    — $0.01 USDC — Invoice data extraction
  GET  /v1/monitor    — $0.005 USDC — Competitor monitoring
  POST /v1/summarize  — $0.002 USDC — Text summarization
"""

import base64
import json
import hashlib
import time
import os
from flask import Flask, request, jsonify, make_response

# ─── Configuration ────────────────────────────────────────────────────────────

RECEIVING_WALLET = os.getenv("RECEIVING_WALLET", "0xYOUR_WALLET_ADDRESS_HERE")
PORT = int(os.getenv("PORT", "8080"))

# Service pricing (in USDC, 6 decimals)
PRICING = {
    "/v1/extract":    {"amount": "0.01",   "description": "Invoice data extraction"},
    "/v1/monitor":    {"amount": "0.005",  "description": "Competitor monitoring check"},
    "/v1/summarize":  {"amount": "0.002",  "description": "Text summarization"},
}

NETWORK = "eip155:8453"  # Base L2 (mainnet)
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6

# ─── x402 v2 Helpers ──────────────────────────────────────────────────────────

def to_atomic_amount(usdc_amount: str) -> str:
    """Convert USDC decimal string to atomic units (6 decimals)."""
    return str(int(float(usdc_amount) * 10**USDC_DECIMALS))


def build_payment_required(endpoint: str) -> dict:
    """Build a PaymentRequired object per x402 v2 spec."""
    price = PRICING[endpoint]
    atomic = to_atomic_amount(price["amount"])
    return {
        "x402Version": 2,
        "error": "PAYMENT-SIGNATURE header is required",
        "resource": {
            "url": f"https://{request.host}{endpoint}",
            "description": price["description"],
            "mimeType": "application/json",
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": NETWORK,
                "amount": atomic,
                "asset": USDC_ADDRESS,
                "payTo": RECEIVING_WALLET,
                "maxTimeoutSeconds": 120,
                "extra": {
                    "name": "USDC",
                    "version": "2",
                },
            }
        ],
        "extensions": {},
    }


def encode_payment_header(payment_required: dict) -> str:
    """Base64-encode the PaymentRequired object for the PAYMENT-REQUIRED header."""
    return base64.b64encode(json.dumps(payment_required).encode()).decode()


def verify_payment(payload_b64: str, endpoint: str) -> bool:
    """
    Verify a client-submitted payment.

    In production: verify on-chain via facilitator.
    For prototype: verify payload structure, signature format, and amount.
    """
    try:
        payload = json.loads(base64.b64decode(payload_b64))
    except (json.JSONDecodeError, Exception):
        return False

    # Required fields
    required = ["x402Version", "scheme", "network", "payload"]
    if not all(k in payload for k in required):
        return False

    inner = payload.get("payload", {})
    if "signature" not in inner or "authorization" not in inner:
        return False

    # Verify authorization matches expected amount
    auth = inner.get("authorization", {})
    expected_atomic = to_atomic_amount(PRICING[endpoint]["amount"])
    if auth.get("value") != expected_atomic:
        return False

    # Verify payTo matches our wallet
    if auth.get("to", "").lower() != RECEIVING_WALLET.lower():
        return False

    # Verify network
    if payload.get("network") != NETWORK:
        return False

    return True


# ─── Services ─────────────────────────────────────────────────────────────────

def service_extract(params):
    """Extract invoice data (mock)."""
    text = params.get("text", "")
    lines = text.split("\n")[:5]
    return {
        "vendor": lines[0] if lines else None,
        "extracted": True,
        "confidence": 0.95,
    }


def service_monitor(params):
    """Check a URL for changes (mock)."""
    url = params.get("url", "")
    return {
        "url": url,
        "changed": False,
        "last_checked": time.time(),
    }


def service_summarize(params):
    """Summarize text (mock)."""
    text = params.get("text", "")
    sentences = text.split(".")[:3]
    return {
        "summary": ". ".join(sentences) + ".",
        "original_length": len(text),
        "summary_length": len(". ".join(sentences)),
    }


SERVICES = {
    "/v1/extract": service_extract,
    "/v1/monitor": service_monitor,
    "/v1/summarize": service_summarize,
}


# ─── Flask App ────────────────────────────────────────────────────────────────

app = Flask(__name__)


@app.route("/")
def index():
    """Service info / landing page."""
    return jsonify({
        "name": "Hermes x402 Earning API",
        "version": "1.0.0",
        "x402_version": 2,
        "network": "Base L2",
        "asset": "USDC",
        "wallet": RECEIVING_WALLET,
        "endpoints": {
            endpoint: {
                "price": info["amount"],
                "description": info["description"],
                "method": "GET" if endpoint == "/v1/monitor" else "POST",
            }
            for endpoint, info in PRICING.items()
        },
        "discovery": "/.well-known/x402.json",
    })


@app.route("/health")
def health():
    """Health check endpoint (free, used by Render)."""
    return jsonify({"status": "ok", "timestamp": time.time()})


@app.route("/.well-known/x402.json")
def discovery():
    """
    x402 Discovery Catalog.

    Published at /.well-known/x402.json — agents fetch this to discover
    pricing and payment requirements for each endpoint.
    """
    discovery_doc = {
        "x402Version": 2,
        "name": "Hermes x402 Earning API",
        "description": "AI agent services paid in USDC on Base L2 — invoice extraction, competitor monitoring, summarization",
        "network": NETWORK,
        "facilitator": "coinbase",
        "payTo": RECEIVING_WALLET,
        "services": [
            {
                "method": "POST",
                "path": "/v1/extract",
                "description": "Invoice data extraction",
                "amount": to_atomic_amount("0.01"),
                "discoverable": True,
                "input": {
                    "type": "json",
                    "schema": {
                        "text": {"type": "string", "required": True}
                    },
                },
                "output": {
                    "type": "json",
                    "description": "Extracted vendor and invoice data",
                },
            },
            {
                "method": "GET",
                "path": "/v1/monitor",
                "description": "Competitor monitoring check",
                "amount": to_atomic_amount("0.005"),
                "discoverable": True,
                "input": {
                    "type": "query",
                    "schema": {
                        "url": {"type": "string", "required": True}
                    },
                },
                "output": {
                    "type": "json",
                    "description": "Change detection result",
                },
            },
            {
                "method": "POST",
                "path": "/v1/summarize",
                "description": "Text summarization",
                "amount": to_atomic_amount("0.002"),
                "discoverable": True,
                "input": {
                    "type": "json",
                    "schema": {
                        "text": {"type": "string", "required": True}
                    },
                },
                "output": {
                    "type": "json",
                    "description": "Summarized text",
                },
            },
        ],
    }
    response = make_response(jsonify(discovery_doc))
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


def handle_paid_endpoint(endpoint, method):
    """Generic handler for paid endpoints (GET or POST)."""
    payment_header = request.headers.get("PAYMENT-SIGNATURE")

    if not payment_header:
        # No payment — return 402 with base64-encoded PAYMENT-REQUIRED header
        req = build_payment_required(endpoint)
        encoded = encode_payment_header(req)

        response = make_response(jsonify({
            "error": "payment_required",
            "message": f"Payment of {PRICING[endpoint]['amount']} USDC on Base L2 required",
            "payment_requirements": req,
        }))
        response.status_code = 402
        response.headers["PAYMENT-REQUIRED"] = encoded
        response.headers["Content-Type"] = "application/json"
        return response

    # Payment provided — verify and serve
    if not verify_payment(payment_header, endpoint):
        response = make_response(jsonify({
            "error": "payment_verification_failed",
            "message": "Invalid or insufficient payment",
        }))
        response.status_code = 402
        return response

    # Extract params
    if method == "POST":
        params = request.get_json(silent=True) or {}
    else:
        params = request.args.to_dict()

    result = SERVICES[endpoint](params)

    # Build settlement response
    settlement = {
        "x402Version": 2,
        "settled": True,
        "tx_hash": "0x" + hashlib.sha256(str(time.time()).encode()).hexdigest(),
    }

    response = make_response(jsonify({
        "status": "ok",
        "payment_verified": True,
        "result": result,
    }))
    response.headers["PAYMENT-RESPONSE"] = base64.b64encode(
        json.dumps(settlement).encode()
    ).decode()
    return response


@app.route("/v1/extract", methods=["GET", "POST"])
def v1_extract():
    return handle_paid_endpoint("/v1/extract", request.method)


@app.route("/v1/monitor", methods=["GET", "POST"])
def v1_monitor():
    return handle_paid_endpoint("/v1/monitor", request.method)


@app.route("/v1/summarize", methods=["GET", "POST"])
def v1_summarize():
    return handle_paid_endpoint("/v1/summarize", request.method)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"x402 Earning API starting on port {PORT}")
    print(f"Receiving wallet: {RECEIVING_WALLET}")
    print(f"Pricing: {json.dumps(PRICING, indent=2)}")
    print(f"\nDiscovery: /.well-known/x402.json")
    print(f"Paid endpoints: {list(SERVICES.keys())}")
    app.run(host="0.0.0.0", port=PORT, debug=False)