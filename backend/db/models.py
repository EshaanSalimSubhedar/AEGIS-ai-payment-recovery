from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATABASE_PATH = (
    BASE_DIR
    / "backend"
    / "recovery.db"
)

DATABASE_URL = (
    f"sqlite:///{DATABASE_PATH}"
)


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


# ============================================================
# FAILED PAYMENT
# ============================================================

class FailedPayment(Base):
    __tablename__ = "failed_payments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Original Razorpay payment
    razorpay_payment_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    # Customer information
    customer_name = Column(
        String,
        nullable=False,
    )

    customer_contact = Column(
        String,
        nullable=False,
    )

    language_pref = Column(
        String,
        default="english",
        nullable=False,
    )

    # Payment information
    amount = Column(
        Float,
        nullable=False,
    )

    failure_reason = Column(
        String,
        nullable=False,
    )

    recovery_score = Column(
        Float,
        nullable=False,
    )

    # Recovery state
    status = Column(
        String,
        default="pending",
        nullable=False,
        index=True,
    )

    attempts = Column(
        Integer,
        default=0,
        nullable=False,
    )

    # ========================================================
    # RECOVERY FLOW CORRELATION
    # ========================================================

    recovery_reference_id = Column(
        String,
        nullable=True,
        index=True,
    )

    recovery_reference_type = Column(
        String,
        nullable=True,
    )

    # ========================================================
    # TIMING
    # ========================================================

    last_attempt_at = Column(
        DateTime,
        nullable=True,
    )

    next_action_at = Column(
        DateTime,
        nullable=True,
    )

    # ========================================================
    # PAYMENT LINK / RECOVERY
    # ========================================================

    payment_link = Column(
        String,
        nullable=True,
    )

    recovered_at = Column(
        DateTime,
        nullable=True,
    )

    # ========================================================
    # CUSTOMER SAFETY
    # ========================================================

    opted_out = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ========================================================
    # TIMESTAMPS
    # ========================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    audit_entries = relationship(
        "AuditLog",
        back_populates="payment",
        cascade="all, delete-orphan",
    )

    promises = relationship(
        "PromiseToPay",
        back_populates="payment",
        cascade="all, delete-orphan",
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    payment_id = Column(
        Integer,
        ForeignKey(
            "failed_payments.id"
        ),
        nullable=False,
        index=True,
    )

    action = Column(
        String,
        nullable=False,
    )

    reasoning = Column(
        Text,
        nullable=False,
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    payment = relationship(
        "FailedPayment",
        back_populates="audit_entries",
    )


# ============================================================
# PROMISE TO PAY
# ============================================================

class PromiseToPay(Base):
    __tablename__ = "promises_to_pay"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    payment_id = Column(
        Integer,
        ForeignKey(
            "failed_payments.id"
        ),
        nullable=False,
        index=True,
    )

    promised_date = Column(
        Date,
        nullable=False,
    )

    fulfilled = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    follow_up_sent = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    payment = relationship(
        "FailedPayment",
        back_populates="promises",
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db() -> None:
    """
    Create database tables if they do not already exist.
    """

    Base.metadata.create_all(
        bind=engine,
    )


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()