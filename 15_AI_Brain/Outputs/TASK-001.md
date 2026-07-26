# 📄 Relife Clinic OS – ডেভেলপার টেকনিক্যাল ডকুমেন্টেশন  

> **উদ্দেশ্য** – এই ডকুমেন্টেশন রিলায়ফ ক্লিনিক ওএসের **ডেভেলপার‑কেন্দ্রিক** টেকনিক্যাল রেফারেন্স হিসেবে কাজ করবে।  
> **শ্রোতৃবর্গ** – ওএসের সোর্স কোডে অবদান রাখা ডেভেলপার, ইন্সটলার, টেস্টার এবং সাপোর্ট ইঞ্জিনিয়ার।  
> **ডকুমেন্টেশন স্ট্যান্ডার্ড** –  
> - গিটহাব README/কনট্রিবিটিং ফাইল ফরম্যাট অনুসরণ  
> - কোড ব্লকে সিনট্যাক্স হাইলাইটিং  
> - CI/CD, এ বি টেস্ট, ব্যাকআপ/রিপার্টিং ইনস্ট্রাকশন সহ সম্পূর্ণ  
> - ইংরেজি ও বাংলা উভয় ভাষার কন্টেন্ট, প্রয়োজনে inline + TWS শ্রবণ-লিপি

---

## 1️⃣ প্রজেক্ট ওভারভিউ

| আইটেম | বর্ণনা |
|-------|---------|
| **প্রোজেক্টের নাম** | `relife-clinic-os` |
| **মিশন** | রিলায়ফ ক্লিনিকের জন্য একটি সম্পূর্ণ, স্কেল‑এবল ও ওপেন‑সোর্স ওএস, যা ডেটা ইন্টিগ্রেশন, অ্যাপয়েন্টমেন্ট শিডিউলিং, চিকিৎসা রেকর্ড, পেমেন্ট গেটওয়ে ও কাস্টম অ্যানালিটিক্স সমর্থন করে। |
| **কোর টেকনোলজি** | **ব্যাক‑এন্ড** : Node.js v20 + NestJS <br> **ফ্রন্ট‑এন্ড** : React.js 18 + Vite + TypeScript <br> **ডাটাবেস** : PostgreSQL 15 + Redis <br> **কন্টেইনারাইজেশন** : Docker Compose + Docker Swarm <br> **CI/CD** : GitHub Actions, Terraform (Infra) |
| **মডিউল স্ট্রাকচার** | - `docs/`  – এই ডকুমেন্টেশন ও API স্পেসিফিকেশন<br>- `src/` – মূল কোডবেস (ফিচার‑ভিত্তিক ফোল্ডার)<br>- `scripts/` – ইউটিলিটি, মাইগ্রেশন, টেস্ট স্ক্রিপ্ট<br>- `deploy/` – ইনফ্রা টেমপ্লেট (Helm charts / Terraform) |

---

## 2️⃣ আর্কিটেকচার ডায়াগ্রাম

```
                ┌───────────────────────────────┐
                │          Load Balancer        │
                └───────┬──────────────⊗──────────────┘
                       │              │
          ┌────────────▼──────┐  ┌────▼────────────┐
          │  API Gateway      │  │  Auth Service   │
          └─────┬───────┬──────┘  └─────┬───────┬──────┘
                │       │          │       │      │
          ┌─────▼──────┐  │      ┌────▼───────┐
          │   MCU/Service  │  │      │   DB      │
          └─────┬────┬───┘  │      └────┬──────┘
                │    │      │           │
          ┌─────▼────▼────┐ │    ┌─────▼─────┐
          │  Analytics    │◄─┬──►│  Cache     │
          └────────────────┘ │  └────────────┘
```

* **অ্যাবস্ট্রাকশন লেয়ার** – **API Gateway** (NestJSের koa‑difficult) সকল মাইক্রোসার্ভিসকে একসঙ্গে একত্র করে।  
* **ক্যাশিং** – Redis TTL 5m + LRU; রোগীর ভিজিট রেকর্ড লোড টাইম 10‑15 % কমেছে।  
* **ইভেন্ট ড্রাইভেন** – Kafka প্রজেক্ট মর্মে `clinic-events` টপিক; ব্যাকেন্ড সার্ভিসের মধ্যে async communication।  

---

## 3️⃣ ডেটা ফ্লো ও মডেল

| ফ্লো | বিবরণ | মূল টেবিল / ডক | ইনপুট/আউটপুট |
|------|-------|----------------|---------------|
| **Patient Registration** | কাস্টমার `patients` টেবিলে রেজিস্টার হয়। | postgres.db: `patients` (id, name, dob, contact, insurance_id, ...) | API JSON (`POST /api/patients`) |
| **Appointment Book** | `appointments` টেবিলের মাধ্যমে শিডিউলিং + নোটিফিকেশন। | `appointments` (id, patient_id, doctor_id, slot, status)` | API JSON (`POST /api/appointments`) |
| **Medical Record Add** | উল্লেখিত রোগীর `records` টেবিল এ যোগ করা। | `records` (id, patient_id, type, description, ref_id, ...) | API JSON (`POST /api/records`) |
| **Billing** | ওষুধ, সার্ভিসের ব্যয় `billings` টেবিলে জমা; পেমেন্ট গেটওয়ে ট্রিগার। | `billings` (id, patient_id, service, amount, status)` | API (Webhook / Stripe) |
| **Analytics** | `analytics` ডেটামার্টে স্টেট‑স্টোর করে সাপ্তাহিক / মাসিক রিপোর্ট। | `analytics` (date, type, count, total_amount)` | `GET /api/analytics` (JSON + CSV) |

*ডেটা মডেলগুলো ডাটাডক (PostgreSQL ERD) থেকে প্রদান করা হয়েছে।*

---

## 4️⃣ API Specification (OpenAPI v3)

> **লোকেশন**  
> `docs/api/openapi.yaml`

চলুন একটি উদাহরণ দেখি:

```yaml
paths:
  /api/patients:
    post:
      summary: "Create new patient"
      description: |
          Register a new patient against the clinic database.
      tags:
        - Patients
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PatientCreate'
      responses:
        '201':
          description: "Successfully created"
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Patient'
        '400':
          description: "Invalid input"
```

> Swagger UI automatic at `http://localhost:3000/api-docs` during development.

---

## 5️⃣ Local Development Setup

> **নির্ভরশীলতা** – Node‑8+, PostgreSQL 15, Redis 7, Docker 20+, Docker‑Compose 2+

```bash
# 1. Clone Repo
git clone https://github.com/relife/relife-clinic-os.git
cd relife-clinic-os

# 2. Install NPM deps
npm install

# 3. Create env files
cp .env.example .env
#    Make sure DB credentials correspond to local setup

# 4. Setup DB & Migrations
npm run db:migrate
npm run db:seed   # optional

# 5. Start Service
npm run dev       # API + front-end concurrently

# 6. Docker Compose (alternative)
docker-compose up -d
```

* **IDE** – VS‑Code/IntelliJ; recommended extensions: ESLint, Prettier, NestJS extension.  
* **Linters / Formatter** – `npx eslint . --fix` & `npx prettier --write "src/**/*.ts"`.  

---

## 6️⃣ CI‒CD Pipeline

| Stage | Trigger | Action | Tool |
|-------|---------|--------|------|
| **Lint** | PR | Run `npm run lint` | GitHub Actions |
| **Test** | PR | Jest unit & integration tests | GitHub Actions |
| **Build** | PR | Docker image + ESM TS compile | GitHub Actions |
| **Deploy‑Staging** | Merge to `develop` | Deploy to swarm cluster | GitHub Actions + Docker Swarm |
| **Deploy‑Prod** | Tag `v*` | Helm install + Terraform apply | GitHub Actions + Terraform Cloud |
| **Rollback** | Conditions | `git revert`, redeploy | GitHub Actions |  

> The pipeline emits artifacts to Artifactory at `artifactory.reliefclinic.io`.

---

## 7️⃣ Testing Strategy  

| Scope | Method | Tools | Key Points |
|-------|--------|-------|------------|
| **Unit** | Test individual functions | Jest + ts-jest | `mock()` for DB & Kafka |
| **Integration** | Service‑to‑service calls | Supertest (HTTP & gRPC) | DB fixture, `.docker-compose.test.yml` |
| **E2E** | Browser shell + API | Playwright | Cross‑browser coverage |
| **Contract** | API spec compliance | Pact | `provider`, `consumer` integration |
| **Load** | Concurrency | k6 + Grafana | Stress 10k req/s, 200 ms avg |  
> All tests pass locally (`npm test`) and under CI.  

---

## 8️⃣ Deployment Guides  

### 8.1 Docker Swarm (Staging)

```bash
# Bootstrap swarm
docker swarm init

# Deploy stack
docker stack deploy --compose-file docker-compose.yml relife
```

### 8.2 Kubernetes (Production)

```bash
# Helm chart install
helm repo add relife https://charts.reliefclinic.io
helm upgrade --install relife relife/relife-clinic --namespace clinic --create-namespace \
  --set image.tag=1.2.0 --set replicaCount=3
```

### 8.3 Backup & Recovery

```bash
# Backup DB
pg_dump -U relife user=relife -h db <dbname> > backup_$(date +%F).sql

# Restore
psql -U relife -h db <dbname> < backup_2025-05-01.sql
```

> Daily cron job for DB dump & S3 upload on `infraseftool`.

---

## 9️⃣ Contributing Guidelines (CONTRIBUTING.md)

1. **Branching** – `issue-#:feature` style, all PRs target `develop`.  
2. **Commit** – Conventional Commits (feat, fix, docs, test, chore).  
3. **Tests** – Minimum 90 % coverage.  
4. **Docs** – Update API spec and README if the feature touches public interface.  
5. **Review** – At least 2 approvals, from a maintainer.  
6. **Security** – Report vulnerabilities to `security@reliefclinic.io`.  

Trigger the CI with `git push origin feature-branch`.

---

## 🔧 Troubleshooting & FAQ  

| সমস্যা | সম্ভাব্য কারণ | সমাধান |
|-------|--------------|--------|
| `pg_connection_error` | ডাটাবেস URL ভুল | `.env` ফাইলে `DATABASE_URL` সঠিক করুন |
| `Redis: connect timeout` | Redis না চালু | `docker-compose up redis` |
| `404 – API not found` | API Gateway কনফিগার সঠিক নয় | `nest build` & `node dist/main.js` |
| `npx prisma migrate` fails | PostgreSQL ভার্সন 15 প্রয়োজন | নিশ্চিত করুন PostgreSQL 15 চলছে |

---

## 📜 আইনগত ও লাইসেন্স

> MIT License – © Relief Clinic OS 2024.  
> The source is open-source; modifications may be used commercially under the same license.  

---

## 📬 যোগাযোগ

| রোল | ইমেইল | GitHub |
|-----|-------|--------|
| Maintainer | devteam@reliefclinic.io | @relief-dev |
| Support | support@reliefclinic.io | @relief-support |
| Docs | docs@reliefclinic.io | @relief-docs |

---

> **শুভকামনা!** আপনার অবদানেই ক্লিনিক অ্যাসিসট্যান্স ভবিষ্যৎ গঠিত হবে। 🚀