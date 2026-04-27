from sqlalchemy import Column, String, Enum, DateTime, JSON, ForeignKey, Integer, Float, Boolean, Text
from sqlalchemy.sql import func
import enum
from .database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False, server_default=UserRole.VIEWER.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Ownership — nullable for backwards compatibility with existing rows.
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    status: Column = Column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    mode = Column(
        String
    )  # PipelineMode: exploratory, predictive, diagnostic, comparative, forecasting, segmentation
    title = Column(String, nullable=True)

    # Inputs
    csv_path = Column(String)
    csv_hash = Column(String(64), nullable=True, index=True)  # sha256 of resolved CSV bytes
    multi_file_input = Column(JSON, nullable=True)  # v1.8.0 Multi-file configuration
    dict_path = Column(String, nullable=True)  # Data dictionary
    target_column = Column(String, nullable=True)
    analysis_type = Column(String, nullable=True)  # classification, regression, etc.
    question = Column(String, nullable=True)

    # Outputs
    result_path = Column(String, nullable=True)
    error_message = Column(String(2000), nullable=True)
    logs_location = Column(String, nullable=True)  # Path to log file

    # Executive summary (generated once after notebook assembly)
    executive_summary = Column(JSON, nullable=True)

    # Metrics
    token_usage = Column(
        JSON, default=dict
    )  # {"prompt": 0, "completion": 0, "total": 0}
    cost_estimate = Column(
        JSON, default=dict
    )  # {"input": 0.0, "output": 0.0, "total": 0.0}
    cost_breakdown = Column(
        JSON, nullable=True
    )  # [{"phase": "phase1", "cost_usd": 0.12, "is_estimate": false}, ...]


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobProgress(Base):
    __tablename__ = "job_progress"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), index=True)
    phase = Column(String)
    progress = Column(Integer)
    message = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class ConversationMessage(Base):
    """Persistent follow-up conversation message linked to a job.

    Stores each Q&A exchange so conversations survive server restarts.
    The 'role' field is either 'user' (question) or 'assistant' (answer + cells).
    """

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), index=True, nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(String, nullable=False)  # question text or summary text
    cells = Column(JSON, nullable=True)  # [{cell_type, source, output, images}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Records security-relevant user actions for compliance and forensics."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id = Column(String, index=True, nullable=True)  # null for unauthenticated events
    username = Column(String, index=True, nullable=True)
    action = Column(String, nullable=False, index=True)  # e.g. "login", "analyze", "upload_file"
    resource_type = Column(String, nullable=True)  # e.g. "job", "file", "user"
    resource_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)  # JSON-serializable extra context
    ip_address = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    method = Column(String, nullable=True)  # HTTP method
    path = Column(String, nullable=True)  # request path
