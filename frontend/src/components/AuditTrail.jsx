import React from "react";

import {
  Activity,
  AlertCircle,
  Ban,
  CheckCircle2,
  Clock3,
  FileText,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

/* ============================================================
   HELPERS
   ============================================================ */

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

function formatAction(action) {
  if (!action) {
    return "Action";
  }

  return action
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}

function getActionIcon(action) {
  const normalized =
    String(action || "").toLowerCase();

  if (
    normalized.includes("recovered")
  ) {
    return CheckCircle2;
  }

  if (
    normalized.includes("retry")
  ) {
    return RefreshCw;
  }

  if (
    normalized.includes("message") ||
    normalized.includes("reply")
  ) {
    return MessageSquare;
  }

  if (
    normalized.includes("fallback")
  ) {
    return Sparkles;
  }

  if (
    normalized.includes("blocked") ||
    normalized.includes("opt_out")
  ) {
    return Ban;
  }

  if (
    normalized.includes("exception") ||
    normalized.includes("escalat") ||
    normalized.includes("fraud")
  ) {
    return ShieldAlert;
  }

  if (
    normalized.includes("scheduled")
  ) {
    return Clock3;
  }

  if (
    normalized.includes("error")
  ) {
    return AlertCircle;
  }

  if (
    normalized.includes("classified")
  ) {
    return Activity;
  }

  return FileText;
}

/* ============================================================
   COMPONENT
   ============================================================ */

export function AuditTrail({
  entries = [],
  paymentId = null,
  loading = false,
}) {
  /* ==========================================================
     NO PAYMENT SELECTED
     ========================================================== */

  if (!paymentId) {
    return (
      <div className="audit-trail">

        <div className="section-header">

          <div>
            <h2>
              Audit Trail
            </h2>

            <p>
              Recovery decision history
            </p>
          </div>

        </div>

        <div
          className="empty-state"
          style={{
            minHeight: "145px",
          }}
        >

          <div className="empty-state-icon">
            <FileText size={18} />
          </div>

          <h3>
            No payment selected
          </h3>

          <p>
            Select a recovery case to inspect
            its decision history.
          </p>

        </div>

      </div>
    );
  }

  /* ==========================================================
     LOADING
     ========================================================== */

  if (loading) {
    return (
      <div className="audit-trail">

        <div className="section-header">

          <div>
            <h2>
              Audit Trail
            </h2>

            <p>
              Recovery decision history
            </p>
          </div>

        </div>

        <div
          style={{
            padding: "15px",
          }}
        >

          {[1, 2, 3].map((item) => (
            <div
              key={item}
              style={{
                display: "grid",
                gridTemplateColumns:
                  "27px minmax(0, 1fr)",
                gap: "9px",
                marginBottom: "14px",
              }}
            >

              <div
                className="skeleton"
                style={{
                  width: "27px",
                  height: "27px",
                  borderRadius: "50%",
                }}
              />

              <div>

                <div
                  className="skeleton"
                  style={{
                    width: "45%",
                    height: "9px",
                  }}
                />

                <div
                  className="skeleton"
                  style={{
                    width: "80%",
                    height: "8px",
                    marginTop: "7px",
                  }}
                />

              </div>

            </div>
          ))}

        </div>

      </div>
    );
  }

  /* ==========================================================
     EMPTY AUDIT
     ========================================================== */

  if (!entries || entries.length === 0) {
    return (
      <div className="audit-trail">

        <div className="section-header">

          <div>
            <h2>
              Audit Trail
            </h2>

            <p>
              Recovery decision history
            </p>
          </div>

        </div>

        <div
          className="empty-state"
          style={{
            minHeight: "145px",
          }}
        >

          <div className="empty-state-icon">
            <FileText size={18} />
          </div>

          <h3>
            No audit events yet
          </h3>

          <p>
            Recovery decisions and actions
            will appear here.
          </p>

        </div>

      </div>
    );
  }

  /* ==========================================================
     AUDIT LIST
     ========================================================== */

  return (
    <div className="audit-trail">

      {/* ======================================================
          HEADER — ONLY ONE
          ====================================================== */}

      <div className="section-header">

        <div>
          <h2>
            Audit Trail
          </h2>

          <p>
            Recovery decision history
          </p>
        </div>

        <span className="status-badge pending">
          {entries.length}{" "}
          {entries.length === 1
            ? "event"
            : "events"}
        </span>

      </div>

      {/* ======================================================
          EVENTS
          ====================================================== */}

      <div
        style={{
          paddingTop: "14px",
        }}
      >

        {entries.map((entry, index) => {
          const Icon =
            getActionIcon(
              entry.action,
            );

          return (
            <div
              key={
                entry.id ||
                `${entry.action}-${index}`
              }
              className="audit-entry"
            >

              {/* ------------------------------------------------
                  TIMELINE ICON
                  ------------------------------------------------ */}

              <div className="audit-dot">
                <Icon size={13} />
              </div>

              {/* ------------------------------------------------
                  CONTENT
                  ------------------------------------------------ */}

              <div className="audit-content">

                <div className="audit-topline">

                  <p className="audit-action">
                    {formatAction(
                      entry.action,
                    )}
                  </p>

                  <span className="audit-time">
                    {formatDate(
                      entry.timestamp,
                    )}
                  </span>

                </div>

                <p className="audit-reasoning">
                  {entry.reasoning ||
                    "No reasoning recorded."}
                </p>

              </div>

            </div>
          );
        })}

      </div>

    </div>
  );
}

export default AuditTrail;