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

이를 개선하기 위해 역할을 분리했습니다.

**Python → KPI Calculation**  
**Rule → Exception Detection**  
**LLM → Interpretation & Reporting**

---

## 2. System Architecture

**Production Data**  
↓  
**Python KPI Calculation**  
↓  
**Rule-based Exception Detection**  
↓  
**Repeated Loss / Priority Analysis**  
↓  
**LLM-based Report Generation**

---

## 3. Production KPI

| KPI | Calculation |
|---|---|
| Schedule Attainment | Actual Production / Planned Production |
| Defect Rate | Defect Quantity / Actual Production |
| Equipment Utilization | Actual Operating Time / Available Operating Time |

---

## 4. Exception Rules

| KPI | Exception Rule |
|---|---|
| Schedule Attainment | < 0.95 |
| Defect Rate | > 0.03 |
| Equipment Utilization | < 0.85 |

KPI 계산과 이상 판정을 Python과 Rule로 고정하여  
LLM이 임의로 수치를 계산하거나 판단하지 않도록 설계했습니다.

---

## 5. Analysis Result

총 **20건의 생산 데이터**를 대상으로 분석했습니다.

- **8건의 Exception 탐지**
- 특정 품목에서 **동일 유형의 이상 3회 반복** 확인
- 전체 데이터를 일괄적으로 확인하는 방식에서
  **반복 Loss 및 우선 점검 대상을 먼저 확인하는 구조**로 개선

---

## 6. Role Separation

| Component | Role |
|---|---|
| Python | KPI 계산 및 데이터 처리 |
| Rule | 관리 기준 적용 및 Exception 판정 |
| LLM | 이상 현황 해석 및 보고서 생성 |

### Design Principle

**Calculation by Python → Validation by Rules → Reporting by LLM**

---

## 7. Tech Stack

- Python
- pandas
- NumPy
- OpenAI API
- Jupyter Notebook
- CSV

---

## 8. Repository Structure

production-management-ai/

- README.md
- data/
  - sample_production_data.csv
- src/
  - calculate_kpi.py
  - detect_exceptions.py
  - generate_report.py
- notebooks/
  - production_analysis.ipynb
- results/
  - exception_summary.csv
- requirements.txt
- .gitignore

---

## 9. Key Learning

이 프로젝트를 통해 LLM을 생산관리 업무에 적용할 때  
하나의 모델에 계산부터 최종 판단까지 모두 맡기는 것보다,

**정량 계산 → 관리 기준 판정 → 해석 및 보고**

단계를 분리하는 것이 결과의 **정확성, 일관성, 추적성**을 높이는 데 중요하다는 점을 확인했습니다.

향후에는 생산계획, 품질, 설비 등 기능별 분석 모듈을 추가하여  
생산 이상 발생 시 원인을 다각도로 분석하는 구조로 확장할 예정입니다.
