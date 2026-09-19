# Hermes x402 Earning API

> **Agent-to-agent micropayment API.** Charge AI agents USDC for API calls via the HTTP 402 protocol. No KYC. No accounts. No API keys.

## What It Is

A minimal, production-pattern API server that charges **USDC on Base L2** for each API call. When an AI agent requests an endpoint without payment, the server responds with HTTP 402 + payment specification. The agent signs a USDC transfer, includes the receipt in the request header, and gets the resource.

**Cost to run: $0** (free-tier hosting)
**KYC: NONE** (self-custody wallets only)
**Settlement time: ~2 seconds** (Base L2)

## The Protocol

```
Client                          Server
  |                               |
  |── GET /v1/extract ──────────▶|
  |                               |
  |◀── 402 Payment Required ─────|
  |    {price: 0.01,             |
  |     network: base,            |
  |     asset: USDC,              |
  |     to: 0xYOUR_WALLET}        |
  |                               |
  |── [Agent signs USDC tx] ─────|
  |                               |
  |── GET /v1/extract ──────────▶|
  |    X-Payment: {signed tx}     |
  |                               |
  |◀── 200 OK ───────────────────|
  |    {result: {...}}            |
```

## Quick Start

```bash
# Clone
git clone https://github.com/uspourmirza-boop/hermes-x402-api.git
cd hermes-x402-api

# Configure (set your Base L2 wallet)
# Edit src/api.py: RECEIVING_WALLET = "0x..."

# Run locally
python src/api.py 8080

# Test
curl http://localhost:8080/v1/extract
# → 402 with payment requirements

curl -H 'X-Payment: {"price":"0.01","network":"base","asset":"USDC","to":"0x...","amount":"10000"}' \
     http://localhost:8080/v1/extract?text=invoice+text
# → 200 with result
```

## Endpoints

| Endpoint | Price (USDC) | Description |
|----------|--------------|-------------|
| `/v1/extract` | $0.01 | Invoice data extraction |
| `/v1/monitor` | $0.005 | Competitor check |
| `/v1/summarize` | $0.002 | Text summary |

## Deployment

Designed for free-tier hosting:

- **Hugging Face Spaces** (static + Gradio wrapper)
- **Cloudflare Workers** (serverless, 100K req/day free)
- **Render** (free tier)
- **Fly.io** (free allowance)

```bash
# Build for static upload
cd src && zip -r ../hermes-x402-api.zip api.py

# Upload to your chosen platform
```

## Why x402 Matters

Traditional payments assume a human with a credit card. AI agents:
- Don't have credit cards
- Make hundreds of sub-cent calls/minute
- Can't share credentials securely

x402 solves this: agents sign transactions with their own wallet, pay per-call, and the protocol settles on-chain in ~2 seconds at sub-cent gas.

The x402 Foundation launched July 2026 with 40+ tech companies. Coinbase, Stripe, Visa, and Mastercard are building agent-payment infrastructure. This prototype puts Hermes on the earning side.

## License

MIT — use commercially, modify, redistribute. No attribution required.

## Part of the Hermes Economic Engine

This is **Stage 2** infrastructure — the answer to "how does an AI earn money autonomously without a human's bank account?" x402 + self-custody USDC wallet = fully autonomous revenue.

See the [full plan](https://github.com/uspourmirza-boop) for Stage 0-4 architecture.
