import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  Activity,
  AlertCircle,
  CheckCircle2,
  CircleDollarSign,
  Database,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Wifi,
} from "lucide-react";

import {
  getPayments,
  getMetrics,
  getExceptions,
  getPaymentAudit,
  triggerPaymentAction,
  markPaymentRecovered,
  submitCustomerReply,
} from "./api/client";

import { MetricsPanel } from "./components/MetricsPanel";
import { RecoveryFeed } from "./components/RecoveryFeed";
import { ExceptionsList } from "./components/ExceptionsList";
import { AuditTrail } from "./components/AuditTrail";
import { PromiseTracker } from "./components/PromiseTracker";
import { usePolling } from "./hooks/usePolling";

/* ============================================================
   CONFIGURATION
   ============================================================ */

const POLLING_INTERVAL = 3000;
const API_BASE_URL = "http://127.0.0.1:8000";

const DEMO_PAYMENTS = [
  {
    razorpay_payment_id: "pay_demo_bank_timeout_001",
    customer_name: "Aarav Sharma",
    customer_contact: "+919876543210",
    language_pref: "english",
    amount: 2499,
    error_code: "BANK_TIMEOUT",
    error_description: "Bank response timed out while processing payment.",
  },
  {
    razorpay_payment_id: "pay_demo_insufficient_002",
    customer_name: "Priya Menon",
    customer_contact: "+919876543211",
    language_pref: "english",
    amount: 4999,
    error_code: "INSUFFICIENT_FUNDS",
    error_description: "Insufficient funds in the customer's account.",
  },
  {
    razorpay_payment_id: "pay_demo_expired_003",
    customer_name: "Rohan Verma",
    customer_contact: "+919876543212",
    language_pref: "english",
    amount: 7999,
    error_code: "CARD_EXPIRED",
    error_description: "The card used for this payment has expired.",
  },
  {
    razorpay_payment_id: "pay_demo_declined_004",
    customer_name: "Sneha Iyer",
    customer_contact: "+919876543213",
    language_pref: "hinglish",
    amount: 3499,
    error_code: "ISSUER_DECLINED",
    error_description: "Payment was declined by the card issuer.",
  },
  {
    razorpay_payment_id: "pay_demo_network_005",
    customer_name: "Vikram Rao",
    customer_contact: "+919876543214",
    language_pref: "english",
    amount: 1299,
    error_code: "NETWORK_ERROR",
    error_description: "A network error occurred during payment processing.",
  },
  {
    razorpay_payment_id: "pay_demo_fraud_006",
    customer_name: "Neha Kapoor",
    customer_contact: "+919876543215",
    language_pref: "english",
    amount: 15999,
    error_code: "FRAUD_REVIEW",
    error_description: "Payment requires additional fraud review.",
  },
];

/* ============================================================
   HELPERS
   ============================================================ */

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function getInitialPayment(payments) {
  if (!Array.isArray(payments) || payments.length === 0) {
    return null;
  }

  return payments[0];
}

/* ============================================================
   APP
   ============================================================ */

export default function App() {
  /* ==========================================================
     DATA
     ========================================================== */

  const [payments, setPayments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [exceptions, setExceptions] = useState([]);

  const [selectedPaymentId, setSelectedPaymentId] =
    useState(null);

  const [auditEntries, setAuditEntries] = useState([]);

  /* ==========================================================
     UI STATE
     ========================================================== */

  const [initialLoading, setInitialLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [error, setError] =
    useState(null);

  const [actionLoadingId, setActionLoadingId] =
    useState(null);

  const [replySubmitting, setReplySubmitting] =
    useState(false);

  const [toast, setToast] =
    useState(null);

  const [demoLoading, setDemoLoading] =
    useState(false);

  /* ==========================================================
     SELECTED PAYMENT
     ========================================================== */

  const selectedPayment = useMemo(() => {
    if (selectedPaymentId !== null) {
      return (
        payments.find(
          (payment) =>
            payment.id === selectedPaymentId,
        ) || null
      );
    }

    return getInitialPayment(payments);
  }, [
    payments,
    selectedPaymentId,
  ]);

  /* ==========================================================
     TOAST
     ========================================================== */

  const showToast = useCallback(
    (message, type = "success") => {
      setToast({
        message,
        type,
      });

      window.setTimeout(() => {
        setToast(null);
      }, 3500);
    },
    [],
  );

  /* ==========================================================
     LOAD DASHBOARD
     ========================================================== */

  const loadDashboard = useCallback(
    async (showLoader = false) => {
      try {
        if (showLoader) {
          setRefreshing(true);
        }

        const [
          paymentsData,
          metricsData,
          exceptionsData,
        ] = await Promise.all([
          getPayments(),
          getMetrics(),
          getExceptions(),
        ]);

        const nextPayments =
          Array.isArray(paymentsData)
            ? paymentsData
            : [];

        const nextExceptions =
          Array.isArray(exceptionsData)
            ? exceptionsData
            : [];

        setPayments(nextPayments);
        setMetrics(metricsData || null);
        setExceptions(nextExceptions);

        /*
         * If the currently selected payment no longer exists,
         * reset selection so the UI does not point at a stale case.
         */
        if (
          selectedPaymentId !== null &&
          !nextPayments.some(
            (payment) =>
              payment.id === selectedPaymentId,
          )
        ) {
          setSelectedPaymentId(null);
        }

        setError(null);
      } catch (requestError) {
        console.error(
          "Dashboard loading failed:",
          requestError,
        );

        setError(
          "Unable to connect to the recovery API.",
        );
      } finally {
        setInitialLoading(false);
        setRefreshing(false);
      }
    },
    [selectedPaymentId],
  );

  /* ==========================================================
     INITIAL LOAD
     ========================================================== */

  useEffect(() => {
    loadDashboard(true);
  }, [loadDashboard]);

  /* ==========================================================
     POLLING
     ========================================================== */

  usePolling(
    () => loadDashboard(false),
    POLLING_INTERVAL,
    true,
  );

  /* ==========================================================
     LOAD AUDIT
     ========================================================== */

  const loadAudit = useCallback(
    async (paymentId) => {
      if (!paymentId) {
        setAuditEntries([]);
        return;
      }

      try {
        const data =
          await getPaymentAudit(paymentId);

        setAuditEntries(
          Array.isArray(data)
            ? data
            : [],
        );
      } catch (requestError) {
        console.error(
          "Audit loading failed:",
          requestError,
        );

        setAuditEntries([]);
      }
    },
    [],
  );

  /* ==========================================================
     AUDIT EFFECT
     ========================================================== */

  useEffect(() => {
    const paymentId =
      selectedPaymentId ??
      selectedPayment?.id ??
      null;

    if (!paymentId) {
      setAuditEntries([]);
      return;
    }

    loadAudit(paymentId);
  }, [
    selectedPaymentId,
    selectedPayment,
    loadAudit,
  ]);

  /* ==========================================================
     SELECT PAYMENT
     ========================================================== */

  const handleSelectPayment = useCallback(
    (paymentId) => {
      setSelectedPaymentId(paymentId);
    },
    [],
  );

  /* ==========================================================
     DEMO DATA
     ========================================================== */

  const demoPresent = useMemo(
    () =>
      payments.some((payment) =>
        String(
          payment.razorpay_payment_id || "",
        ).startsWith("pay_demo_"),
      ),
    [payments],
  );

  const handleDemoData = useCallback(
    async () => {
      if (demoLoading) {
        return;
      }

      setDemoLoading(true);

      try {
        if (demoPresent) {
          const response = await fetch(
            `${API_BASE_URL}/demo-data`,
            {
              method: "DELETE",
            },
          );

          if (!response.ok) {
            throw new Error(
              "Unable to unload demo data.",
            );
          }

          const result = await response.json();

          showToast(
            `Demo data unloaded${
              result?.deleted_count != null
                ? ` (${result.deleted_count} cases removed).`
                : "."
            }`,
            "success",
          );
        } else {
          for (const payment of DEMO_PAYMENTS) {
            const response = await fetch(
              `${API_BASE_URL}/ingest`,
              {
                method: "POST",
                headers: {
                  "Content-Type":
                    "application/json",
                },
                body: JSON.stringify(payment),
              },
            );

            if (!response.ok) {
              throw new Error(
                "Unable to load demo data.",
              );
            }
          }

          showToast(
            "Demo data loaded successfully.",
            "success",
          );
        }

        await loadDashboard(false);
        setSelectedPaymentId(null);
        setAuditEntries([]);
      } catch (requestError) {
        console.error(
          "Demo data operation failed:",
          requestError,
        );

        showToast(
          demoPresent
            ? "Unable to unload demo data."
            : "Unable to load demo data.",
          "error",
        );
      } finally {
        setDemoLoading(false);
      }
    },
    [
      demoLoading,
      demoPresent,
      loadDashboard,
      showToast,
    ],
  );

  /* ==========================================================
     RECOVERY ACTION
     ========================================================== */

  const handleAction = useCallback(
    async (paymentId) => {
      if (!paymentId) {
        return;
      }

      setActionLoadingId(paymentId);

      try {
        const result =
          await triggerPaymentAction(
            paymentId,
          );

        if (result?.success) {
          showToast(
            "Recovery action executed successfully.",
            "success",
          );
        } else if (result?.blocked) {
          showToast(
            `Action blocked: ${
              result.reason ||
              "Safety rule prevented execution."
            }`,
            "warning",
          );
        } else {
          showToast(
            result?.error ||
              "Recovery action could not be completed.",
            "error",
          );
        }

        await loadDashboard(false);
        await loadAudit(paymentId);
      } catch (requestError) {
        console.error(
          "Recovery action failed:",
          requestError,
        );

        showToast(
          "Recovery action failed.",
          "error",
        );
      } finally {
        setActionLoadingId(null);
      }
    },
    [
      loadDashboard,
      loadAudit,
      showToast,
    ],
  );

  /* ==========================================================
     MARK RECOVERED
     ========================================================== */

  const handleRecover = useCallback(
    async (paymentId) => {
      if (!paymentId) {
        return;
      }

      setActionLoadingId(paymentId);

      try {
        const result =
          await markPaymentRecovered(
            paymentId,
          );

        if (result?.success) {
          showToast(
            "Payment marked as recovered.",
            "success",
          );
        } else {
          showToast(
            result?.error ||
              "Payment could not be marked as recovered.",
            "error",
          );
        }

        await loadDashboard(false);
        await loadAudit(paymentId);
      } catch (requestError) {
        console.error(
          "Mark recovered failed:",
          requestError,
        );

        showToast(
          "Unable to mark payment as recovered.",
          "error",
        );
      } finally {
        setActionLoadingId(null);
      }
    },
    [
      loadDashboard,
      loadAudit,
      showToast,
    ],
  );

  /* ==========================================================
     CUSTOMER REPLY / PTP
     ========================================================== */

  const handleSubmitReply = useCallback(
    async (paymentId, message) => {
      if (
        !paymentId ||
        !message ||
        !message.trim()
      ) {
        return;
      }

      setReplySubmitting(true);

      try {
        const result =
          await submitCustomerReply(
            paymentId,
            message.trim(),
          );

        if (
          result?.type ===
          "opt_out"
        ) {
          showToast(
            "Customer opted out. Recovery contact stopped.",
            "warning",
          );
        } else if (
          result?.type ===
          "promise_to_pay"
        ) {
          const promisedDate =
            result?.promised_date
              ? new Date(
                  result.promised_date,
                ).toLocaleDateString(
                  "en-IN",
                )
              : "the promised date";

          showToast(
            `PTP detected for ${promisedDate}.`,
            "success",
          );
        } else {
          showToast(
            "Customer reply processed.",
            "success",
          );
        }

        await loadDashboard(false);
        await loadAudit(paymentId);
      } catch (requestError) {
        console.error(
          "Customer reply failed:",
          requestError,
        );

        showToast(
          "Unable to process customer reply.",
          "error",
        );
      } finally {
        setReplySubmitting(false);
      }
    },
    [
      loadDashboard,
      loadAudit,
      showToast,
    ],
  );

  /* ==========================================================
     DASHBOARD VALUES
     ========================================================== */

  const recoveredAmount =
    metrics?.total_recovered_amount || 0;

  const failedAmount =
    metrics?.total_failed_amount || 0;

  const recoveryRate =
    metrics?.recovery_rate || 0;

  const exceptionCount =
    exceptions.length;

  /* ==========================================================
     RENDER
     ========================================================== */

  return (
    <div className="app-shell">

      <div className="app-container">

        {/* ==================================================
            TOAST
            ================================================== */}

        {toast && (
          <div className="toast">
            {toast.type === "success" ? (
              <CheckCircle2 size={17} />
            ) : (
              <AlertCircle size={17} />
            )}

            <span>
              {toast.message}
            </span>
          </div>
        )}

        {/* ==================================================
            HEADER
            ================================================== */}

        <header className="topbar">

          <div className="brand">

            <div className="brand-start">
              <h1>
                <span className="brand-title"> </span>
              </h1>
            </div>

            <div className="brand-mark">
              <img src="/logo.png" alt="AEGIS" className="brand-logo" />
            </div>

            <div className="brand-copy">
              <h1>
                <span className="brand-title"> | AEGIS | </span>
                <span className="brand-subtitle"> AI Revenue Recovery |</span>
              </h1>
            </div>

          </div>

          <div className="header-actions">

            <div className="connection-status">

              <span className="connection-dot" />

              <span>
                Live
              </span>

            </div>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleDemoData}
              disabled={
                demoLoading ||
                refreshing
              }
            >
              {demoPresent ? (
                <Trash2 size={15} />
              ) : (
                <Database size={15} />
              )}

              {demoLoading
                ? "Working..."
                : demoPresent
                  ? "Unload Demo Data"
                  : "Load Demo Data"}
            </button>

          </div>

        </header>

        {/* ==================================================
            ERROR
            ================================================== */}

        {error && (
          <div className="global-error">

            <AlertCircle size={17} />

            <div>

              <strong>
                Backend unavailable
              </strong>

              <div>
                Start FastAPI with{" "}
                <code>
                  uvicorn backend.app:app --reload
                </code>
              </div>

            </div>

          </div>
        )}

        {/* ==================================================
            HERO
            ================================================== */}

        <section className="hero">

          <div className="hero-copy">

            <div className="hero-eyebrow">

              <Activity size={13} />

              <span>
                AUTONOMOUS RECOVERY
              </span>

            </div>

            <h2>
              Recover failed revenue
              <br />
              before it becomes lost revenue.
            </h2>

            <p>
              Detect, diagnose, decide and recover
              failed payments with bounded,
              explainable automation.
            </p>

          </div>

          <div className="hero-summary">

            <div className="hero-summary-card">

              <span className="hero-summary-label">
                Recovered
              </span>

              <span className="hero-summary-value">
                {formatCurrency(
                  recoveredAmount,
                )}
              </span>

            </div>

            <div className="hero-summary-card">

              <span className="hero-summary-label">
                Recovery Rate
              </span>

              <span className="hero-summary-value">
                {recoveryRate}%
              </span>

            </div>

            <div className="hero-summary-card">

              <span className="hero-summary-label">
                Failed Value
              </span>

              <span className="hero-summary-value">
                {formatCurrency(
                  failedAmount,
                )}
              </span>

            </div>

          </div>

        </section>

        {/* ==================================================
            METRICS
            ================================================== */}

        <section className="section">

          <MetricsPanel
            metrics={metrics}
            loading={initialLoading}
          />

        </section>

        {/* ==================================================
            MAIN DASHBOARD
            ================================================== */}

        <div className="dashboard-grid">

          {/* ==================================================
              RECOVERY FEED

              IMPORTANT:
              RecoveryFeed owns its own header.
              Do NOT add another header here.
              ================================================== */}

          <main className="dashboard-main">

            <section className="panel">

              <RecoveryFeed
                payments={payments}
                loading={initialLoading}
                onAction={handleAction}
                onRecover={handleRecover}
                actionLoadingId={
                  actionLoadingId
                }
              />

            </section>

          </main>

          {/* ==================================================
              SIDEBAR
              ================================================== */}

          <aside className="dashboard-side">

            <section className="panel">

              <ExceptionsList
                exceptions={exceptions}
              />

            </section>

            <section className="panel">

              <PromiseTracker
                payment={selectedPayment}
                onSubmitReply={
                  handleSubmitReply
                }
                submitting={
                  replySubmitting
                }
              />

            </section>

          </aside>

        </div>

        {/* ==================================================
            SELECTED CASE
            ================================================== */}

        <section className="section">

          <div className="panel selected-case-section">

            {/* ------------------------------------------------
                Selected Case Header (use shared section-header)
                ------------------------------------------------ */}

            <div className="section-header">

              <div>

                <h2>
                  Selected Case
                </h2>

                <p>
                  Choose a payment to inspect
                  its recovery history
                </p>

              </div>

              {selectedPayment && (
                <span className="status-badge pending">
                  Case #{selectedPayment.id}
                </span>
              )}

            </div>

            {/* ------------------------------------------------
                Case Selector + Bubbles
                ------------------------------------------------ */}

            <div className="selected-case">

              <div className="bubbles-wrapper">
                <div className="bubble bubble-1" />
                <div className="bubble bubble-2" />
                <div className="bubble bubble-3" />

                <div className="bubbles-content">

                  {payments.length === 0 ? (

                    <div className="empty-state">

                      <div className="empty-state-icon">
                        <CircleDollarSign
                          size={18}
                        />
                      </div>

                      <h3>
                        No payment cases available
                      </h3>

                      <p>
                        New failed-payment recovery
                        cases will appear here.
                      </p>

                    </div>

                  ) : (

                    <div className="case-selector">

                      {payments
                        .slice(0, 8)
                        .map((payment) => (

                          <button
                            key={payment.id}
                            type="button"
                            className={`case-selector-item ${
                              selectedPayment?.id ===
                              payment.id
                                ? "selected"
                                : ""
                            }`}
                            onClick={() =>
                              handleSelectPayment(
                                payment.id,
                              )
                            }
                          >

                            <span>
                              {payment.customer_name ||
                                "Customer"}
                            </span>

                            <span>
                              {formatCurrency(
                                payment.amount,
                              )}
                            </span>

                          </button>

                        ))}

                    </div>

                  )}

                </div>
              </div>

            </div>

            {/* =================================================
                AUDIT TRAIL

                IMPORTANT:
                AuditTrail owns its own header.
                We deliberately do NOT create another
                "Audit Trail" header here.
                ================================================= */}

            <AuditTrail
              entries={auditEntries}
              paymentId={
                selectedPayment?.id
              }
              loading={initialLoading}
            />

          </div>

        </section>

        {/* ==================================================
            FOOTER
            ================================================== */}

        <footer className="footer">

          <div className="footer-status">

            <span className="footer-status-dot" />

            <Wifi size={13} />

            <span>
              API connected
            </span>

          </div>

          <div>

            <ShieldCheck size={13} />

            <span>
              Max 3 automated retries
            </span>

          </div>

          <div>

            <CircleDollarSign size={13} />

            <span>
              ₹ recovered is the primary KPI
            </span>

          </div>

          <div>

            <span>
              {exceptionCount} active exceptions
            </span>

          </div>

          <div>

            <span>
              Auto-refresh:{" "}
              {POLLING_INTERVAL / 1000}s
            </span>

          </div>

        </footer>

      </div>

    </div>
  );
}