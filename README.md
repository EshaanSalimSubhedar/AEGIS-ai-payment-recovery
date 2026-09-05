# AI Failed-Payment Recovery Agent

MVP implementation based on the supplied Razorpay Hackathon Track 03 specification. The architecture follows the requested FastAPI + SQLite/SQLAlchemy + React/Vite stack, with rule-based classification, recovery scoring, action planning, audit logging, stopping-rule helpers, and a live dashboard.

## Run backend
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

## Run frontend
```bash
cd frontend
npm install
npm run dev
```

## Demo ingestion
```bash
curl -X POST http://localhost:8000/ingest -H "Content-Type: application/json" -d "{\"razorpay_payment_id\":\"pay_demo_001\",\"customer_name\":\"Asha\",\"customer_contact\":\"9999999999\",\"amount\":1499,\"error_code\":\"BAD_REQUEST_ERROR\",\"error_description\":\"insufficient funds\"}"
```

## Next integration steps
- Wire Razorpay test-mode webhooks into `/ingest`.
- Add Groq API with `fallback_message()` as the explicit failure path.
- Add Twilio/WhatsApp dispatcher.
- Add APScheduler jobs for 2-hour cooldown and PTP dates.
- Enforce audit-before-money-action transactionally.
- Add tests for LLM/API timeout and malformed webhook payloads.
