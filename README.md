# Euclid Swap Bot (Testnet)

Automated bot for PLUME ↔ STT and PHRS ↔ ETH (Pharos ↔ Unichain) swaps on Euclid testnet with professional CLI output and immediate tracking.

## Features
- PLUME ↔ STT same-chain swaps
- PHRS ↔ ETH cross-chain swaps (meta preserved, immediate tracking)
- Route discovery and slippage protection
- Informative CLI output
- Optional adaptive amount configuration (token-agnostic)

## Setup
1. (Optional) Create a virtual environment and activate it
2. Install dependencies
3. Create a `.env` file with your private key
4. Run the bot

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
copy NUL .env
```

Edit `.env`:
```
PRIVATE_KEY=0xYOUR_PRIVATE_KEY
```

Run:
```bash
python main.py
```

## Sensitive Files (do not commit)
- `.env`
- `referral_config.json`
- `config/adaptive_config.json`

## Initialize and push to GitHub
```bash
git init
git remote add origin https://github.com/<your-username>/<your-repo>.git
# If repo already exists remotely, fetch first
git fetch origin
# Add .gitignore, then stage and commit
git add .
git commit -m "feat: euclid swap bot initial import"
# Create main branch if needed
git branch -M main
# Push
git push -u origin main
```

## Update an existing repository
```bash
# Verify remote
git remote -v
# Pull latest (rebase preferred)
git pull --rebase origin main
# Stage + commit
git add -A
git commit -m "feat: update euclid bot (menu, cross-chain, tracking)"
# Push
git push origin main
```

## Notes
- Never commit private keys, seed phrases, API keys, or passwords
- Use `.env` for secrets (already ignored)
- Referral config is local-only and ignored by git
