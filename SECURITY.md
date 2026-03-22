# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Inzyts, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/kamuma03/Inzyts/security/advisories/new).

We will acknowledge your report within 48 hours and aim to provide a fix within 7 days for critical issues.

## Security Considerations

### API Keys and Secrets

- **Never commit API keys or secrets** to the repository
- Use the `.env` file for local development (already in `.gitignore`)
- See `config/.env.example` for the expected environment variables
- Generate tokens with: `python -c "import secrets; print(secrets.token_hex(32))"`

### Sandbox Execution

Inzyts executes LLM-generated code in a sandboxed environment with:
- Isolated namespace (no access to the host file system)
- Allowlisted imports only
- 60-second timeout per cell execution
- No network access from sandbox

### Authentication

- JWT-based login with bcrypt password hashing (`POST /api/v2/auth/login`)
- System API token (`INZYTS_API_TOKEN`) for worker/server-to-server calls, verified with `secrets.compare_digest` (constant-time)
- `ADMIN_PASSWORD` is required — the server refuses to start without it (no default value)
- JWT tokens stored in `sessionStorage` only (cleared on tab/browser close)
- JWT claims include `sub` (username) and `role` for stateless authorization
- Token expiry configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 7 days)

### Role-Based Access Control (RBAC)

- Three-tier role hierarchy: **Admin** > **Analyst** > **Viewer**
- Roles stored in the `users` table (`role` column, PostgreSQL enum) and embedded in JWT claims
- `require_role()` FastAPI dependency factory enforces role checks with hierarchy awareness — admins automatically pass analyst-level checks
- First-boot admin auto-creation assigns the `admin` role automatically
- System API tokens receive `admin` role for full access
- Admin-only endpoints: user management (`/api/v2/admin/users`), audit log queries (`/api/v2/admin/audit-logs`)
- Frontend routes guarded by role-based route components; admin navigation only visible to admin users

### Audit Logging

- All security-relevant actions are recorded in the `audit_logs` database table:
  - **Authentication**: successful logins, failed login attempts (with IP and username)
  - **Data operations**: analysis starts, file uploads, job cancellations
  - **User management**: user creation, role changes, account deactivation, deletion
- Each audit entry includes: timestamp, user ID, username, action, resource type/ID, detail, IP address, HTTP method/path, and status code
- `AuditMiddleware` (Starlette middleware) auto-logs API requests to security-relevant endpoints
- `record_audit()` async helper provides fine-grained logging from route handlers
- Audit log failures are caught and logged — they never break the request flow
- Admin-only query endpoint with filters: username, action type, date range
- IP extraction supports `X-Forwarded-For` headers for reverse proxy deployments

### SQL Database Security

- All LLM-generated SQL is validated via `sqlglot` AST parsing — only `SELECT` statements permitted
- Database connections enforce read-only transactions (`SET TRANSACTION READ ONLY`) as defense-in-depth
- URI scheme allowlist: `postgresql`, `mysql`, `mssql`, `bigquery`, `snowflake`, `redshift+redshift_connector`, `databricks+connector` — `sqlite://` is blocked
- Results capped at `SQL_MAX_ROWS` (default 200,000) and `SQL_MAX_COLS` (default 500)

### Cloud Storage Security

- Cloud URI scheme allowlist: `s3://`, `gs://`, `az://`, `abfs://`, `abfss://` only — `http://`, `ftp://`, `file://` are rejected
- Cloud credentials are never stored or accepted in the URI — they must be configured via environment variables (`AWS_ACCESS_KEY_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, `AZURE_STORAGE_CONNECTION_STRING`)
- File size limit enforced before download (`CLOUD_MAX_FILE_SIZE`, default 500 MB) to prevent resource exhaustion
- Downloaded files are placed in the upload directory with restricted permissions

### REST API Data Extraction Security

- **SSRF Protection**: All API URLs are resolved to IP addresses and checked against private/reserved ranges (RFC 1918, link-local, multicast); requests to internal networks are blocked
- `localhost`, `127.0.0.1`, and all loopback/private addresses are blocked — no exemptions, even for development
- Response size capped at `API_MAX_RESPONSE_SIZE` (default 100 MB)
- Request timeout enforced (`API_TIMEOUT`, default 30 seconds) to prevent hanging connections
- Authentication credentials (Bearer tokens, API keys, Basic auth) are passed via headers only — never logged or persisted

### PII Detection & Report Security

- **PII Detection Service**: Regex-based scanner identifies emails, US phone numbers, SSNs, credit card numbers, and IP addresses in notebook content (markdown cells, code source, and code outputs)
- PII findings are deduplicated and partially masked in scan results (e.g., `j***@example.com`, `***-**-6789`) so sensitive data is not fully exposed in the API response
- Common/safe IPs (127.0.0.1, 0.0.0.0, etc.) are excluded from PII findings to reduce false positives
- **Optional PII Masking**: Report export supports `include_pii_masking` flag that replaces all detected PII with redacted placeholders (`[EMAIL]`, `[SSN]`, `[PHONE]`, etc.) before rendering
- PII scan is informational — it never blocks report generation or analysis execution
- Report files are written to `{output_dir}/reports/` alongside existing notebook output

### Credential & Error Handling

- Log messages emitted to WebSocket clients are automatically scrubbed of database URI credentials and API keys/tokens
- API error responses never expose internal details (stack traces, file paths) — errors are logged server-side only
- Password verification failures are logged at WARNING level for security monitoring

### Frontend Security

- All markdown rendered via `dangerouslySetInnerHTML` is sanitized with DOMPurify using a strict tag/attribute allowlist
- Frontend validates DB URI schemes against an allowlist before submission
- File path inputs reject colon characters to prevent URI-based attacks

### Docker Deployment

- Database (5432) and Redis (6379) ports are bound to `127.0.0.1` by default — not exposed externally
- Services are isolated across two Docker networks (`backend` and `db`)
- All services have memory limits enforced via Docker resource constraints
- Backend includes a healthcheck; frontend waits for backend health before starting
- Restart policy is `on-failure:5` to prevent infinite restart loops
- Upload directory has restricted permissions (`chmod 750`)
- Jupyter containers run as non-root (`jovyan` user)
- Use a reverse proxy (e.g., nginx) with TLS for public-facing deployments

### Kernel Bootstrap Security

- Dataset paths are passed to Jupyter kernels via environment variables (not string interpolation) to prevent code injection
- Kernel sessions use LRU eviction when the session limit is reached (graceful degradation instead of hard errors)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.10.0  | Yes       |
