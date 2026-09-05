import React from "react";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  RefreshCw,
  ShieldAlert,
  UserRound,
} from "lucide-react";

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

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatReason(reason) {
  if (!reason) {
    return "Unknown";
  }

  return reason
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}

function formatStatus(status) {
  if (!status) {
    return "pending";
  }

  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}

function getStatusClass(status) {
  switch (status) {
    case "recovered":
      return "recovered";

    case "retrying":
      return "retrying";

    case "escalated":
      return "escalated";

    case "human_review":
      return "human-review";

    case "abandoned":
      return "abandoned";

    default:
      return "pending";
  }
}

function getScoreLabel(score) {
  const numericScore = Number(score || 0);

  if (numericScore >= 0.7) {
    return "High";
  }

  if (numericScore >= 0.45) {
    return "Medium";
  }

  return "Low";
}

function getScoreClass(score) {
  const numericScore = Number(score || 0);

  if (numericScore >= 0.7) {
    return "high";
  }

  if (numericScore >= 0.45) {
    return "medium";
  }

  return "low";
}

/* ============================================================
   COMPONENT
   ============================================================ */

export function RecoveryFeed({
  payments = [],
  loading = false,
  onAction,
  onRecover,
  actionLoadingId = null,
}) {
  /* ==========================================================
     LOADING
     ========================================================== */

  if (loading) {
    return (
      <div className="recovery-feed">

        <div className="section-header">

          <div>
            <h2>
              Recovery Feed
            </h2>

            <p>
              Live failed-payment recovery cases
            </p>
          </div>

          <span className="status-badge pending">
            Loading
          </span>

        </div>

        {[1, 2, 3].map((item) => (
          <div
            key={item}
            className="payment-card"
          >
            <div className="payment-main">

              <div
                className="skeleton skeleton-line"
              />

              <div
                className="skeleton skeleton-line"
              />

              <div className="payment-meta">

                <div className="meta-item">
                  <div
                    className="skeleton"
                    style={{
                      width: "70%",
                      height: "8px",
                    }}
                  />
                </div>

                <div className="meta-item">
                  <div
                    className="skeleton"
                    style={{
                      width: "60%",
                      height: "8px",
                    }}
                  />
                </div>

                <div className="meta-item">
                  <div
                    className="skeleton"
                    style={{
                      width: "65%",
                      height: "8px",
                    }}
                  />
                </div>

                <div className="meta-item">
                  <div
                    className="skeleton"
                    style={{
                      width: "55%",
                      height: "8px",
                    }}
                  />
                </div>

              </div>

            </div>

            <div
              className="skeleton"
              style={{
                width: "120px",
                height: "34px",
              }}
            />

          </div>
        ))}

      </div>
    );
  }

  /* ==========================================================
     EMPTY STATE
     ========================================================== */

  if (!payments || payments.length === 0) {
    return (
      <div className="recovery-feed">

        <div className="section-header">

          <div>
            <h2>
              Recovery Feed
            </h2>

            <p>
              Live failed-payment recovery cases
            </p>
          </div>

          <span className="status-badge pending">
            0 cases
          </span>

        </div>

        <div className="empty-state">

          <div className="empty-state-icon">
            <CheckCircle2 size={19} />
          </div>

          <h3>
            No failed payments
          </h3>

          <p>
            New failed-payment recovery cases
            will appear here.
          </p>

        </div>

      </div>
    );
  }

  /* ==========================================================
     PAYMENT LIST
     ========================================================== */

  return (
    <div className="recovery-feed">

      {/* ======================================================
          HEADER
          ====================================================== */}

      <div className="section-header">

        <div>
          <h2>
            Recovery Feed
          </h2>

          <p>
            Live failed-payment recovery cases
          </p>
        </div>

        <span className="status-badge pending">
          {payments.length}{" "}
          {payments.length === 1
            ? "case"
            : "cases"}
        </span>

      </div>

      {/* ======================================================
          CASES
          ====================================================== */}

      {payments.map((payment) => {
        const status =
          payment.status || "pending";

        const isLoading =
          actionLoadingId === payment.id;

        const score =
          Number(
            payment.recovery_score || 0,
          );

        const attempts =
          Number(payment.attempts || 0);

        const maxAttempts = 3;

        const isRecovered =
          status === "recovered";

        const isEscalated =
          status === "escalated" ||
          status === "human_review";

        const isAbandoned =
          status === "abandoned";

        const isOptedOut =
          Boolean(payment.opted_out);

        return (
          <article
            key={payment.id}
            className="payment-card"
          >

            {/* ==================================================
                MAIN CONTENT
                ================================================== */}

            <div className="payment-main">

              {/* ------------------------------------------------
                  TOP
                  ------------------------------------------------ */}

              <div className="payment-top">

                <div className="customer-block">

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "7px",
                      marginBottom: "3px",
                    }}
                  >

                    <UserRound
                      size={13}
                      color="var(--blue)"
                    />

                    <h3 className="customer-name">
                      {payment.customer_name ||
                        "Customer"}
                    </h3>

                  </div>

                  <p className="customer-contact">
                    {payment.customer_contact ||
                      "Contact unavailable"}
                  </p>

                </div>

                <div className="amount-block">

                  <p className="amount">
                    {formatCurrency(
                      payment.amount,
                    )}
                  </p>

                  <div className="amount-label">
                    Failed payment
                  </div>

                </div>

              </div>

              {/* ------------------------------------------------
                  STATUS + REASON
                  ------------------------------------------------ */}

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "7px",
                  marginBottom: "8px",
                }}
              >

                <span
                  className={`status-badge ${getStatusClass(
                    status,
                  )}`}
                >
                  {formatStatus(status)}
                </span>

                <span
                  style={{
                    color: "var(--text-secondary)",
                    fontSize: "10px",
                    fontWeight: 650,
                  }}
                >
                  {formatReason(
                    payment.failure_reason,
                  )}
                </span>

              </div>

              {/* ------------------------------------------------
                  METADATA
                  ------------------------------------------------ */}

              <div className="payment-meta">

                <div className="meta-item">

                  <span className="meta-label">
                    Recovery Score
                  </span>

                  <span
                    className="meta-value"
                    style={{
                      color:
                        score >= 0.7
                          ? "var(--green-dark)"
                          : score >= 0.45
                            ? "var(--amber)"
                            : "var(--red)",
                    }}
                  >
                    {(score * 100).toFixed(0)}%
                    {" · "}
                    {getScoreLabel(score)}
                  </span>

                </div>

                <div className="meta-item">

                  <span className="meta-label">
                    Attempts
                  </span>

                  <span className="meta-value">
                    {attempts} / {maxAttempts}
                  </span>

                </div>

                <div className="meta-item">

                  <span className="meta-label">
                    Language
                  </span>

                  <span className="meta-value">
                    {payment.language_pref ||
                      "English"}
                  </span>

                </div>

                <div className="meta-item">

                  <span className="meta-label">
                    Created
                  </span>

                  <span className="meta-value">
                    {formatDate(
                      payment.created_at,
                    )}
                  </span>

                </div>

              </div>

              {/* ------------------------------------------------
                  RAZORPAY ID
                  ------------------------------------------------ */}

              <div className="payment-reference">

                <strong>
                  Razorpay:
                </strong>{" "}

                {payment.razorpay_payment_id ||
                  "Unavailable"}

              </div>

              {/* ------------------------------------------------
                  RECOVERY REFERENCE
                  ------------------------------------------------ */}

              {payment.recovery_reference_id && (
                <div className="payment-reference">

                  <strong>
                    Recovery reference:
                  </strong>{" "}

                  {payment.recovery_reference_id}

                  {payment.recovery_reference_type && (
                    <>
                      {" · "}
                      {formatReason(
                        payment.recovery_reference_type,
                      )}
                    </>
                  )}

                </div>
              )}

              {/* ------------------------------------------------
                  PAYMENT LINK
                  ------------------------------------------------ */}

              {payment.payment_link && (
                <a
                  className="payment-link"
                  href={payment.payment_link}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open payment link{" "}
                  <ExternalLink
                    size={11}
                    style={{
                      verticalAlign: "middle",
                    }}
                  />
                </a>
              )}

              {/* ------------------------------------------------
                  HUMAN REVIEW
                  ------------------------------------------------ */}

              {isEscalated && (
                <div className="human-review-notice">

                  <ShieldAlert
                    size={14}
                  />

                  <span>
                    This case requires human
                    review. Automated recovery
                    is not being attempted.
                  </span>

                </div>
              )}

              {/* ------------------------------------------------
                  OPT OUT
                  ------------------------------------------------ */}

              {isOptedOut && (
                <div className="human-review-notice">

                  <AlertTriangle
                    size={14}
                  />

                  <span>
                    Customer opted out.
                    Further automated contact
                    is stopped.
                  </span>

                </div>
              )}

            </div>

            {/* ==================================================
                ACTIONS
                ================================================== */}

            <div className="payment-actions">

              {/* ------------------------------------------------
                  RECOVERY ACTION
                  ------------------------------------------------ */}

              {!isRecovered &&
                !isEscalated &&
                !isAbandoned &&
                !isOptedOut && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={isLoading}
                    onClick={() =>
                      onAction?.(
                        payment.id,
                      )
                    }
                  >

                    <RefreshCw
                      size={14}
                      className={
                        isLoading
                          ? "spin"
                          : ""
                      }
                    />

                    {isLoading
                      ? "Running..."
                      : "Run recovery"}

                  </button>
                )}

              {/* ------------------------------------------------
                  RECOVERED
                  ------------------------------------------------ */}

              {isRecovered && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    minHeight: "34px",
                    padding: "7px 9px",
                    borderRadius: "8px",
                    background:
                      "var(--green-soft)",
                    color:
                      "var(--green-dark)",
                    fontSize: "10px",
                    fontWeight: 800,
                  }}
                >
                  <CheckCircle2
                    size={14}
                  />
                  Recovered
                </div>
              )}

              {/* ------------------------------------------------
                  DEMO RECOVERY
                  ------------------------------------------------ */}

              {!isRecovered &&
                !isAbandoned &&
                !isOptedOut && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={isLoading}
                    onClick={() =>
                      onRecover?.(
                        payment.id,
                      )
                    }
                    title="Demo helper: marks this payment as recovered"
                  >
                    <CheckCircle2
                      size={13}
                    />

                    Mark recovered
                  </button>
                )}

              {/* ------------------------------------------------
                  RETRY INFORMATION
                  ------------------------------------------------ */}

              {!isRecovered &&
                !isEscalated &&
                !isAbandoned &&
                !isOptedOut &&
                attempts >= maxAttempts && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "5px",
                      padding: "6px",
                      color:
                        "var(--red)",
                      fontSize: "9px",
                      fontWeight: 700,
                      textAlign: "center",
                    }}
                  >
                    <Clock3 size={12} />

                    Maximum attempts reached
                  </div>
                )}

            </div>

          </article>
        );
      })}

    </div>
  );
}

export default RecoveryFeed;