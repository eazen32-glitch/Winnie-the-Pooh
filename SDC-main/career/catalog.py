"""Small, reviewable career catalogue for the Domain 1 proof of concept.

Roles are anchored to O*NET occupations. Skill requirements, SDG links and
learning-hour budgets are our editorial assumptions, not O*NET forecasts or
provider-certified course durations. Resource links point to real free learning
material; a provider may require a free account. No personal data is included.
"""

_GOALS = [
    ("No Poverty", "Build accessible pathways to income and economic participation."),
    ("Zero Hunger", "Apply skills to resilient agriculture and food systems."),
    ("Good Health and Well-being", "Support safe, accessible health and well-being services."),
    ("Quality Education", "Make continuing education and practical skills more accessible."),
    ("Gender Equality", "Promote equal access to skills and career opportunities."),
    ("Clean Water and Sanitation", "Improve measurement and management of water resources."),
    ("Affordable and Clean Energy", "Support effective, accessible clean-energy systems."),
    ("Decent Work and Economic Growth", "Support productive work and worker-led reskilling."),
    ("Industry, Innovation and Infrastructure", "Build reliable technology and responsible innovation."),
    ("Reduced Inequalities", "Reduce barriers to opportunity and inclusive services."),
    ("Sustainable Cities and Communities", "Support resilient and inclusive communities."),
    ("Responsible Consumption and Production", "Measure and reduce waste in operations and supply chains."),
    ("Climate Action", "Use evidence and practical capabilities to respond to climate change."),
    ("Life Below Water", "Support protection of marine ecosystems through evidence and action."),
    ("Life on Land", "Support conservation and responsible land management."),
    ("Peace, Justice and Strong Institutions", "Promote trustworthy systems, accountability and information security."),
    ("Partnerships for the Goals", "Share knowledge and collaborate across organisations."),
]
SDGS = [
    {"id": number, "title": title, "description": description,
     "url": f"https://sdgs.un.org/goals/goal{number}"}
    for number, (title, description) in enumerate(_GOALS, start=1)
]


def _resource(title, provider, url, hours):
    return {"title": title, "provider": provider, "url": url, "hours": hours}


def _skill(identifier, name, description, aliases, sdgs, resources):
    return {"id": identifier, "name": name, "description": description,
            "aliases": aliases, "sdgs": sdgs, "resources": resources}


SKILLS = [
    _skill("ai-literacy", "AI literacy", "Understand AI capabilities, limits and responsible use at work.",
           ["artificial intelligence", "AI literacy", "generative AI", "gen AI", "LLM", "large language model"], [4, 8, 9], [
               _resource("AI for Beginners — introductory lessons", "Microsoft", "https://github.com/microsoft/AI-For-Beginners", 4)]),
    _skill("python", "Python", "Write readable programs to analyse data and automate repeatable tasks.",
           ["Python", "pandas", "NumPy"], [4, 8, 9], [
               _resource("Python", "Kaggle Learn", "https://www.kaggle.com/learn/python", 8)]),
    _skill("sql", "SQL", "Query structured information and audit the evidence behind decisions.",
           ["SQL", "PostgreSQL", "MySQL", "T-SQL", "Snowflake"], [8, 9, 16], [
               _resource("Intro to SQL", "Kaggle Learn", "https://www.kaggle.com/learn/intro-to-sql", 6)]),
    _skill("excel", "Spreadsheets", "Organise, inspect and communicate operational information.",
           ["Excel", "spreadsheet", "Google Sheets"], [4, 8], [
               _resource("Excel help and learning", "Microsoft Support", "https://support.microsoft.com/en-us/excel", 5)]),
    _skill("data-analysis", "Data analysis", "Turn data into defensible insights and evaluate their limitations.",
           ["data analysis", "data analyst", "data analytics", "exploratory data", "analytics"], [8, 9, 12], [
               _resource("Pandas", "Kaggle Learn", "https://www.kaggle.com/learn/pandas", 8)]),
    _skill("statistics", "Statistics", "Reason about uncertainty, sampling and evidence before making claims.",
           ["statistics", "statistical", "probability", "A/B testing", "hypothesis testing"], [4, 9, 16], [
               _resource("Statistics and probability", "Khan Academy", "https://www.khanacademy.org/math/statistics-probability", 10)]),
    _skill("data-visualisation", "Data visualisation", "Make patterns and limitations in evidence understandable.",
           ["data visualization", "data visualisation", "Power BI", "Tableau", "dashboard"], [4, 8, 16], [
               _resource("Data Visualization", "Kaggle Learn", "https://www.kaggle.com/learn/data-visualization", 6)]),
    _skill("machine-learning", "Machine learning", "Train and evaluate predictive models with appropriate validation.",
           ["machine learning", "deep learning", "PyTorch", "TensorFlow", "scikit-learn", "model training", "transformers"], [9, 12, 13], [
               _resource("Intro to Machine Learning", "Kaggle Learn", "https://www.kaggle.com/learn/intro-to-machine-learning", 10)]),
    _skill("prompting", "Prompt design", "Specify and evaluate AI-assisted tasks without trusting generated answers blindly.",
           ["prompt engineering", "prompt design", "prompting", "prompt tuning"], [4, 8, 9], [
               _resource("Introduction to prompt engineering", "Microsoft Learn", "https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/prompt-engineering", 4)]),
    _skill("ai-ethics", "Responsible AI", "Identify fairness, privacy and reliability risks in AI-enabled services.",
           ["responsible AI", "AI ethics", "AI governance", "model fairness", "algorithmic bias"], [5, 10, 16], [
               _resource("Responsible AI principles and approach", "Microsoft", "https://www.microsoft.com/en-us/ai/principles-and-approach", 4)]),
    _skill("cloud", "Cloud fundamentals", "Understand shared infrastructure, cost and secure cloud delivery.",
           ["cloud", "Azure", "AWS", "GCP", "Google Cloud", "Kubernetes"], [8, 9], [
               _resource("Describe cloud concepts", "Microsoft Learn", "https://learn.microsoft.com/en-us/training/paths/microsoft-azure-fundamentals-describe-cloud-concepts/", 6)]),
    _skill("cybersecurity", "Cybersecurity", "Protect systems and information so digital services remain trustworthy.",
           ["cybersecurity", "cyber security", "information security", "security analyst", "threat detection", "SOC analyst"], [9, 16], [
               _resource("Cybersecurity learning", "IBM SkillsBuild", "https://skillsbuild.org/students/course-catalog/cybersecurity", 8)]),
    _skill("communication", "Communication", "Explain decisions clearly and work constructively with other people.",
           ["communication", "stakeholder", "presentation", "collaboration", "interpersonal"], [4, 8, 17], [
               _resource("Professional skills learning", "IBM SkillsBuild", "https://skillsbuild.org/students/course-catalog/professional-skills", 5)]),
    _skill("project-management", "Project management", "Plan, coordinate and evaluate realistic work with a team.",
           ["project management", "project manager", "Agile", "Scrum", "project coordination"], [8, 9, 17], [
               _resource("Project management learning", "IBM SkillsBuild", "https://skillsbuild.org/students/course-catalog/project-management", 8)]),
    _skill("sustainability", "Sustainability literacy", "Connect operational decisions with environmental and social impacts.",
           ["sustainability", "sustainable", "ESG", "climate", "carbon", "environmental"], [7, 12, 13], [
               _resource("UN SDG:Learn course catalogue", "UN SDG:Learn", "https://www.unsdglearn.org/", 6)]),
    _skill("automation", "Workflow automation", "Design auditable workflows that remove repetitive effort while retaining human oversight.",
           ["automation", "automate", "automated", "workflow", "Power Automate", "RPA"], [8, 9, 12], [
               _resource("Get started with Power Automate", "Microsoft Learn", "https://learn.microsoft.com/en-us/training/modules/get-started-flows/", 6)]),
    _skill("software-development", "Software development", "Build, test and maintain useful software with version control.",
           ["software engineer", "software developer", "software development", "programming", "Git", "JavaScript", "Java", "C++"], [8, 9], [
               _resource("Web Development for Beginners — selected lessons", "Microsoft", "https://github.com/microsoft/Web-Dev-For-Beginners", 8)]),
    _skill("learning-design", "Learning design", "Create inclusive, practical learning experiences and check understanding.",
           ["instructional design", "learning design", "training and development", "e-learning", "curriculum", "learning development"], [4, 8, 10], [
               _resource("Training and education resources", "Microsoft Educator Center", "https://learn.microsoft.com/en-us/training/educator-center/", 6)]),
]


def _role(identifier, title, summary, requirements, interests, sdgs, code, impact, aliases, exposure):
    return {"id": identifier, "title": title, "summary": summary,
            "skills": [{"id": skill, "weight": weight} for skill, weight in requirements],
            "interests": interests, "sdgs": sdgs,
            "source_url": f"https://www.onetonline.org/link/summary/{code}",
            "sdg_impact": impact, "aliases": aliases, "ai_exposure": exposure}


ROLES = [
    _role("business-intelligence-analyst", "Business Intelligence Analyst",
          "Use data and dashboards to help people make better operational decisions.",
          [("excel", 1), ("sql", 3), ("data-analysis", 3), ("data-visualisation", 2), ("communication", 2), ("ai-literacy", 1)],
          ["business", "analytics", "data", "dashboards", "decisions", "operations"], [8, 9, 12], "15-2051.01",
          "Measure operational waste and explain opportunities for more productive, responsible work (SDGs 8 and 12).",
          ["business intelligence", "BI analyst", "data analyst", "analytics analyst", "business analyst"], 0.65),
    _role("data-scientist", "Data Scientist",
          "Analyse complex data, test assumptions and develop evaluated predictive models.",
          [("python", 3), ("sql", 2), ("statistics", 3), ("data-analysis", 2), ("machine-learning", 3), ("ai-ethics", 2), ("communication", 1)],
          ["data", "research", "machine learning", "AI", "statistics", "prediction", "science"], [9, 12, 13], "15-2051.00",
          "Apply validated models to resource efficiency or climate questions; impact depends on the project and data (SDGs 12 and 13).",
          ["data scientist", "data science", "machine learning engineer", "ML engineer", "AI engineer", "applied scientist"], 0.85),
    _role("software-developer", "Software Developer",
          "Design, test and maintain software that people can use reliably.",
          [("software-development", 3), ("python", 2), ("cloud", 2), ("automation", 2), ("ai-literacy", 1), ("communication", 1), ("ai-ethics", 1)],
          ["coding", "software", "building", "applications", "automation", "technology", "engineering"], [8, 9], "15-1252.00",
          "Build accessible and dependable digital tools that improve work and infrastructure (SDGs 8 and 9).",
          ["software engineer", "software developer", "backend engineer", "frontend engineer", "full stack", "full-stack", "application developer"], 0.80),
    _role("information-security-analyst", "Information Security Analyst",
          "Monitor risks and protect the systems and information people depend on.",
          [("cybersecurity", 3), ("cloud", 2), ("python", 1), ("data-analysis", 1), ("ai-ethics", 1), ("communication", 2)],
          ["security", "privacy", "risk", "investigation", "networks", "trust"], [9, 16], "15-1212.00",
          "Protect essential infrastructure and confidential information to support trustworthy institutions (SDGs 9 and 16).",
          ["security analyst", "cybersecurity analyst", "information security", "cyber security", "SOC analyst", "security engineer"], 0.55),
    _role("sustainability-specialist", "Sustainability Specialist",
          "Evaluate organisational practices and coordinate practical sustainability improvements.",
          [("sustainability", 3), ("data-analysis", 2), ("excel", 2), ("data-visualisation", 1), ("project-management", 2), ("communication", 2), ("ai-literacy", 1)],
          ["sustainability", "environment", "climate", "ESG", "impact", "energy", "community"], [7, 12, 13], "13-1199.05",
          "Track resource use and help organisations implement measurable environmental improvements (SDGs 7, 12 and 13).",
          ["sustainability", "ESG analyst", "environmental analyst", "climate analyst", "carbon analyst"], 0.40),
    _role("learning-development-specialist", "Training and Development Specialist",
          "Help workers learn relevant capabilities and evaluate whether training works.",
          [("learning-design", 3), ("communication", 3), ("ai-literacy", 2), ("prompting", 1), ("ai-ethics", 1), ("project-management", 1)],
          ["teaching", "education", "learning", "training", "people", "coaching", "inclusion"], [4, 8, 10], "13-1151.00",
          "Design inclusive reskilling that helps more people remain in decent work (SDGs 4, 8 and 10).",
          ["training specialist", "learning and development", "instructional designer", "learning designer", "L&D specialist", "training and development"], 0.50),
    _role("project-management-specialist", "Project Management Specialist",
          "Coordinate people, requirements, schedules and risks to deliver useful work.",
          [("project-management", 3), ("communication", 3), ("excel", 1), ("data-analysis", 1), ("ai-literacy", 1), ("automation", 1)],
          ["planning", "leadership", "teams", "projects", "delivery", "coordination", "business"], [8, 9, 17], "13-1082.00",
          "Coordinate responsible innovation and partnerships that turn plans into effective work (SDGs 8, 9 and 17).",
          ["project manager", "project coordinator", "program manager", "programme manager", "project management"], 0.45),
    _role("computer-systems-analyst", "Computer Systems Analyst",
          "Understand business needs and improve information systems with people in the loop.",
          [("data-analysis", 2), ("software-development", 2), ("sql", 2), ("communication", 3), ("automation", 2), ("ai-literacy", 1), ("project-management", 1)],
          ["systems", "business", "process", "technology", "problem solving", "automation", "requirements"], [8, 9, 12], "15-1211.00",
          "Improve organisational systems to reduce repetitive work and inefficient resource use (SDGs 8, 9 and 12).",
          ["systems analyst", "system analyst", "business systems analyst", "IT analyst", "technology analyst"], 0.60),
]

PROFILES = [
    {"id": "working-analyst", "label": "Operations analyst · synthetic demo",
     "skills": ["excel", "data-analysis", "communication", "project-management"],
     "interests": "I enjoy solving business problems with data and making operations more sustainable.", "weekly_hours": 6},
    {"id": "fresh-graduate", "label": "Computing graduate · synthetic demo",
     "skills": ["python", "software-development", "sql", "statistics"],
     "interests": "I want to build useful software and learn machine learning responsibly.", "weekly_hours": 10},
    {"id": "career-switcher", "label": "Learning coordinator · synthetic demo",
     "skills": ["communication", "learning-design", "excel"],
     "interests": "I enjoy teaching and helping people learn new skills and use AI safely at work.", "weekly_hours": 4},
]
