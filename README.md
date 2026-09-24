# AegisEHR - Decentralized Healthcare Framework (Algorand TestNet)

AegisEHR is a production-ready decentralized Electronic Health Record (EHR) platform combining **Django 5.2**, **Algorand Pure Proof-of-Stake TestNet**, **AES-256-GCM authenticated encryption**, dynamic patient-centric consent controls, and cryptographic audit logging.

---

## 🚀 Fast 1-Click Deployment on Render

This repository is pre-configured with a Render Blueprint (`render.yaml`) and build pipeline (`build.sh`) for automatic deployment with a free PostgreSQL database and web service.

### Quick Deploy via Render Blueprint (Recommended)
1. In your [Render Dashboard](https://dashboard.render.com), click **+ New** (top right) &rarr; **Blueprint**.
2. Select your repository: **`sirkays/AegisEHR`**.
3. Render automatically detects `render.yaml` and sets up:
   - **Database**: Free Managed PostgreSQL (`aegisehr-db`)
   - **Web Service**: Free Python Web Service (`aegisehr`) with Gunicorn & Whitenoise
   - **Environment Variables**: Automatic `DATABASE_URL`, `SECRET_KEY`, and Algorand TestNet endpoints
4. Click **Apply**.
5. Render will run `build.sh` (installs dependencies, collects static assets, runs migrations, and seeds demo accounts) and launch the portal live!

---

## 🔑 Pre-Configured Demo Accounts

All accounts share the default development password: **`demo12345`**

| Role | Username | Password | Purpose & Capabilities |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin_auditor` | `demo12345` | Administrative provider verification, consensus audit trail |
| **Verified Doctor** | `dr_smith` | `demo12345` | Dr. Evelyn Smith; record upload, consent requests, decryption |
| **Unverified Doctor** | `dr_jones` | `demo12345` | Dr. Robert Jones; demonstration of pending clinician status |
| **Patient 1** | `alice_patient` | `demo12345` | Alice Williams; record owner with active consent permissions |
| **Patient 2** | `bob_patient` | `demo12345` | Bob Miller; orthopedic records |

---

## ⛓️ Algorand TestNet Integration

- **Algod API**: `https://testnet-api.algonode.cloud`
- **Indexer API**: `https://testnet-idx.algonode.cloud`
- **Explorer Links**: All blockchain transactions are directly linked to public explorers:
  - [Pera Wallet TestNet Explorer](https://testnet.explorer.perawallet.app/)
  - [Lora AlgoKit Explorer](https://lora.algokit.io/testnet/)
- **TestNet Faucet**: [Algorand Dispenser](https://bank.testnet.algorand.network/)

---

## 💻 Local Development

```bash
# 1. Create virtual environment and install packages
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# 2. Run migrations and seed data
python manage.py migrate
python manage.py seed_data

# 3. Start development server
python manage.py runserver
```
