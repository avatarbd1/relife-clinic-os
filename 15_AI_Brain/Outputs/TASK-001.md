# Relife Clinic OS – Documentation Standards  
**Version:** 1.0 – 26‑July‑2026  
**Author:** Relife Clinic OS Documentation Team  
**Status:** Final (Approved by the Technical Steering Committee)

---

## 1️⃣ Purpose  
এই ডকুমেন্টের উদ্দেশ্য হলো Relife Clinic OS‑এর সকল টেকনিক্যাল ডকুমেন্টেশনকে একসাথে, সুশৃঙ্খল ও সহজে রক্ষণাবেক্ষণযোগ্য করা।  
It defines the **process**, **format**, and **templates** that every developer, QA, and product owner must follow when creating or updating documentation.

> *Why it matters:*  
> • Consistent look & feel enhances developer productivity.  
> • Easy onboarding for new hires.  
> • Compliance with regulatory requirements (HIPAA, GDPR, ISO 27001).

---

## 2️⃣ Scope  
- All **software artefacts**: APIs, SDKs, micro‑services, configuration files, UI components, CI/CD pipelines, and infra‑as‑code.  
- All **non‑software artefacts** that influence system behaviour: data models, security policies, user‑stories, and test plans.  
- Documentation generated automatically (e.g., Swagger/OpenAPI, Javadoc) **must** be integrated into the “Document Hub” and follow the naming/format guidelines below.  

*Excludes:*  
- Marketing/PR collateral (handled separately).  
- Training videos (managed by the Training & Enablement team).

---

## 3️⃣ Document Types & Classification  

| Type | Description | Example | Format |
|------|-------------|---------|--------|
| **Requirements** | Business & functional requirements | `REQ‑2026‑001` | Markdown + PDF |
| **Design** | System architecture, component diagram, data model | `DES‑API‑Auth` | Markdown, UML (PlantUML) |
| **Implementation** | Code‑level docs, module specs | `IMP‑Payments‑Gateway` | Markdown, Javadoc/Swagger |
| **Deployment** | CI/CD pipelines, environment setup | `DEP‑CI‑GitHubActions` | Markdown, YAML |
| **User** | End‑user manuals, help docs | `USR‑Patient‑Portal` | Markdown, HTML |
| **Release** | Changelog, version notes | `REL‑2026‑07` | Markdown |
| **Operational** | Incident, SRE runbooks | `OPS‑Incident‑SLA` | Markdown, PDF |
| **Governance** | Policy, compliance, audit | `POL‑Data‑Retention` | Markdown |

> **Naming convention**  
> ```<TYPE>‑<SHORTCODE>[-<IDENTIFIER>].md```  
> *e.g.* `IMP‑Auth‑Token.md`

---

## 4️⃣ Content Guidelines  

| Section | What to Include | How to Write |
|---------|----------------|--------------|
| **Title** | Clear, concise, includes type & ID | `IMP‑Auth‑Token – Token Service Implementation` |
| **Purpose** | Why the doc exists | Use present tense, brief paragraph |
| **Audience** | Who should read | List roles (Dev, QA, Ops) |
| **Scope** | What the doc covers | Avoid assumptions |
| **Prerequisites** | Dependencies, knowledge needed | List software versions, external APIs |
| **Definitions & Acronyms** | Jargon explanation | Table format |
| **Content** | Detailed explanation | Sub‑headings, code blocks, diagrams |
| **References** | Related docs, external links | `see: [API Design Guidelines]` |
| **Revision History** | Change log | Table with date, version, author, summary |

> *Formatting Tips*  
> • Use Markdown **backticks** for inline code (`token`).  
> • Use fenced code blocks with language specifier.  
> • Include `![Diagram](diagram.png)` for visual aids.  

---

## 5️⃣ Formatting & Style  

| Rule | Description |
|------|-------------|
| **Language** | All technical prose in **English**. Bengali terms only in the glossary or when local context is unavoidable. |
| **Font** | Monospaced for code (`Courier New` or similar). |
| **Linking** | Use relative links within the repo (`./Design/DB‑Schema.md`). |
| **Code Blocks** | Syntax‑highlighted for readability. |
| **Diagrams** | PlantUML, Mermaid, or SVGs – stored in a `diagrams/` folder. |
| **Tables** | Use GitHub‑Flavored Markdown tables; keep width ≤ 100 characters. |
| **Version Numbers** | Semantic (`MAJOR.MINOR.PATCH`), e.g., `1.3.0`. |
| **Date Format** | ISO‑8601 (`YYYY-MM-DD`). |

---

## 6️⃣ Templates  

All new docs should start from the appropriate **Markdown template**.  
The repository `templates/` contains:

| Template | Purpose | Path |
|----------|---------|------|
| `requirements.md` | Requirements spec | `templates/requirements.md` |
| `design.md` | System design | `templates/design.md` |
| `implementation.md` | Code‑level docs | `templates/implementation.md` |
| `deployment.md` | CI/CD & infra | `templates/deployment.md` |
| `user_manual.md` | End‑user guide | `templates/user_manual.md` |
| `release_notes.md` | Changelog | `templates/release_notes.md` |

> *How to use:*  
> ```bash  
> cp templates/implementation.md docs/IMP‑Auth‑Token.md  
> ```

---

## 7️⃣ Version Control & Repository Structure  

```
/docs
│
├── /requirements
├── /design
├── /implementation
├── /deployment
├── /user_manual
├── /release_notes
└── /templates
```

- **Git Branching**:  
  - `main` – stable docs, merged after review.  
  - `docs/feature‑<ID>` – work‑in‑progress.  

- **Tagging**:  
  - Tag the repo with the release version (`v1.3.0`).  

- **Pull Requests**:  
  - Must include link to JIRA ticket.  
  - Minimum 1 review approval.  

---

## 8️⃣ Review & Approval  

1. **Author** submits a PR.  
2. **Peer Reviewer** (≥ 2 developers) checks for:  
   - Completeness.  
   - Accuracy.  
   - Adherence to style guide.  
3. **Documentation Lead** signs off.  
4. **Merge** into `main`.  

> *Automated Checks*:  
> - **Spell‑check** (cspell).  
> - **Link checker** (`markdown-link-check`).  
> - **Diagram lint** (Mermaid CLI).  

---

## 9️⃣ Tooling  

| Tool | Purpose | Setup |
|------|---------|-------|
| **GitHub** | Version control, PR workflow | Repo `relife/relife-clinic-os` |
| **MkDocs** | Static site generation (Documentation Hub) | `mkdocs.yml` config |
| **PlantUML** | UML diagrams | `plantuml.jar` or online renderer |
| **Mermaid** | Live diagram rendering | Include `cdn.jsdelivr.net` in MkDocs |
| **Javadoc / Swagger** | Auto‑generated API docs | Integrated into CI |
| **cspell** | Spell‑checking | `cspell.json` config |
| **markdown-link-check** | Broken link detection | `.github/workflows/link-check.yml` |
| **Prettier** | Markdown formatting | `prettierrc` |

> *CI Integration* – All docs go through `docs-ci.yml` pipeline that runs linting and link checks before merging.

---

## 🔟 Glossary  

| Term | Bengali | English Definition |
|------|---------|--------------------|
| **API** | অ্যাপ্লিকেশন প্রোগ্রামিং ইন্টারফেস | Interface for software interaction |
| **CI/CD** | কনটিনিউয়াস ইন্টিগ্রেশন / ডিপ্লয়মেন্ট | Automation of build, test, and deployment |
| **SRE** | সাইট রিলায়াবিলিটি ইঞ্জিনিয়ারিং | Reliability engineering for production |
| **UML** | ইউনিফাইড মডেলিং ল্যাঙ্গুয়েজ | Modeling language for software |
| **Semantic Versioning** | সেমান্টিক ভার্শনিং | `MAJOR.MINOR.PATCH` scheme |