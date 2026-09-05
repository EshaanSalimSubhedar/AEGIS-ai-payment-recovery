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

## Why AEGIS?

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
| Unknown | Human Review |

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
