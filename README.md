<div align="center">

# AIR-SANKHYIKI

### Real-Time Airfare Price Index (APIx) for India

**Automated airfare collection, statistical index computation, validation, and auditable price intelligence.**

<br>

**Smart India Hackathon 2026 · Problem Statement SIH26056 · MoSPI / DIID**

<br>

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square\&logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square\&logo=fastapi\&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-Dashboard-000000?style=flat-square\&logo=next.js\&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Data%20Layer-003B57?style=flat-square\&logo=sqlite\&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Collection-2EAD33?style=flat-square\&logo=playwright\&logoColor=white)

</div>

---

## ✈️ Overview

**Air-Sankhyiki** is a production-oriented prototype for developing a **Real-Time Airfare Price Index (APIx) for India** through automated collection of airline and online travel aggregator (OTA) fares.

The system collects airfare observations across a configured set of **DGCA-weighted city pairs and advance-booking windows**, processes them through cleaning and validation pipelines, and applies statistical methodologies to generate structured airfare price intelligence.

The platform is designed to support **high-frequency airfare measurement** and provide analytical inputs relevant to the augmentation of India's Consumer Price Index (CPI).

> **Project status:** Prototype / evaluation build
> **Important:** This project is not an official MoSPI statistic or government publication.

---

## Problem Statement

### Smart India Hackathon 2026 — SIH26056

**Development of a Real-time Airfare Price Index for India through Automated Web Scraping of Airline and Online Travel Aggregator Portals for Augmentation of the Consumer Price Index (CPI).**

Airfare prices can change rapidly depending on route, airline, booking window, availability, demand, and market conditions.

Air-Sankhyiki addresses this challenge by building an automated and auditable pipeline that transforms raw airfare observations into **cleaned, validated, traceable, and statistically processed price information**.

---

## Solution

The platform combines:

* Automated airfare collection
* Fare cleaning and normalization
* DGCA-weighted route coverage
* Multiple advance-booking windows
* Statistical index computation
* Availability-pressure analysis
* Data-quality validation
* Evidence preservation
* Cryptographic integrity checks
* Read-only API serving
* Interactive analytical dashboards

---

## System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                         │
│                                                             │
│       Airline Sources     OTA Sources     DGCA References   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    COLLECTION LAYER                         │
│                                                             │
│     Policy Checks → Collection → Validation → Raw Archive   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATA & INDEXING LAYER                      │
│                                                             │
│  SQLite / Parquet → Matched Models → PRISM → BCWFI → GEKS  │
│                                      │                      │
│                                      ▼                      │
│                                Kalman Nowcast               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    TRUST & VERIFICATION                     │
│                                                             │
│   SHA-256 Hashing → Evidence Ledger → Quality Gates        │
│                         → Verified Snapshot                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       SERVING LAYER                         │
│                                                             │
│                  FastAPI → Next.js Dashboard                 │
└─────────────────────────────────────────────────────────────┘
```

### End-to-End Pipeline

```text
COLLECT → ARCHIVE → VALIDATE → INDEX → VERIFY → SERVE
```

---

## Statistical Framework

Air-Sankhyiki uses multiple statistical and analytical components.

| Component          | Purpose                                                                            |
| :----------------- | :--------------------------------------------------------------------------------- |
| **PRISM**          | Separates base-fare repricing from availability pressure using observed fare rungs |
| **BCWFI**          | Applies provisional weights based on route and advance-booking-window importance   |
| **Rolling GEKS-T** | Provides a multilateral index framework designed to reduce chain drift             |
| **Kalman Nowcast** | Produces a prototype estimate of the monthly APIx level from evolving observations |

### Booking Windows

The prototype works across multiple advance-booking windows:

```text
T+1 → T+7 → T+15 → T+30 → T+45
```

The current provisional BCWFI configuration assigns:

```text
T+1   : 35%
T+7   : 25%
T+15  : 18%
T+30  : 13%
T+45  :  9%
```

The two nearest windows therefore account for **60% of the provisional weight**.

---

## Repository Structure

```text
air-sankhyiki/
│
├── apps/
│   ├── api/
│   │   ├── src/api/
│   │   └── tests/
│   │
│   └── dashboard/
│       ├── src/app/
│       ├── src/components/
│       └── src/lib/
│
├── packages/
│   └── apix_index/
│       ├── src/apix_index/
│       └── tests/
│
├── services/
│   ├── collectors/
│   │   ├── src/collectors/
│   │   └── tests/
│   │
│   └── pipeline/
│
├── data/
│   ├── deploy/
│   ├── logs/
│   ├── scripts/
│   ├── ledger.jsonl
│   ├── route_basket.yaml
│   └── route_weights.csv
│
├── scripts/
├── .github/workflows/
├── .env.example
├── DEPLOY.md
├── pyproject.toml
└── render.yaml
```

---

## Components

### `services/collectors/`

Policy-gated collection layer supporting the current Akasa and SerpAPI workflows.

Responsibilities include:

* Fare collection
* Source validation
* Retry and quota handling
* SQLite storage
* Parquet storage
* Raw-response archival
* Evidence-ledger integration

### `packages/apix_index/`

Core statistical processing package.

Includes:

* Matched-model indexing
* Rolling 14-day GEKS-T
* BCWFI weighting
* PRISM rung heuristic
* Kalman prototype
* Quality gates

### `apps/api/`

FastAPI serving layer using structured, MoSPI-style response envelopes for the prototype.

### `apps/dashboard/`

Next.js and Apache ECharts dashboard providing seven analytical views:

1. Overview
2. Routes
3. PRISM
4. Nowcast
5. Competition
6. Fair Fare
7. Trust

### `services/pipeline/`

Pipeline boundary and operational notes. Current nightly orchestration is handled through **Windows Task Scheduler / PowerShell** rather than a dedicated application-level scheduler.

---

## 📊 Audited Prototype Snapshot

**Snapshot date: 13 September 2026**

| Metric                                         |                        Value |
| :--------------------------------------------- | ---------------------------: |
| Deduplicated Fare Quotes                       |                   **27,980** |
| Collection Dates                               |                       **14** |
| Collection Period                              | **31 August – 13 September** |
| Configured DGCA City Pairs                     |                       **20** |
| Observed Carriers                              |                        **7** |
| Akasa Observations with RBD + Native Base Fare |                    **7,594** |
| Latest Collection                              |             **2,851 quotes** |
| SerpAPI Quotes in Latest Collection            |                    **1,995** |
| Akasa Quotes in Latest Collection              |                      **856** |
| Sealed Raw Captures                            |            **2,643 / 2,643** |
| Latest Prototype APIx                          |                    **85.95** |
| API Cells                                      |                       **71** |
| Matched Products                               |                    **1,122** |

> These values are derived from read-only SQLite queries and local API responses. They represent a dated prototype snapshot and **must not be interpreted as official statistics**.

---

## 🔐 Trust & Data Integrity

Air-Sankhyiki treats evidence preservation and historical integrity as first-class requirements.

### Trust Rules

1. Historical observations and evidence are append-only.
2. Active collectors must pass the policy engine.
3. Raw responses are archived before parsing.
4. Archived evidence is sealed into the evidence ledger.
5. Data passes validation and quality gates before indexing.
6. Verified snapshots are used for read-only serving.

### Collection Policy

The prototype does **not** rely on:

* Fingerprint evasion
* CAPTCHA bypass
* Unauthorized source access
* Disallowed access-control circumvention

The goal is to maintain an ethics-first and auditable collection workflow.

---

## Method Boundaries

The current prototype has explicit methodological limitations.

### BCWFI

BCWFI currently uses provisional booking-window weights:

```text
T+1   35%
T+7   25%
T+15  18%
T+30  13%
T+45   9%
```

### Akasa Availability

Akasa `availableCount` represents source-reported RBD-level availability.

PRISM uses changes in returned fare rungs as an **availability-pressure heuristic**. It is not a measurement of physical cabin utilization.

### Fare Components

SerpAPI provides offered total fares rather than a native fare-component split.

Akasa statutory and airport components are preserved. Material component movements are flagged so that airport-fee changes are not silently described as airline repricing or availability pressure.

### Competition HHI

The Competition HHI view is a **seven-day SerpAPI distinct-flight-number frequency proxy**.

It is not:

* Scheduled capacity
* DGCA seat share
* A causal measure of competition

### Kalman Nowcast

The Kalman component estimates the prototype's monthly APIx level.

It is not yet calibrated to or validated against an official CPI airfare publication.

---

## Local Setup

### Prerequisites

* Python **3.12+**
* `uv`
* Node.js and npm

### Clone

```powershell
git clone <private-repository-url>
cd air-sankhyiki
```

### Install Python dependencies

```powershell
uv sync
```

### Environment Configuration

Create the local environment file from the provided template:

```powershell
Copy-Item .env.example .env
```

Add the required local credentials and configuration.

> Never commit the real `.env` file or source credentials.

---

## Run the API

From the repository root:

```powershell
uv run --project apps/api uvicorn api.main:app --host 127.0.0.1 --port 8001
```

The API will run at:

```text
http://127.0.0.1:8001
```

---

## Run the Dashboard

Open a second terminal:

```powershell
Set-Location apps\dashboard
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:3000/
```

The dashboard communicates with the local FastAPI serving layer.

The API origin can be configured using:

```text
NEXT_PUBLIC_APIX_BASE
```

---

## Testing

### API

```powershell
uv run --project apps/api pytest apps/api/tests -q
```

### Index Engine

```powershell
uv run --project packages/apix_index pytest packages/apix_index/tests -q
```

### Collectors

```powershell
uv run --project services/collectors pytest services/collectors/tests -q
```

### Dashboard Type Check

```powershell
Set-Location apps\dashboard
npm exec -- tsc --noEmit --incremental false
```

### Production Build

```powershell
npm run build
```


---

## Technology Stack

### Backend & Data

* Python 3.12+
* FastAPI
* Uvicorn
* Pandas
* NumPy
* Pydantic
* SQLite
* Apache Parquet
* PyArrow

### Collection

* Playwright
* HTTPX
* Python-dotenv
* Source-specific adapters

### Frontend

* Next.js 15
* React 19
* TypeScript
* Tailwind CSS
* Apache ECharts

### Testing & Tooling

* uv
* pytest
* Ruff
* GitHub Actions

---

## Research & References

The methodology and design of AIR-SANKHYIKI are informed by established
research and official statistical guidance related to consumer price
measurement, dynamic pricing and multilateral index methods.

### Official Statistical Methodology

- **IMF / ILO — Consumer Price Index Manual (2020)**  
  Chapter 10: Multilateral methods and price-index construction.

- **UK Office for National Statistics (ONS)**  
  Methodological work on GEKS-Törnqvist approaches for dynamic pricing data.

- **Eurostat**  
  Guidance on multilateral methods used in price-index construction.

### Airfare Pricing & Availability Research

- **Williams — Dynamic Airfare Pricing and Seat Availability**  
  Research on the relationship between airfare prices and seat availability.

- **Alderighi et al. — Hidden Prices with Fixed Inventory**  
  Research on airline pricing and inventory effects.

- **Statistics Canada — Airfare Methodology**  
  Reference material on airfare measurement and decomposition.

- **MIT Billion Prices Project — Cavallo & Rigobon**  
  Research related to online price collection and high-frequency price measurement.

### Indian Data & Domain Sources

- **Ministry of Statistics and Programme Implementation (MoSPI)**  
  eSankhyiki and CPI-related statistical resources.

- **Directorate General of Civil Aviation (DGCA)**  
  Passenger traffic statistics, route information and aviation-sector references.

- **Air Transport Circular 02/2024**  
  Tariff-sheet and fare-related regulatory reference material.

### Methodological Context

These sources inform the project's approach to:

- CPI airfare measurement
- Multilateral price indices
- GEKS-Törnqvist methodology
- Dynamic airfare pricing
- Fare and availability dynamics
- High-frequency online price collection
- Statistical nowcasting
---

## Related Repositories

| Repository                                                        | Purpose                                                     |
| :---------------------------------------------------------------- | :---------------------------------------------------------- |
| **[landing-page](https://github.com/Air-Sankhyiki/landing-page)** | Air-Sankhyiki project landing page                          |
| **[resources](https://github.com/Air-Sankhyiki/resources)**       | Documentation, methodology and supporting project resources |

---

## Project Status

**Prototype / Development Evaluation Build**

The current implementation demonstrates an end-to-end prototype for
airfare collection, validation, statistical index computation,
verification, API serving and dashboard-based analysis.

Production government integration would require appropriate review of:

- Methodology
- Security
- Data agreements
- Source permissions
- Deployment controls
- Government integration requirements

## Team

### Tech Divaas

**Smart India Hackathon 2026**

**Problem Statement:** SIH26056
**Domain:** Smart Automation
**Category:** Software

---

<div align="center">

**AIR-SANKHYIKI**

*Data-driven airfare intelligence for India.*

</div>
