# HR vacancy posting: code extract and editing guide

HR can **enter and publish a synthetic vacancy through a form**. This feature is not a PDF/file upload. A published vacancy is saved in the running app's local SQLite database and shown in Find a job. No external recruitment API is involved.

**Edit the original application files listed below to change the running app.** The files in this directory are reference extracts, not an independent app or drop-in replacements for the full modules. They use the original account, catalogue, verification, session and database helpers. Loading them alongside the existing files would duplicate functions/listeners/routes. The original feature has not been refactored or changed by this extraction.

## Where the working code lives

| What to change | Original file / entry point |
| --- | --- |
| Vacancy form and fields | [templates/workflow.html](../../../templates/workflow.html#L355), `#hr-job-management` / `#job-create-form` |
| Form submission and payload | [static/workflow.js](../../../static/workflow.js#L684), `createJob(form)` |
| Automatically populate required skills for a selected role | `populateJobRequirements()` in `static/workflow.js:610`; catalogue in `career/catalog.py` |
| HR's own published-vacancy list | `loadOwnJobs()` in `static/workflow.js:1069` |
| Candidate vacancy cards | `renderJobs()` / `loadJobs()` in `static/workflow.js` |
| Create/publish backend | [career/workflow.py](../../../career/workflow.py#L1003), `create_job()` / `POST /api/workflow/jobs` |
| List vacancies | `jobs()` in `career/workflow.py:935`; `GET /api/workflow/jobs`, with `?mine=1` for the HR owner's list |
| Update salary or open/closed status | `change_job()` in `career/workflow.py:1039`; `PATCH /api/workflow/jobs/<id>` |
| Salary validation | `_salary()` in `career/workflow.py:151` |
| Publishing approval | `_publishing_allowed()` in `career/workflow.py:300`; frontend `publishingAllowed()` / `renderPublishingPolicy()` |
| Database and response shape | `WorkflowService.initialize()`, `_migrate()` and `job_view()` in `career/workflow.py` |
| Form appearance | `.workflow-form`, `.workflow-form-grid`, `.workflow-salary-form` in `static/workflow.css`; palette in `static/theme.css` |
| App integration | `app.py` registers `workflow_bp`; `templates/index.html` includes the workflow template and loads its JS/CSS. |

Line numbers identify the source at extraction time. `source_manifest.json` records the source commit and individual excerpt positions/hashes. Search for the named function/DOM ID if later changes move lines.

## What is included in this folder

| Reference file | Contents |
| --- | --- |
| `vacancy_form.html` | Exact HR vacancy management/form markup. |
| `frontend_functions.js` | Request/CSRF helper, form helpers, role/skill population, posting, salary updates, listing and publishing-policy functions. |
| `frontend_event_fragments.js` | Relevant parts of the existing submit/click/change listeners, placed in labelled wrappers for reading. These wrappers are not new listeners to register. |
| `backend_routes.py` | Exact list/create/update routes plus ownership/salary incident helpers. |
| `backend_validation_and_auth.py` | Relevant validators, HR/session/CSRF checks and publishing gate. Shared globals/imports remain in the original module. |
| `backend_service_methods.py` | Partial service methods showing SQLite connections and job/company response construction. The full service/migrations remain in the original module. |
| `schema_reference.sql` | Current migrated users/companies/jobs schema, generated from an isolated temporary fixture. No account or vacancy rows are exported. This is not a production migration script. |
| `reference_workflow.css`, `reference_theme.css` | Full style context copied from the originals; edit the originals in `static/`. |
| `example_request.json` | Example vacancy payload using valid catalogue IDs. Change the deadline to a date after today. |
| `source_manifest.json` | Source positions and hashes to trace the extract back to the working code. |

The Python/JavaScript extracts depend on shared state, imports and helpers, including `WorkflowService`, `ROLE_MAP`, `SKILL_MAP`, salary constants, the NextStep browser bridge and existing session/verification functions. A syntax check passing does not make a reference extract independently runnable.

## Current vacancy fields

| JSON/form key | Type / rule |
| --- | --- |
| `title` | Required text, at most 160 characters. |
| `role_id` | Required catalogue role ID. |
| `description` | Required text, at most 3,000 characters. |
| `location` | Required text, at most 120 characters. |
| `work_mode` | `remote`, `hybrid` or `onsite`. |
| `employment_type` | `full-time`, `part-time` or `internship`. |
| `required_skills` | Non-empty array of distinct catalogue skill IDs. |
| `deadline` | Valid `YYYY-MM-DD` after the current Malaysia date. No fixed six-month cap is implemented. |
| `salary_min`, `salary_max` | Positive finite numbers, rounded to two decimals; maximum at least minimum. |
| `salary_currency` | `MYR`, `USD`, `SGD`, `GBP`, `EUR` or `AUD`. |
| `salary_period` | `hour`, `month` or `year`. |

The company ID is derived from the authenticated HR owner; the client does not choose another company's ID. `created_at` and initial open status are assigned on the server/database side.

## Request flow

1. HR opens My profile, completes the company information and the current publishing checks.
2. The form captures fields. `createJob(form)` converts salary inputs to numbers and selected skills to an array.
3. The request helper sends JSON to `POST /api/workflow/jobs` with the session cookie and `X-CSRF-Token`.
4. Flask checks HR role, onboarding, fields, salary, future deadline and company publishing approval.
5. A transaction inserts the vacancy into `jobs`, builds the response through `job_view()` and returns HTTP **201**.
6. The form resets and reloads the HR list and candidate job explorer.

The frontend publishing button is a convenience, not the security boundary: the backend checks must remain in place. Invalid fields generally return 400; missing/incorrect account permissions or CSRF return 401/403; incomplete company setup/checks or reopening an expired job can return 409. The UI displays the backend's explanation.

## How to edit safely on top of the existing feature

### Change labels, layout or existing input constraints

Edit the original HTML and workflow/theme CSS. Keep field `name` values consistent with the JSON keys and preserve IDs referenced by JavaScript. Server validation still applies even if the HTML constraint is changed.

### Add a new stored field

1. Add its input to `templates/workflow.html` and use a clear `name`.
2. In `createJob(form)`, convert numeric/boolean/array inputs explicitly. `FormData` normally produces strings.
3. Validate it in `create_job()` on the backend.
4. Add an additive migration in `WorkflowService._migrate()` with a sensible treatment for existing rows, and update the insert. Do not reset/delete the database to add a column.
5. Expose it in `WorkflowService.job_view()` and render it in the HR/candidate views as appropriate. Preserve escaping for user-entered text.
6. If existing vacancies must be editable, explicitly extend `change_job()` and the corresponding edit UI, maintaining ownership and relevant validation.
7. Exercise valid/invalid values, an old database and another account's attempted edit.

**Current edit scope:** the PATCH route updates salary and open/closed status. It does not currently update title, description, location, role, skill requirements or deadline. Adding inputs alone will not enable those updates.

## Run and review the existing feature

From the main SDC repository, use the existing virtual environment:

```bash
source .venv/bin/activate
python app.py --port 5001
```

Open `http://127.0.0.1:5001`, choose HR, and open My profile. Default publishing requires the fictional registry check, simulated domain challenge and a separate moderator approval; the presence of seeded sample vacancies is not approval to publish a new one. Use the steps in [the workflow guide](../../../docs/WORKFLOWS.md#hr-demonstration). Keep the demo synthetic and avoid real employer/personal documents.

The following existing tests cover posting/ownership, closing, salary validation and permitted salary edits:

```bash
python -m pytest -q tests/test_workflow.py::test_job_creation_is_owned_and_closing_prevents_applications tests/test_workflow.py::test_jobseekers_cannot_create_jobs tests/test_workflow_requirements.py::test_invalid_salary_never_publishes_and_policy_incident_survives_rejection tests/test_workflow_requirements.py::test_salary_edit_and_currency_are_returned_with_the_vacancy
```

Use temporary fixtures for verification, not the shared demo database. Keep session and CSRF handling, backend HR/company ownership, salary validation, publishing checks, bound SQL parameters and account-change guards when changing the feature.

Extraction verification on 24 October 2026: all 16 targeted posting/ownership/salary cases above passed in 9.00 seconds. Extracted Python/JavaScript passed syntax checks, and the isolated schema includes the migrated salary columns. These results apply to the existing feature; future field/rule changes need their corresponding checks.

## Refresh this reference extract

```bash
.venv/bin/python tools/extract_hr_vacancy_reference.py
```

This overwrites generated reference files and rebuilds `docs/feature-extracts/hr-vacancy-feature.zip`. It leaves the original application sources and user database untouched. Make working changes in the original files, then regenerate the reference if useful.
