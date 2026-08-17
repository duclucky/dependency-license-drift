# Studionet Evidence

This directory stores sanitized Studionet deployment and lifecycle evidence.

Rules:

- Keep only allowlisted public fields such as network, source commit/hash, contract address, transaction hash, execution result, schema summary, and explorer URL.
- Do not store raw Studio receipts, traces, validator config, stdout, stderr, private keys, or `.env` values.
- Studionet only: do not mix other network addresses and receipts here.
