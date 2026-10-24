# REFERENCE EXTRACT ONLY. Uses shared definitions from career/workflow.py.
# Do not register/import this file as an additional Flask blueprint.

# Source: career/workflow.py:43
class WorkflowError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

# Source: career/workflow.py:49
def _fail(message, status=400):
    raise WorkflowError(message, status)

# Source: career/workflow.py:58
def _now():
    return datetime.now(UTC)

# Source: career/workflow.py:62
def _iso(value=None):
    return (value or _now()).astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

# Source: career/workflow.py:66
def _today():
    return _now().astimezone(LOCAL_ZONE).date()

# Source: career/workflow.py:70
def _json():
    if not request.is_json:
        _fail("Send application/json.", 415)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        _fail("Send a JSON object.")
    return payload

# Source: career/workflow.py:79
def _text(payload, key, maximum=240, *, required=False, default=""):
    value = payload.get(key, default)
    if not isinstance(value, str) or len(value) > maximum:
        _fail(f"{key.replace('_', ' ').capitalize()} must be text of at most {maximum} characters.")
    value = value.strip()
    if required and not value:
        _fail(f"{key.replace('_', ' ').capitalize()} is required.")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        _fail(f"{key.replace('_', ' ').capitalize()} contains unsupported characters.")
    return value

# Source: career/workflow.py:91
def _skills(values, *, required=False):
    if not isinstance(values, list) or len(values) > len(SKILL_MAP):
        _fail("Select skills from the supplied catalogue.")
    if any(not isinstance(value, str) or value not in SKILL_MAP for value in values):
        _fail("Select skills from the supplied catalogue.")
    if len(set(values)) != len(values):
        _fail("Select each skill only once.")
    if required and not values:
        _fail("Select at least one skill.")
    return values

# Source: career/workflow.py:103
def _positive_id(value, field="ID"):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2**63 - 1:
        _fail(f"{field} must be a positive whole number.")
    return value

# Source: career/workflow.py:109
def _is_choice(value, choices):
    return isinstance(value, str) and value in choices

# Source: career/workflow.py:151
def _salary(payload):
    values = []
    for key in ("salary_min", "salary_max"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1_000_000_000 or not math.isfinite(value):
            _fail("A positive, finite minimum and maximum base salary are required.")
        values.append(round(value, 2))
    if min(values) <= 0:
        _fail("Base salary must be at least 0.01 in the selected currency.")
    if values[0] > values[1]:
        _fail("Maximum base salary must be at least the minimum base salary.")
    currency = payload.get("salary_currency")
    period = payload.get("salary_period")
    if not _is_choice(currency, SALARY_CURRENCIES) or not _is_choice(period, SALARY_PERIODS):
        _fail("Choose a supported salary currency and pay period.")
    return (*values, currency, period)

# Source: career/workflow.py:300
def _publishing_allowed(company):
    if current_app.config.get("REQUIRE_EMPLOYER_VERIFICATION", True) and not company["verification"]["can_publish"]:
        _fail("Complete current registry, company domain and independent moderator checks before publishing a vacancy.", 409)

# Source: career/workflow.py:630
def _service():
    return current_app.extensions["workflow"]

# Source: career/workflow.py:634
def _user(role=None):
    user = _service().current_user()
    if not user:
        _fail("Sign in to use this feature.", 401)
    if role and user["role"] != role:
        _fail("This action is not available for your account type.", 403)
    return user

# Source: career/workflow.py:657
@workflow_bp.before_request
def csrf_check():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not token or not supplied or not hmac.compare_digest(token.encode("utf-8"), supplied.encode("utf-8")):
            _fail("Your session token is missing or expired. Reload and try again.", 403)
