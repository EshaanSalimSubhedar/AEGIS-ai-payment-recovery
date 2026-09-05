import React from "react";

import {
  AlertTriangle,
  CircleDollarSign,
  TrendingUp,
  WalletCards,
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

/* ============================================================
   METRIC CARD
   ============================================================ */

function MetricCard({
  icon: Icon,
  label,
  value,
  subtitle,
  iconClass = "",
}) {
  return (
    <article className="metric-card">

      <div className="metric-card-top">

        <div
          className={`metric-icon ${iconClass}`}
        >
          <Icon size={17} />
        </div>

        <p className="metric-label">
          {label}
        </p>

      </div>

      <p className="metric-value">
        {value}
      </p>

      <p className="metric-subtitle">
        {subtitle}
      </p>

    </article>
  );
}

/* ============================================================
   LOADING CARD
   ============================================================ */

function LoadingMetricCard() {
  return (
    <article className="metric-card">

      <div className="metric-card-top">

        <div className="metric-icon">
          <div
            className="skeleton"
            style={{
              width: "15px",
              height: "15px",
              borderRadius: "4px",
            }}
          />
        </div>

        <div
          className="skeleton"
          style={{
            width: "72px",
            height: "9px",
          }}
        />

      </div>

      <div
        className="skeleton skeleton-value"
      />

      <div
        className="skeleton skeleton-line"
        style={{
          marginTop: "7px",
          width: "90px",
          height: "9px",
        }}
      />

    </article>
  );
}

/* ============================================================
   COMPONENT
   ============================================================ */

export function MetricsPanel({
  metrics,
  loading = false,
}) {
  if (loading) {
    return (
      <div className="metrics-grid">

        <LoadingMetricCard />
        <LoadingMetricCard />
        <LoadingMetricCard />
        <LoadingMetricCard />

      </div>
    );
  }

  const failedAmount =
    metrics?.total_failed_amount || 0;

  const recoveredAmount =
    metrics?.total_recovered_amount || 0;

  const recoveryRate =
    metrics?.recovery_rate || 0;

  const failedCount =
    metrics?.total_failed_count ||
    metrics?.failed_payments_count ||
    0;

  const recoveredCount =
    metrics?.total_recovered_count ||
    metrics?.recovered_payments_count ||
    0;

  const exceptionCount =
    metrics?.exceptions_count ||
    0;

  return (
    <div className="metrics-grid">

      {/* ======================================================
          FAILED VALUE
          ====================================================== */}

      <MetricCard
        icon={CircleDollarSign}
        label="Failed Value"
        value={formatCurrency(
          failedAmount,
        )}
        subtitle={`${failedCount} failed ${
          failedCount === 1
            ? "payment"
            : "payments"
        }`}
      />

      {/* ======================================================
          RECOVERED
          ====================================================== */}

      <MetricCard
        icon={TrendingUp}
        label="Recovered"
        value={formatCurrency(
          recoveredAmount,
        )}
        subtitle={`${recoveredCount} recovered ${
          recoveredCount === 1
            ? "payment"
            : "payments"
        }`}
        iconClass="metric-icon-success"
      />

      {/* ======================================================
          RECOVERY RATE
          ====================================================== */}

      <MetricCard
        icon={WalletCards}
        label="Recovery Rate"
        value={`${recoveryRate}%`}
        subtitle="Value recovered / failed value"
      />

      {/* ======================================================
          EXCEPTIONS
          ====================================================== */}

      <MetricCard
        icon={AlertTriangle}
        label="Exceptions"
        value={exceptionCount}
        subtitle="Escalated or abandoned"
        iconClass="metric-icon-danger"
      />

    </div>
  );
}

export default MetricsPanel;