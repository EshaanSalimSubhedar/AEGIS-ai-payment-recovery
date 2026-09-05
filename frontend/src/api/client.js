import axios from "axios";

const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_BASE_URL ||
    "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10000,
});

// ============================================================
// PAYMENTS
// ============================================================

export async function getPayments() {
  const response = await api.get("/payments");

  return response.data;
}


export async function getPayment(paymentId) {
  const response = await api.get(
    `/payments/${paymentId}`
  );

  return response.data;
}


// ============================================================
// AUDIT
// ============================================================

export async function getPaymentAudit(
  paymentId
) {
  const response = await api.get(
    `/payments/${paymentId}/audit`
  );

  return response.data;
}


// ============================================================
// RECOVERY ACTIONS
// ============================================================

export async function triggerPaymentAction(
  paymentId,
  action = null
) {
  const response = await api.post(
    `/payments/${paymentId}/action`,
    {
      action,
    }
  );

  return response.data;
}


// ============================================================
// MANUAL RECOVERY — DEMO ONLY
// ============================================================

export async function markPaymentRecovered(
  paymentId
) {
  const response = await api.post(
    `/payments/${paymentId}/recover`
  );

  return response.data;
}


// ============================================================
// METRICS
// ============================================================

export async function getMetrics() {
  const response = await api.get(
    "/metrics"
  );

  return response.data;
}


// ============================================================
// EXCEPTIONS
// ============================================================

export async function getExceptions() {
  const response = await api.get(
    "/exceptions"
  );

  return response.data;
}


// ============================================================
// CUSTOMER REPLY / PTP
// ============================================================

export async function submitCustomerReply(
  paymentId,
  message
) {
  const response = await api.post(
    "/webhook/reply",
    {
      payment_id: paymentId,
      message,
    }
  );

  return response.data;
}


// ============================================================
// PAYMENT INGESTION
// ============================================================

export async function ingestPayment(
  payment
) {
  const response = await api.post(
    "/ingest",
    payment
  );

  return response.data;
}


// ============================================================
// HEALTH
// ============================================================

export async function getHealth() {
  const response = await api.get(
    "/health"
  );

  return response.data;
}


export default api;