import React from "react";

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
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

function getExceptionType(payment) {
  if (
    payment.status === "abandoned"
  ) {
    return {
      label: "Abandoned",
      icon: Ban,
    };
  }

  if (
    payment.failure_reason ===
    "fraud_review"
  ) {
    return {
      label: "Risk Review",
      icon: ShieldAlert,
    };
  }

  if (
    payment.status === "escalated" ||
    payment.status === "human_review"
  ) {
    return {
      label: "Human Review",
      icon: UserRound,
    };
  }

  return {
    label: "Attention Required",
    icon: AlertTriangle,
  };
}

/* ============================================================
   COMPONENT
   ============================================================ */

export function ExceptionsList({
  exceptions = [],
}) {
  /* ==========================================================
     EMPTY STATE
     ========================================================== */

  if (!exceptions || exceptions.length === 0) {
    return (
      <div className="exceptions-list">

        <div className="section-header">

          <div>
            <h2>
              Exceptions
            </h2>

            <p>
              Cases requiring attention
            </p>
          </div>

          <span className="status-badge pending">
            0
          </span>

        </div>

        <div
          className="empty-state"
          style={{
            minHeight: "190px",
          }}
        >

          <div
            className="empty-state-icon"
            style={{
              background:
                "var(--green-soft)",
              color:
                "var(--green)",
            }}
          >
            <CheckCircle2 size={19} />
          </div>

          <h3>
            No active exceptions
          </h3>

          <p>
            All current recovery cases are
            within automated recovery rules.
          </p>

        </div>

      </div>
    );
  }

  /* ==========================================================
     EXCEPTION LIST
     ========================================================== */

  return (
    <div className="exceptions-list">

      {/* ======================================================
          HEADER
          ====================================================== */}

      <div className="section-header">

        <div>
          <h2>
            Exceptions
          </h2>

          <p>
            Cases requiring attention
          </p>
        </div>

        <span className="status-badge escalated">
          {exceptions.length}
        </span>

      </div>

      {/* ======================================================
          ITEMS
          ====================================================== */}

      {exceptions.map((exception) => {
        const {
          label,
          icon: ExceptionIcon,
        } = getExceptionType(
          exception,
        );

        const customerName =
          exception.customer_name ||
          "Customer";

        const amount =
          exception.amount || 0;

        const reason =
          exception.failure_reason ||
          "unknown";

        const status =
          exception.status ||
          "escalated";

        return (
          <div
            key={
              exception.id ||
              exception.razorpay_payment_id
            }
            className="exception-item"
          >

            {/* ------------------------------------------------
                ICON
                ------------------------------------------------ */}

            <div className="exception-icon">
              <ExceptionIcon
                size={15}
              />
            </div>

            {/* ------------------------------------------------
                CONTENT
                ------------------------------------------------ */}

            <div className="exception-content">

              <p className="exception-title">
                {customerName}
              </p>

              <p className="exception-subtitle">
                {label}
                {" · "}
                {formatReason(reason)}
              </p>

              <div
                style={{
                  marginTop: "5px",
                  color:
                    "var(--text-muted)",
                  fontSize: "8px",
                  lineHeight: "1.3",
                }}
              >
                {status ===
                "abandoned"
                  ? "Automated recovery stopped"
                  : "Manual intervention required"}
              </div>

            </div>

            {/* ------------------------------------------------
                AMOUNT
                ------------------------------------------------ */}

            <div className="exception-amount">
              {formatCurrency(amount)}
            </div>

          </div>
        );
      })}

    </div>
  );
}

export default ExceptionsList;