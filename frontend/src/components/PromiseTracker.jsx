import React, {
  useState,
} from "react";

import {
  CalendarClock,
  CheckCircle2,
  MessageSquare,
  Send,
} from "lucide-react";

/* ============================================================
   COMPONENT
   ============================================================ */

export function PromiseTracker({
  payment,
  onSubmitReply,
  submitting = false,
}) {
  const [
    message,
    setMessage,
  ] = useState("");

  /* ==========================================================
     NO PAYMENT
     ========================================================== */

  if (!payment) {
    return (
      <div className="ptp-section">

        <div className="section-header">

          <div>
            <h2>
              Promise to Pay
            </h2>

            <p>
              Customer commitment tracking
            </p>
          </div>

          <MessageSquare
            size={17}
            color="var(--blue)"
          />

        </div>

        <div
          className="empty-state"
          style={{
            minHeight: "105px",
            padding: "10px",
          }}
        >

          <div
            className="empty-state-icon"
            style={{
              width: "32px",
              height: "32px",
            }}
          >
            <CalendarClock
              size={16}
            />
          </div>

          <h3>
            No payment selected
          </h3>

          <p>
            Select a payment to track a
            customer promise.
          </p>

        </div>

      </div>
    );
  }

  /* ==========================================================
     SUBMIT
     ========================================================== */

  const handleSubmit = () => {
    const trimmed =
      message.trim();

    if (
      !trimmed ||
      submitting
    ) {
      return;
    }

    onSubmitReply?.(
      payment.id,
      trimmed,
    );

    setMessage("");
  };

  /* ==========================================================
     KEYBOARD
     ========================================================== */

  const handleKeyDown = (
    event,
  ) => {
    if (
      event.key === "Enter" &&
      (event.ctrlKey ||
        event.metaKey)
    ) {
      event.preventDefault();
      handleSubmit();
    }
  };

  /* ==========================================================
     RENDER
     ========================================================== */

  return (
    <div className="ptp-section">

      {/* ======================================================
          HEADER
          ====================================================== */}

      <div className="section-header">

        <div>

          <h2>
            Promise to Pay
          </h2>

          <p>
            Customer commitment tracking
          </p>

        </div>

        <MessageSquare
          size={17}
          color="var(--blue)"
        />

      </div>

      {/* ======================================================
          SELECTED CUSTOMER
          ====================================================== */}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "11px",
          padding: "8px 9px",
          borderRadius: "8px",
          background:
            "var(--blue-pale)",
        }}
      >

        <CheckCircle2
          size={14}
          color="var(--blue)"
        />

        <div
          style={{
            minWidth: 0,
          }}
        >

          <div
            style={{
              color:
                "var(--navy)",
              fontSize: "10px",
              fontWeight: 800,
              lineHeight: "1.2",
            }}
          >
            {payment.customer_name ||
              "Customer"}
          </div>

          <div
            style={{
              marginTop: "2px",
              color:
                "var(--text-secondary)",
              fontSize: "8px",
              lineHeight: "1.2",
            }}
          >
            Case #{payment.id}
          </div>

        </div>

      </div>

      {/* ======================================================
          FORM
          ====================================================== */}

      <div className="ptp-form">

        <label htmlFor="customer-reply">
          Customer reply
        </label>

        <textarea
          id="customer-reply"
          value={message}
          onChange={(event) =>
            setMessage(
              event.target.value,
            )
          }
          onKeyDown={
            handleKeyDown
          }
          placeholder="Example: I'll pay tomorrow"
          rows={3}
          disabled={submitting}
        />

        <button
          type="button"
          disabled={
            submitting ||
            !message.trim()
          }
          onClick={
            handleSubmit
          }
        >

          {submitting ? (
            <>
              <span
                className="button-spinner"
              />
              Processing...
            </>
          ) : (
            <>
              <Send size={12} />
              Process reply
            </>
          )}

        </button>

      </div>

      {/* ======================================================
          EXAMPLES
          ====================================================== */}

      <div className="ptp-hint">

        <span>
          Try:
        </span>

        <button
          type="button"
          onClick={() =>
            setMessage(
              "I'll pay tomorrow",
            )
          }
          disabled={submitting}
          style={{
            border: 0,
            padding: 0,
            background:
              "transparent",
            color:
              "var(--blue)",
            fontSize: "8px",
            fontWeight: 700,
          }}
        >
          "I'll pay tomorrow"
        </button>

        <button
          type="button"
          onClick={() =>
            setMessage(
              "I'll pay on September 10",
            )
          }
          disabled={submitting}
          style={{
            border: 0,
            padding: 0,
            background:
              "transparent",
            color:
              "var(--blue)",
            fontSize: "8px",
            fontWeight: 700,
          }}
        >
          "I'll pay on September 10"
        </button>

      </div>

      {/* ======================================================
          SHORTCUT
          ====================================================== */}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          marginTop: "8px",
          color:
            "var(--text-muted)",
          fontSize: "8px",
        }}
      >

        <span>
          Tip:
        </span>

        <code
          style={{
            padding: "2px 4px",
            borderRadius: "4px",
            background:
              "var(--surface-soft)",
            border:
              "1px solid var(--border)",
            fontSize: "8px",
          }}
        >
          Ctrl + Enter
        </code>

        <span>
          to submit
        </span>

      </div>

    </div>
  );
}

export default PromiseTracker;