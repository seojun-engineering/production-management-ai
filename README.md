# Production Management AI

Python 기반 생산 KPI 계산, Rule 기반 이상 탐지,  
LLM 기반 보고를 결합한 생산관리 의사결정 지원 프로젝트입니다.

## 1. Project Overview

생산관리에서는 생산계획 달성률, 불량률, 설비 가동률과 같은 KPI를
일관된 기준으로 계산하고 이상 발생 시 우선 점검 대상을 빠르게 좁히는 것이 중요합니다.

초기에는 생산 데이터를 LLM에 직접 입력해
KPI 계산부터 이상 판단, 원인 해석까지 수행하도록 구성했습니다.

그러나 LLM이 수치를 직접 계산하면서 결과가 달라지거나
판단 근거를 추적하기 어려운 문제가 발생했습니다.

이를 개선하기 위해 역할을 다음과 같이 분리했습니다.

**Python → KPI Calculation**  
**Rule → Exception Detection**  
**LLM → Interpretation & Reporting**

---

## 2. System Architecture

```text
Production Data
      ↓
Python KPI Calculation
      ↓
Rule-based Exception Detection
      ↓
Repeated Loss / Priority Analysis
      ↓
LLM-based Report Generation
