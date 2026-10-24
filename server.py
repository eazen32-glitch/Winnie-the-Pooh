# Backend: Skills extraction

import os, io, json, re, uuid, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).parent

SDG = {1: "No Poverty", 2: "Zero Hunger", 3: "Good Health and Well-being", 4: "Quality Education",
       5: "Gender Equality", 6: "Clean Water and Sanitation", 7: "Affordable and Clean Energy",
       8: "Decent Work and Economic Growth", 9: "Industry, Innovation and Infrastructure",
       10: "Reduced Inequalities", 11: "Sustainable Cities and Communities", 
       12: "Responsible Consumption and Production", 13: "Climate Action", 14: "Life Below Water",
       15: "Life on Land", 16: "Peace, Justice and Strong Institutions", 17: "Partnerships for the Goals"
       }

'''
a = aliases found in CVs
c = category
t = AI-era trend
d = demand index 0 - 100
s = linked SDGs
r = related skills
'''
def S(a,c,t,d,s,r=()):
    return dict(a=a, c=c, t=t, d=d, s=list(s), r=list(r))

SKILLS = {
    "Python": S(["python"], "Programming", "growing", 92, [9], ["SQL", "Data Analysis"]),
     "SQL": S(["sql", "mysql", "postgresql"], "Data", "stable", 80, [9], ["Python", "Data Analysis"]),
     "Machine Learning": S(["machine learning", "scikit-learn", "sklearn"], "AI", "growing", 94, [9, 3], ["Deep Learning", "Statistics"]),
     "Deep Learning": S(["deep learning", "pytorch", "tensorflow", "neural network"], "AI", "growing", 90, [9], ["Machine Learning"]),
     "NLP": S(["nlp", "natural language processing"], "AI", "growing", 85, [4, 16], ["Machine Learning", "Generative AI"]),
     "Generative AI": S(["generative ai", "llm", "prompt engineering", "chatgpt"], "AI", "emerging", 97, [4, 9], ["NLP", "Machine Learning"]),
     "MLOps": S(["mlops", "model deployment"], "AI", "emerging", 82, [9], ["Docker", "Cloud"]),
     "Data Analysis": S(["data analysis", "data analytics", "pandas", "analytics"], "Data", "growing", 88, [8, 9], ["Statistics", "Excel", "Python"]),
     "Data Visualization": S(["data visualization", "tableau", "power bi", "matplotlib"], "Data", "growing", 78, [9], ["Data Analysis"]),
     "Statistics": S(["statistics", "statistical", "probability"], "Data", "stable", 75, [9], ["Data Analysis", "Machine Learning"]),
     "Excel": S(["excel", "spreadsheet"], "Data", "declining", 55, [8], ["Data Analysis"]),
     "Cloud": S(["aws", "azure", "gcp", "cloud computing", "cloud"], "Engineering", "growing", 88, [9], ["Docker"]),
     "Docker": S(["docker", "kubernetes", "containers"], "Engineering", "growing", 80, [9], ["Cloud"]),
     "JavaScript": S(["javascript", "typescript", "node.js"], "Programming", "stable", 82, [9], ["React", "HTML/CSS"]),
     "React": S(["react", "vue", "front-end", "frontend"], "Programming", "stable", 74, [9], ["JavaScript", "HTML/CSS"]),
     "HTML/CSS": S(["html", "css"], "Programming", "stable", 65, [9], ["JavaScript"]),
     "Java": S(["java", "spring boot"], "Programming", "stable", 70, [9], ["Python"]),
     "API Design": S(["api", "rest", "flask", "fastapi", "django"], "Engineering", "stable", 76, [9], ["Python", "JavaScript"]),
     "Cybersecurity": S(["cybersecurity", "cyber security", "penetration testing", "network security"], "Security", "growing", 90, [16, 9], ["Cloud"]),
     "IoT": S(["iot", "internet of things", "embedded", "sensors", "arduino"], "Engineering", "growing", 72, [9, 11, 6], ["Python"]),
     "Renewable Energy": S(["renewable energy", "solar", "wind power", "energy storage", "smart grid"], "Sustainability", "growing", 80, [7, 13], ["Sustainability Reporting"]),
     "Sustainability Reporting": S(["sustainability", "esg", "carbon accounting", "life cycle assessment"], "Sustainability", "emerging", 78, [12, 13], ["Policy Analysis"]),
     "Policy Analysis": S(["policy analysis", "public policy", "regulatory"], "Social", "stable", 60, [16, 10], ["Sustainability Reporting"]),
     "Healthcare Informatics": S(["healthcare informatics", "health informatics", "clinical data", "ehr"], "Domain", "growing", 76, [3], ["Data Analysis"]),
     "Curriculum Design": S(["curriculum", "instructional design", "e-learning", "teaching"], "Domain", "growing", 66, [4], ["Communication"]),
     "Project Management": S(["project management", "agile", "scrum", "pmp"], "Business", "stable", 72, [8, 17], ["Leadership"]),
     "Leadership": S(["leadership", "team lead", "led a team", "mentoring"], "Business", "growing", 74, [8], ["Project Management", "Communication"]),
     "Communication": S(["communication", "presentation", "stakeholder", "public speaking"], "Business", "growing", 80, [4, 17], ["Leadership"]),
     "UX Design": S(["ux", "ui design", "figma", "user research"], "Design", "growing", 70, [9, 10], ["HTML/CSS"]),
     "Supply Chain": S(["supply chain", "logistics", "procurement"], "Domain", "stable", 62, [2, 12], ["Data Analysis"]),
     "Manual Data Entry": S(["data entry", "manual reporting"], "Admin", "declining", 15, [8]),
     "Legacy COBOL": S(["cobol", "mainframe"], "Programming", "declining", 20, [9]),
}

REL = {k: set(v["r"]) for k,v in SKILLS.items()}
for k,v in list(REL.items()):
    for o in v: REL.setdefault(o,set()).add(k)

def J(id, title, company, loc, sdgs, req, pref, yrs, edu, thr, abt):
    return dict(id=id, title=title, company=company, location=loc, sdgs=sdgs, required=req, 
                preferred=pref, min_years=yrs, education=edu, threshold=thr, about=abt)

JOBS = [
    J(1, "Junior ML Engineer", "NovaCloud", "Federal Territory of Kuala Lumpur", [9, 8], ["Python", "Machine Learning", "SQL"], ["Docker", "MLOps", "Statistics"],1,2,60,
                                                                                          "Build and ship models that power smart-city services."),
    J(2, "Data Analyst, Clean Energy", "BuildGreen Energy", "Cyberjaya", [7, 13], ["Data Analysis", "SQL", "Data Visualization"], ["Python", "Renewable Energy", "Excel"], 1, 2, 55, 
                                                                                   "Turn grid and solar data into decisions for lower-carbon power."),     
    J(3, "Generative AI Specialist", "EduSpark", "Remote", [4, 9], ["Generative AI", "Python", "NLP"], ["API Design", "Curriculum Design", "Communication"], 2, 2, 65, 
                                                                    "Design AI tutors that reach students who lack access to teachers."),
    J(4, "Health Data Scientist", "MedicAI Labs", "Penang", [3, 10], ["Machine Learning", "Statistics", "Python", "Healthcare Informatics"], ["Deep Learning", "Data Visualization"], 2, 3, 70, 
                                                                     "Predict patient risk and improve care in under-served clinics."),
    J(5, "Water IoT Engineer", "AquaSense", "Seremban", [6, 11, 14], ["IoT", "Python", "Cloud"], ["Data Analysis", "Docker"], 2, 2, 65, 
                                                                         "Deploy sensor networks that detect leaks and pollution early."),
    J(6, "Sustainability Analyst", "Harvest Logic", "Federal Territory of Kuala Lumpur", [12, 13, 2], ["Sustainability Reporting", "Data Analysis", "Communication"], ["Supply Chain", "Excel", "Policy Analysis"], 1, 2, 55, 
                                                                                  "Measure and cut the carbon footprint of food supply chains."),
    J(7, "Security Engineer", "BDC Asia", "Cyberjaya", [16, 9], ["Cybersecurity", "Cloud", "Python"], ["Docker", "API Design"], 3, 2, 70, 
                                                                 "Protect public-sector digital services against attacks."),
    J(8, "Full-Stack Developer", "CiviTech Malaysia", "Remote", [16, 10, 11], ["JavaScript", "React", "API Design", "HTML/CSS"], ["UX Design", "SQL", "Cloud"], 2, 2, 60, 
                                                                               "Build open portals that make public services easier to use."),
] # Can be added in the future

SALARY = {1:(4000,6000), 2:(3500, 5000), 3:(6000,9000), 4:(7000,10500),
          5:(5000,7500), 6:(4000,5800), 7:(7000, 11000), 8:(4500,8000)}
for j in JOBS:
    j["salary_min"], j["salary_max"] = SALARY[j["id"]]
    j["currency"], j["period"] = "RM", "month"

W = dict(required=.60, preferred=.15, experience=.15, education=.10) #Weighing
EDU_NAME = {0: "not stated", 1:"diploma", 2:"bachelor", 3:"master", 4: "PhD"}
PAT = {k: re.compile(r"(?<![a-z0-9+#])(?:%s)(?![a-z0-9+#])" % "|".join(re.escape(a) for a in v["a"]))
       for k,v in SKILLS.items()}

def read_cv(data: bytes, filename: str) -> str:
    name=(filename or "").lower()
    if name.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf8", "ignore")
        return re.sub(r"<[^>]+>", " ", xml.replace("</w:p>", "\n"))
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("PDF reading needs 'pip install pypdf'. Or upload .docx/.txt, or paste your CV text.")
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    return data.decode("utf8", "ignore")

def profile(text: str) -> dict:
    low = text.lower()
    skills=[k for k, p in PAT.items() if p.search(low)]
    yrs = [int(m) for m in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)", low)]
    edu = 4 if re.search(r"ph\.?d|doctorate", low) else 3 if re.search(r"master|m\.?sc|mba", low) else \
          2 if re.search(r"bachelor|b\.?sc|b\.?eng|degree", low) else 1 if "diploma" in low else 0
    return dict(skills=skills, years=max(yrs) if yrs else 0, education=edu)

def credit(skill, have):
    if skill in have: return 1.0, "matched"
    if REL.get(skill, set()) & have: 
        return 0.5, "partial"
    return 0.0, "missing"

def score_job(profile, job):
    have = set(profile["skills"])
    def part(names):
        rows = [(n, *credit(n, have)) for n in names]
        return (sum(c for _, c, _ in rows) / len(rows) if rows else 1.0), rows
    req_s, req = part(job["required"])
    pref_s, pref=part(job["preferred"])
    exp_s = min(1, profile["years"] / job["min_years"]) if job["min_years"] else 1
    edu_s = min(1, profile["education"] / job["education"]) if job["education"] else 1
    parts = dict(required=req_s, preferred=pref_s, experience=exp_s, education=edu_s)
    total = round(100*sum(W[k]*v for k, v in parts.items()))
    allrows = req + pref
    partial = [{"skill": n, "via": sorted(REL.get(n, set()) & have)} for n,c,s in allrows if s=="partial"]
    missing = [n for n,c,s in allrows if s=="missing"]
    matched = [n for n,c,s in allrows if s=="matched"]
    eligible = total >= job["threshold"]
    why = (f"Your score is {total}%: required skills count for 60% ({round(req_s*100)}% covered), preferred skills 15% "
           f"({round(pref_s*100)}%), experience 15% ({profile['years']} of {job['min_years']} yrs asked), "
           f"education 10% ({EDU_NAME[profile['education']]} vs {EDU_NAME[job['education']]} asked). "
           f"Related skills earn half credit.")

    path = sorted(({"skill": m, "trend": SKILLS[m]["t"], "demand": SKILLS[m]["d"],
                    "required": m in job["required"], "sdgs": SKILLS[m]["s"]} for m in missing),
                    key=lambda x: (not x["required"], -x["demand"]))
    return dict(job_id=job["id"], score=total, threshold=job["threshold"], eligible=eligible,
                shortfall=0 if eligible else job["threshold"] - total,
                breakdown={k:dict(score=round(v*100), weight=int(W[k]*100)) for k, v in parts.items()},
                matched=matched, partial=partial, missing=missing, explanation=why, pathway=path)

CVS, APPS = {}, []

def dashboard(profile, results):
    jobs = {j["id"]: j for j in JOBS}
    top = sorted(results, key=lambda r: -r["score"])[:5]
    sdg = {}
    for r in top:
        for g in jobs[r["job_id"]]["sdgs"]: 
            sdg[g] = sdg.get(g,0) + r["score"]
    gaps = {}
    for r in results:
        for p in r["pathway"]: 
            gaps[p["skill"]] = gaps.get(p["skill"], 0) + 1
    gap_list = sorted(gaps, key=lambda s: (-gaps[s], -SKILLS[s]["d"]))[:6]
    trend = {}
    for s in profile["skills"]:
        trend[SKILLS[s]["t"]] = trend.get(SKILLS[s]["t"], 0)+ 1
    return dict(
        top = [r["job_id"] for r in top],
        skills = [dict(name=s, category=SKILLS[s]["c"], trend=SKILLS[s]["t"], demand=SKILLS[s]["d"]) for s in profile["skills"]],
        trend=trend, 
        avg_demand = round(sum(SKILLS[s]["d"] for s in profile["skills"]) / max(1, len(profile["skills"]))),
        sdgs = [dict(id=g, name=SDG[g], weight=round(w / max(sdg.values())*100)) for g,w in sorted(sdg.items(), key=lambda x: -x[1])],
        gaps = [dict(skill=s, jobs=gaps[s], trend=SKILLS[s]["t"], demand=SKILLS[s]["d"]) for s in gap_list],
        eligible_count = sum(r["eligible"] for r in results)
    )

class H(BaseHTTPRequestHandler):
    def send(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionError:
            pass

    def body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_GET(self):
        path=self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/jobs": 
            return self.send(200, dict(jobs=JOBS, sdgs=SDG, skills={k:v["t"] for k,v in SKILLS.items()}))
        if path == "/job_search.html":
            return self.send(200, (HERE / "job_search.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/matches":  # lets other pages reload the analysed CV
            cv_id = parse_qs(urlparse(self.path).query).get("cv_id", [""])[0]
            prof = CVS.get(cv_id)
            if not prof: 
                return self.send(404, dict(error="CV not found"))
            results = [score_job(prof, j) for j in JOBS]
            return self.send(200, dict(cv_id=cv_id, profile=prof, results=results, dashboard=dashboard(prof, results)))
        if path == "/api/sample":
            return self.send(200, dict(text=(HERE / "sample_cv.txt").read_text(encoding="utf8")))
        self.send(404, dict(error = "Not found"))

    def do_POST(self):
        try:
            if self.path == "/api/analyze":
                raw = self.body()
                fn = self.headers.get("X-Filename", "")
                text = raw.decode("utf8", "ignore") if self.headers.get("X-Source") == "text" else read_cv(raw, fn)
                if len(text.strip()) < 40:
                    return self.send(422, dict(error="Could not read enough text from this CV. Paste the text instead."))
                prof = profile(text)
                if not prof["skills"]:
                    return self.send(422, dict(error="No known skills found. Add a skills section and try again."))
                results = [score_job(prof, j) for j in JOBS]
                cv_id = uuid.uuid4().hex
                CVS[cv_id]=prof
                return self.send(200, dict(cv_id=cv_id, profile=prof, results=results, dashboard=dashboard(prof, results)))
            if self.path == "/api/apply":
                d = json.loads(self.body() or b"{}")
                prof = CVS.get(d.get("cv_id"))
                job = next((j for j in JOBS if j["id"] == d.get("job_id")), None)
                if not prof or not job:
                    return self.send(400, dict(error="Upload your CV first."))
                r = score_job(prof, job) # re-checked on the server so the gate can't be bypassed
                if not r["eligible"]:
                    return self.send(403, dict(error=f"Match is {r['score']}%. This role needs {job['threshold']}% to apply.", score=r["score"]))
                APPS.append(dict(cv_id=d["cv_id"], job_id=job["id"], name=d.get("name", ""), email=d.get("email", ""), score=r["score"]))
                return self.send(200, dict(ok=True, message = f"Application sent to {job['company']} with a {r['score']}% match."))
            self.send(404, dict(error="Not found"))
        except ValueError as e:
            self.send(422, dict(error=str(e)))
        except Exception as e:
            self.send(500, dict(error=f"Server error: {e}"))

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    print("WinHire running at http://localhost:8000 (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()