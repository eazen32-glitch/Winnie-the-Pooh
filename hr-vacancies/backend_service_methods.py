# REFERENCE EXTRACT ONLY. This is a partial class, not the runnable service.
# Keep the full WorkflowService and migrations in career/workflow.py.

class WorkflowService:
    # Source: career/workflow.py:343
    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    # Source: career/workflow.py:566
    def company(self, con, user_id):
        row = con.execute("SELECT * FROM companies WHERE owner_id=?", (user_id,)).fetchone()
        return self.company_view(con, row, private=True) if row else None

    # Source: career/workflow.py:570
    def company_view(self, con, row, private=False):
        result = {key: row[key] for key in ("id", "name", "industry", "location", "description", "website")}
        result["verification"] = _verification_view(row, private=private)
        violations = con.execute("SELECT COUNT(*) FROM compliance_incidents WHERE company_id=?", (row["id"],)).fetchone()[0]
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        overdue = con.execute(f"SELECT COUNT(*) FROM applications a JOIN jobs j ON j.id=a.job_id WHERE j.company_id=? AND a.status IN ({placeholders}) AND a.response_due_at<?",
                              (row["id"], *ACTIVE_STATUSES, _iso())).fetchone()[0]
        result["accountability"] = {"score": max(0, 100 - violations * 10 - overdue * 5), "violations": violations,
                                    "overdue_applications": overdue, "method": "100 minus 10 per salary incident and 5 per currently overdue application; prototype policy."}
        if private:
            result["owner_id"] = row["owner_id"]
            result.update({key: row[key] for key in ("registration_number", "recruiter_identity", "evidence_note")})
        return result

    # Source: career/workflow.py:590
    def job_view(self, con, row, resume=None, application=None):
        company = con.execute("SELECT * FROM companies WHERE id=?", (row["company_id"],)).fetchone()
        requirements = json.loads(row["required_skills_json"])
        known = (resume or {}).get("skills", [])
        weekly_hours = (resume or {}).get("weekly_hours", 6)
        pathway = build_skill_pathway(requirements, known, weekly_hours)
        pathway["weekly_hours"] = weekly_hours
        return {"id": row["id"], "title": row["title"], "role_id": row["role_id"], "description": row["description"],
                "location": row["location"], "work_mode": row["work_mode"], "employment_type": row["employment_type"],
                "required_skills": [_skill_view(value) for value in requirements], "deadline": row["deadline"],
                "status": row["status"], "company": self.company_view(con, company), "synthetic": True,
                "salary_min": row["salary_min"], "salary_max": row["salary_max"], "salary_currency": row["salary_currency"], "salary_period": row["salary_period"],
                "salary": {"minimum": row["salary_min"], "maximum": row["salary_max"], "currency": row["salary_currency"], "period": row["salary_period"], "illustrative": True},
                "exposure": role_exposure(row["role_id"]),
                "match": _match(requirements, known), "pathway": pathway,
                "application_id": application["id"] if application else None,
                "application_status": application["status"] if application else None}
