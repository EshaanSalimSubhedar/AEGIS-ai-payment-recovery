# AEGIS — AI Payment Recovery Agent

> An explainable AI-powered revenue recovery system that diagnoses failed payments, predicts recovery potential, selects the safest recovery strategy, and tracks recovered revenue.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Razorpay](https://img.shields.io/badge/Razorpay-Test%20Mode-3395FF?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-Llama%203.3%2070B-F55036?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

---

## Overview

Failed payments represent potentially recoverable revenue, but simply retrying every failed transaction is neither effective nor safe.

**AEGIS** (AI Payment Recovery Agent) is an automated revenue recovery system designed to make failure-aware recovery decisions.

Instead of treating every failed payment identically, AEGIS:

1. Detects failed payments
2. Classifies the failure reason
3. Calculates a recovery probability score
4. Selects an appropriate recovery strategy
5. Generates a personalized customer message
6. Executes or schedules the recovery action
7. Tracks customer responses and Promise-to-Pay commitments
8. Enforces retry limits, cooldowns, and opt-out rules
9. Records an explainable audit trail
10. Measures the revenue actually recovered

The central objective is simple:

> **Recover more revenue without blindly retrying payments or over-contacting customers.**

---

# Why AEGIS?

A failed payment does not always mean the same thing.

| Failure Reason | Example Recovery Strategy |
|---|---|
| Bank Timeout | Immediate Retry |
| Network Error | Delayed Retry |
| Insufficient Funds | Delayed Retry |
| Card Expired | Payment Link |
| Authentication Failed | Payment Link |
| Issuer Declined | Human Review / Delayed Retry |
| Limit Exceeded | Human Review |
| Fraud Review | Human Review |
| Unknown Failure | Human Review |

This makes AEGIS a **decision system**, rather than simply a payment retry script or an LLM-powered chatbot.

---

# Core Architecture

```text
                         ┌─────────────────────┐
                         │   Failed Payment     │
                         │ Razorpay / Webhook   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Failure Classifier  │
                         │                     │
                         │ Rules + Error Codes │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Recovery Scoring   │
                         │                     │
                         │ Failure + Context   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Action Planner    │
                         │                     │
                         │ Retry / Link /      │
                         │ Human Review /      │
                         │ Abandon             │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
              Immediate         Delayed          Payment
                Retry            Retry             Link
                    │               │                │
                    └───────────────┼────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Message Composer    │
                         │                     │
                         │ Groq / Llama 3.3    │
                         │ + Static Fallback   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Messaging Layer     │
                         │                     │
                         │ Twilio SMS          │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Customer Response   │
                         │                     │
                         │ Payment / PTP /     │
                         │ Opt-out             │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Outcome Tracking    │
                         │                     │
                         │ ₹ Recovered         │
                         │ Audit Trail         │
                         └─────────────────────┘
Key Features
1. Failure Classification

AEGIS identifies the underlying failure category using payment error codes and failure descriptions.

Supported categories include:

Insufficient Funds
Bank Timeout
Network Error
Card Expired
Issuer Declined
Authentication Failed
Limit Exceeded
Fraud Review
Unknown Failure
2. Recovery Scoring

Each failed payment receives a deterministic recovery score between 0 and 1.

The score considers factors such as:

Failure category
Payment amount
Time since failure
Optional customer history score

Scores are categorized as:

0.70+      → High
0.45–0.69  → Medium
< 0.45     → Low

The score helps the action planner choose an appropriate recovery strategy.

3. Intelligent Action Planning

AEGIS routes payments to different recovery strategies based on failure type, recovery probability, previous attempts, and safety constraints.

Possible actions:

IMMEDIATE_RETRY
DELAYED_RETRY
PAYMENT_LINK
HUMAN_REVIEW
ABANDON

This allows the system to adapt its recovery behavior instead of applying a single retry policy to every customer.

4. AI-Powered Customer Messaging

AEGIS uses Groq with Llama 3.3 70B to generate personalized recovery messages.

The LLM receives structured recovery context such as:

Customer name
Amount
Failure reason
Recovery action
Preferred language
Payment link when applicable

The LLM is intentionally limited to the communication layer.

Financially sensitive decisions remain controlled by the deterministic recovery engine.

Example

Input

Customer: Priya
Amount: ₹4,999
Failure: insufficient_funds
Action: delayed_retry
Language: English

Generated message

Hi Priya, your ₹4,999 payment couldn't be completed because
there were insufficient funds. We'll retry the payment later.
Please make sure sufficient funds are available.
Graceful LLM Failure

If Groq is unavailable, AEGIS automatically falls back to predefined recovery templates.

The fallback is also recorded in the audit trail.

Groq Available
      │
      ▼
Llama-generated message
      │
      ▼
Customer

Groq Unavailable
      │
      ▼
Static recovery template
      │
      ▼
Customer
5. Razorpay Integration

AEGIS is designed for Razorpay Test Mode.

The recovery connector supports:

Failed payment retrieval
Payment failure ingestion
Recovery Order creation
Payment Link creation
Provider API retry with bounded exponential backoff

Recovery attempts create a fresh recovery flow rather than attempting to mutate an already-failed payment transaction.

6. Customer Messaging

The messaging layer supports Twilio-based SMS delivery.

The system separates message composition from message delivery so that additional communication channels can be added later.

Recovery Decision
       ↓
Message Composer
       ↓
Channel Dispatcher
       ↓
Twilio SMS
7. Promise-to-Pay Tracking

Customers can respond with commitments such as:

I'll pay tomorrow

AEGIS can detect a Promise-to-Pay response and record the commitment for follow-up.

This prevents the system from treating a customer who has already committed to paying the same way as an unresponsive customer.

8. Opt-Out Protection

Customers can opt out using keywords such as:

STOP
NO
UNSUBSCRIBE
CANCEL

Once an opt-out is received, automated recovery communication is blocked.

9. Stopping Rules

Recovery automation is deliberately bounded.

Maximum Attempts
Maximum automated attempts = 3
Cooldown
Minimum recovery cooldown = 2 hours
Automatic Abandonment

Payments are abandoned when:

Maximum attempts are reached
Recovery is no longer appropriate
The customer has opted out
The case requires human intervention

The objective is:

Do not optimize recovery at the expense of customer experience or uncontrolled payment attempts.

10. Explainable Audit Trail

Every important action is recorded.

Example:

PAYMENT_INGESTED
       ↓
FAILURE_CLASSIFIED
       ↓
RECOVERY_SCORED
       ↓
ACTION_PLANNED
       ↓
RETRY_SCHEDULED
       ↓
MESSAGE_GENERATED
       ↓
MESSAGE_SENT
       ↓
PAYMENT_RECOVERED

Money-related actions are audited before execution.

This provides a traceable explanation of:

What the agent decided
Why it decided it
What action was executed
What happened afterward
11. Revenue Metrics

AEGIS focuses on measurable financial outcomes.

The dashboard tracks:

Total Failed Revenue
Recovered Revenue
Recovery Rate
Failure Reason Breakdown
Exceptions
Escalated Cases
Recovery Attempts
Recovery Rate
Recovery Rate =
Recovered Revenue / Total Failed Revenue × 100

The primary success metric is therefore:

₹ actually recovered

rather than the number of retries or messages generated.

Tech Stack
Backend
Technology	Purpose
Python	Core backend
FastAPI	REST API
SQLAlchemy	Database ORM
SQLite	Local persistence
APScheduler	Retry and follow-up scheduling
Pydantic	Data validation
HTTPX	HTTP communication
PyYAML	Configuration
Razorpay SDK	Payment integration
Groq SDK	LLM integration
Twilio SDK	Messaging
AI
Groq
└── Llama 3.3 70B Versatile

Used for:

Personalized recovery messages
Language-aware communication
Customer-facing message generation

The financial recovery decision itself is handled by deterministic scoring and action-planning logic.

Frontend
Technology	Purpose
React	UI
Vite	Frontend tooling
Tailwind CSS	Styling
Axios	API communication
TanStack React Query	Data fetching/state
Recharts	Metrics visualization
Lucide React	UI icons
Project Structure
recovery-agent/
│
├── backend/
│   ├── audit/
│   │   └── audit_log.py
│   │
│   ├── classifier/
│   │   ├── rules_engine.py
│   │   └── risk_scorer.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   │
│   ├── ingestion/
│   │   ├── schema.py
│   │   └── razorpay_connector.py
│   │
│   ├── messaging/
│   │   ├── channel_dispatcher.py
│   │   └── llm_composer.py
│   │
│   ├── strategy/
│   │   └── action_planner.py
│   │
│   ├── tracker/
│   │   └── stopping_rules.py
│   │
│   ├── app.py
│   └── scheduler.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── ...
│   └── package.json
│
├── config/
│   └── settings.yaml
│
├── tests/
│   ├── test_api.py
│   └── test_edge_cases.py
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
Getting Started
Prerequisites
Python 3.11+
Node.js 18+
npm
Razorpay Test Mode credentials
Groq API key
Twilio credentials for live SMS testing
1. Clone the Repository
git clone https://github.com/EshaanSalimSubhedar/AEGIS-ai-payment-recovery.git
cd AEGIS-ai-payment-recovery
2. Create Python Virtual Environment
Windows
python -m venv .venv
.venv\Scripts\activate
macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
3. Install Backend Dependencies
pip install -r requirements.txt
4. Configure Environment Variables

Create a .env file in the project root.

APP_ENVIRONMENT=development
APP_TIMEZONE=Asia/Kolkata

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_DEMO_MODE=true

GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

MAX_ATTEMPTS=3
COOLDOWN_HOURS=2

RAZORPAY_API_MAX_ATTEMPTS=2
RAZORPAY_API_INITIAL_DELAY_SECONDS=1
RAZORPAY_API_BACKOFF_MULTIPLIER=2

Never commit .env or API credentials to Git.

Running the Backend

From the project root:

uvicorn backend.app:app --reload

The API will be available at:

http://127.0.0.1:8000

FastAPI documentation:

http://127.0.0.1:8000/docs
Running the Frontend

Open another terminal:

cd frontend
npm install
npm run dev

The frontend will normally be available at:

http://localhost:5173
Demo Mode

AEGIS includes demo-mode support so the complete recovery workflow can be demonstrated without moving real money.

Demo cases cover multiple failure scenarios, including:

Bank timeout
Insufficient funds
Expired card
Issuer decline
Network failure
Fraud review

The dashboard supports loading and unloading demo data.

For a hackathon demonstration, the recommended flow is:

Load Demo Data
      ↓
Select Failed Payment
      ↓
View Failure Classification
      ↓
View Recovery Score
      ↓
View Recommended Action
      ↓
Execute Recovery
      ↓
View Customer Message
      ↓
View Audit Trail
      ↓
Simulate / Confirm Recovery
      ↓
Recovered ₹ Updates

Demo mode is designed to prevent accidental real-money transactions.

API Overview
Endpoint	Purpose
GET /health	Service health
GET /payments	List failed payments
GET /payments/{id}	Payment details
GET /payments/{id}/audit	Payment audit trail
POST /ingest	Ingest failed payment
POST /webhook	Process payment webhook
POST /webhook/reply	Process customer response
POST /payments/{id}/recover	Mark payment recovered
GET /metrics	Revenue recovery metrics
GET /exceptions	Escalated/abandoned cases
DELETE /demo-data	Remove demo cases
Testing

Run the complete test suite:

pytest

The project includes tests covering:

Failure classification
Recovery scoring
Action planning
Stopping rules
Opt-out behavior
Payment ingestion
Recovery workflows
Metrics
API behavior
Edge cases
Safety & Reliability

AEGIS is designed with several safeguards.

Bounded Recovery

Automated recovery is capped at three attempts.

Cooldown Enforcement

Repeated recovery actions cannot occur within the configured cooldown period.

Pre-Action Audit

Money-related actions are logged before provider execution.

Opt-Out Protection

Customer opt-outs immediately block automated recovery communication.

Human Escalation

Certain failures are routed to human review instead of being repeatedly automated.

LLM Fallback

Customer communication continues using deterministic templates if the LLM provider is unavailable.

Provider Retry

Razorpay API failures use bounded exponential backoff rather than unlimited retries.

Design Principles

AEGIS follows five core principles:

1. Failure-Aware

Different payment failures require different recovery strategies.

2. Explainable

Every important decision is recorded and traceable.

3. Bounded

Automation has explicit attempt, cooldown, and escalation limits.

4. Graceful

External-service failures should degrade functionality rather than crash the recovery workflow.

5. Revenue-Focused

The system measures success through actual recovered revenue.

Future Improvements

Potential production extensions include:

Historical ML-based recovery prediction
More sophisticated customer segmentation
WhatsApp and email channels
Production webhook signature verification
Advanced retry-time optimization
Merchant-level strategy configuration
A/B testing of recovery messages
Long-term customer behavior modeling
Production-grade distributed task processing
PostgreSQL-based persistence
Role-based access control
Advanced revenue analytics
Hackathon Objective

AEGIS was designed around a simple question:

When a payment fails, what is the safest and most effective action we can take to recover the revenue?

Rather than blindly retrying transactions, AEGIS combines deterministic recovery logic, AI-powered communication, customer intent, stopping rules, and measurable outcomes into a single recovery workflow.

Detect → Diagnose → Decide → Recover → Measure

Built With

Python · FastAPI · React · SQLite · SQLAlchemy · Razorpay · Groq · Llama 3.3 70B · Twilio · APScheduler · Vite · Tailwind CSS · Recharts
