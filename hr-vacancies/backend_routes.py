# REFERENCE EXTRACT ONLY. Uses shared definitions from career/workflow.py.
# Do not register/import this file as an additional Flask blueprint.

# Source: career/workflow.py:934
@workflow_bp.get("/api/workflow/jobs")
def jobs():
    service, user = _service(), _service().current_user()
    profile = service.profile(user)["resume"] if user and user["role"] == "jobseeker" else None
    if not user or user["role"] != "jobseeker":
        raw = request.args.get("skills", "")
        if len(raw) > 1000:
            _fail("Skill filter is too long.")
        try:
            weekly_hours = int(request.args.get("weekly_hours", "6"))
        except (ValueError, TypeError):
            _fail("Weekly learning hours must be a whole number from 1 to 40.")
        if not 1 <= weekly_hours <= 40:
            _fail("Weekly learning hours must be a whole number from 1 to 40.")
        profile = {"skills": _skills(raw.split(",") if raw else []), "weekly_hours": weekly_hours}
    search = request.args.get("search", "").strip().casefold()
    location = request.args.get("location", "").strip().casefold()
    mode = request.args.get("work_mode", "")
    if mode and mode not in {"remote", "hybrid", "onsite"}:
        _fail("Choose remote, hybrid or onsite.")
    if len(search) > 200 or len(location) > 120:
        _fail("Search filter is too long.")
    mine = request.args.get("mine") == "1"
    sorting = request.args.get("sort", "newest" if mine else "match")
    if sorting not in {"match", "newest"}:
        _fail("Choose match or newest ordering.")
    if mine:
        _user("hr")
    with service.connection() as con:
        if mine:
            rows = con.execute("SELECT j.* FROM jobs j JOIN companies c ON c.id=j.company_id WHERE c.owner_id=? ORDER BY j.id DESC", (user["id"],)).fetchall()
        else:
            rows = con.execute("SELECT * FROM jobs WHERE salary_min>0 AND salary_max>=salary_min ORDER BY id DESC").fetchall()
        items = []
        for row in rows:
            application = con.execute("SELECT id,status FROM applications WHERE job_id=? AND applicant_id=?", (row["id"], user["id"])).fetchone() if user and user["role"] == "jobseeker" else None
            item = service.job_view(con, row, profile, application)
            text = " ".join([item["title"], item["description"], item["company"]["name"], *[skill["name"] for skill in item["required_skills"]]]).casefold()
            if search and search not in text or location and location not in item["location"].casefold() or mode and item["work_mode"] != mode:
                continue
            items.append(item)
    if sorting == "match":
        items.sort(key=lambda item: (-item["match"]["percentage"], -item["id"]))
    return jsonify(jobs=items, profile=profile, sort=sorting)

# Source: career/workflow.py:980
def _owned_job(con, identifier, user):
    _positive_id(identifier, "Job ID")
    row = con.execute("SELECT j.* FROM jobs j JOIN companies c ON c.id=j.company_id WHERE j.id=? AND c.owner_id=?", (identifier, user["id"])).fetchone()
    if not row:
        _fail("Job not found in your company.", 404)
    return row

# Source: career/workflow.py:988
def _salary_for_owner(payload, user):
    try:
        return _salary(payload)
    except WorkflowError:
        # Save a transparent policy incident independently of the rejected job
        # transaction, so rejecting invalid pay cannot silently erase a penalty.
        with _service().connection() as con:
            company = con.execute("SELECT id FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
            if company:
                con.execute("INSERT INTO compliance_incidents(company_id,kind,detail,created_at) VALUES(?,'invalid_salary','A vacancy submission was rejected because its base salary range was missing or invalid.',?)", (company["id"], _iso()))
                _notify(con, user["id"], "compliance", "Vacancy rejected: supply a valid base salary range. Accountability score reduced by 10.")
        raise

# Source: career/workflow.py:1002
@workflow_bp.post("/api/workflow/jobs")
def create_job():
    user, payload = _user("hr"), _json()
    if not user["onboarding_complete"]:
        _fail("Complete your company profile before posting a job.", 409)
    title = _text(payload, "title", 160, required=True)
    description = _text(payload, "description", 3000, required=True)
    location = _text(payload, "location", 120, required=True)
    role_id = payload.get("role_id")
    if not _is_choice(role_id, ROLE_MAP):
        _fail("Select a role from the catalogue.")
    required = _skills(payload.get("required_skills", []), required=True)
    mode = payload.get("work_mode")
    employment = payload.get("employment_type")
    if not _is_choice(mode, {"remote", "hybrid", "onsite"}) or not _is_choice(employment, {"full-time", "part-time", "internship"}):
        _fail("Select a valid work arrangement and employment type.")
    try:
        deadline = date.fromisoformat(payload.get("deadline", ""))
    except (TypeError, ValueError):
        _fail("Enter a valid application deadline.")
    if deadline <= _today() or deadline == date.max:
        _fail("Application deadline must be after today.")
    salary = _salary_for_owner(payload, user)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        company = _service().company(con, user["id"])
        if not company:
            _fail("Complete your company profile first.", 409)
        _publishing_allowed(company)
        cursor = con.execute("INSERT INTO jobs(company_id,title,role_id,description,location,work_mode,employment_type,required_skills_json,deadline,created_at,salary_min,salary_max,salary_currency,salary_period) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (company["id"], title, role_id, description, location, mode, employment, json.dumps(required), deadline.isoformat(), _iso(), *salary))
        row = con.execute("SELECT * FROM jobs WHERE id=?", (cursor.lastrowid,)).fetchone()
        result = _service().job_view(con, row)
    return jsonify(job=result), 201

# Source: career/workflow.py:1038
@workflow_bp.patch("/api/workflow/jobs/<int:identifier>")
def change_job(identifier):
    user, payload = _user("hr"), _json()
    with _service().connection() as con:
        previous = _owned_job(con, identifier, user)
    status = payload.get("status", previous["status"])
    if not _is_choice(status, {"open", "closed"}):
        _fail("Choose open or closed.")
    salary_payload = {key: payload.get(key, previous[key]) for key in ("salary_min", "salary_max", "salary_currency", "salary_period")}
    salary = _salary_for_owner(salary_payload, user)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = _owned_job(con, identifier, user)
        if status == "open" and date.fromisoformat(row["deadline"]) < _today():
            _fail("An expired job cannot be reopened.", 409)
        if status == "open":
            _publishing_allowed(_service().company(con, user["id"]))
        con.execute("UPDATE jobs SET status=?,salary_min=?,salary_max=?,salary_currency=?,salary_period=? WHERE id=?", (status, *salary, identifier))
        result = _service().job_view(con, con.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone())
    return jsonify(job=result)
