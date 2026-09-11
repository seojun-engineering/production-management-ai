# V2 Production Analysis Report

## 1. Objective

V2는 실제 산업 생산라인의 공개 데이터를 활용하여  
생산·가동·Downtime 데이터를 검증하고, 운영 Loss를 정량적으로 분석하기 위한 단계입니다.

V1이 synthetic dataset을 이용한 분석 구조 검증이었다면,  
V2에서는 실제 제조 데이터를 대상으로 다음 과정을 수행했습니다.

**Raw Data → Data Validation → Canonical Dataset → KPI Analysis → Operational Screening → Downtime Pareto**

---

## 2. Dataset

분석에는 실제 음료 생산라인에서 수집된 공개 제조 데이터를 사용했습니다.

분석 대상 데이터:

- Daily production records: **59**
- Hourly operation records: **265**
- Downtime events: **1,388**
- Production period: **2022-07-22 ~ 2023-02-10**

주요 데이터는 다음 세 수준으로 분리했습니다.

- Daily Production
- Hourly Operation
- Downtime Event Log

---

## 3. Data Quality Validation

실제 데이터를 그대로 분석하지 않고 테이블 간 정합성을 먼저 검증했습니다.

주요 검증 결과:

### Date Error

Downtime Event Log에서 `2022-01-13`으로 기록된 18개 이벤트를 확인했습니다.

해당 날짜에는 다른 생산 데이터가 존재하지 않았고,

- 직전 이벤트: 2023-01-11
- 문제 이벤트: 2022-01-13
- 직후 이벤트: 2023-01-16

순으로 ID가 이어졌습니다.

또한 2023-01-13에는 Daily/Hourly 생산 데이터가 존재하지만 Downtime Event만 누락되어 있었습니다.

이에 따라 18개 Event의 연도 값을  
**2022-01-13 → 2023-01-13**으로 보정했습니다.

### Metric Validation

다음 관계는 수학적으로 검증되었습니다.

**Operating Ratio = Operation Time / Monitored Time**

반면 일부 source column은 다른 테이블과 완전히 일치하지 않았기 때문에  
원본 값과 파생 지표를 분리하여 관리했습니다.

### Data Quality Flags

- Missing hourly production date: **1**
- Potential event-log gap: **1**
- Pause-definition mismatch records: **15**
- Multi-product daily records: **6**

불일치 데이터는 임의 삭제하거나 수정하지 않고  
분석용 flag로 유지했습니다.

---

## 4. Operational Screening

생산일별 운영 Loss를 비교하기 위해 다음 세 지표를 사용했습니다.

1. Operating Loss
2. Hourly-record Downtime
3. Downtime Event Frequency

각 지표를 percentile rank로 변환한 뒤 동일 가중치로 결합하여  
**Relative Screening Score**를 계산했습니다.

이 점수는 관리 기준이나 통계적 control limit가 아니라  
데이터 내에서 우선 검토할 생산일을 선별하기 위한 상대적 지표입니다.

### Top Screening Days

| Rank | Date | Product | Operating Ratio | Downtime (h) | Events | Screening Score |
|---|---|---:|---:|---:|---:|---:|
| 1 | 2022-11-03 | 3L | 0.2907 | 3.9910 | 67 | 92.59 |
| 2 | 2022-12-13 | 5L | 0.2926 | 6.9991 | 36 | 88.89 |
| 3 | 2022-11-28 | 3L | 0.3220 | 4.5419 | 46 | 87.04 |
| 4 | 2022-12-19 | 5L | 0.1538 | 4.8586 | 25 | 87.04 |
| 5 | 2022-07-26 | 3L | 0.3785 | 3.7292 | 50 | 84.26 |

`2022-09-22`와 같이 Hourly 데이터가 없는 생산일은  
Screening Ranking에서 제외하고 Data Quality 대상으로 분리했습니다.

---

## 5. Statistical Outlier vs Operational Priority

IQR 기반 통계적 이상치와 운영 우선순위를 별도로 분석했습니다.

### IQR Limits

- Operating Ratio lower limit: **0.1103**
- Downtime upper limit: **6.4977 h**
- Event Count upper limit: **68.5**

Statistical outlier day는 총 **3일**이었습니다.

### Outlier Days

- **2022-12-13** — Downtime 6.9991 h
- **2022-07-22** — 70 Downtime Events
- **2022-12-06** — Downtime 6.8600 h

중요한 점은 다음과 같습니다.

**Statistical Outlier ≠ Operational Priority**

예를 들어 `2022-11-03`은 통계적 outlier는 아니지만  
Operating Loss, Downtime, Event Frequency를 종합했을 때  
Screening Rank 1위였습니다.

따라서 통계적 이상 여부만으로 운영 우선순위를 결정하지 않았습니다.

---

## 6. Downtime Pareto Analysis

Downtime Event의 지속시간 분포를 분석했습니다.

### Event Duration Distribution

- Median: **1.50 min**
- P75: **2.75 min**
- P90: **6.50 min**
- P95: **13.74 min**
- P99: **106.84 min**

총 **1,388건**의 Downtime Event 중  
P90 이상 장시간 Event는 **139건**이었습니다.

### Duration Contribution

| Group | Event Share | Duration Share |
|---|---:|---:|
| Short (≤ P50) | 50.07% | 10.13% |
| Medium (P50–P90) | 39.91% | 19.01% |
| Long (≥ P90) | 10.01% | 70.87% |

즉, 전체 Event 중 약 **10%의 장시간 정지**가  
전체 Event-log Duration의 **70.87%**를 차지했습니다.

또한:

- 전체 Event의 약 **2.5%인 35건**이 Duration의 50%를 설명
- **319건**이 Duration의 80%를 설명

했습니다.

이를 통해 Downtime 관리에서는 Event 발생 횟수만 보는 것보다  
**장시간 정지가 전체 손실시간에 미치는 영향을 별도로 관리하는 것이 중요함**을 확인했습니다.

---

## 7. Product Comparison

복수 제품 생산일을 제외하고 3L와 5L 생산 기록을 비교했습니다.

| Product | Records | Median Operating Ratio | Mean Operating Ratio |
|---|---:|---:|---:|
| 3L | 36 | 0.4751 | 0.4936 |
| 5L | 17 | 0.4274 | 0.4162 |

5L 생산 기록에서 Operating Ratio가 상대적으로 낮게 관찰되었습니다.

그러나 본 데이터만으로는 제품 용량 자체가 Operating Ratio 차이의 직접적인 원인이라고 판단할 수 없습니다.

제품, 생산조건, 작업순서, 설비조건 등의 추가 데이터가 필요합니다.

---

## 8. Key Findings

### 1. Long-duration events dominate loss time

Downtime Event의 약 10%가 전체 Event-log Duration의 약 71%를 차지했습니다.

### 2. Frequency and duration must be separated

Event가 자주 발생하는 날과 장시간 Downtime이 발생하는 날은 동일하지 않았습니다.

따라서 Frequency와 Duration은 별도의 Loss 지표로 관리할 필요가 있습니다.

### 3. Statistical anomaly and operational priority are different

IQR 기반 Outlier만으로는 실제 운영 우선순위를 충분히 설명하지 못했습니다.

따라서 통계적 이상 탐지와 상대적 Screening을 분리했습니다.

### 4. Data quality affects operational judgment

결측 Hourly 데이터가 있는 날짜를 그대로 Ranking에 포함하면  
잘못된 우선순위가 생성될 수 있었습니다.

이에 따라 데이터 완전성을 먼저 검증한 뒤 분석 대상을 선별했습니다.

---

## 9. Limitations

본 분석은 다음 한계를 가집니다.

- Downtime Event Log의 duration 합은 Hourly downtime과 완전히 일치하지 않음
- Downtime Event에 고장 원인 코드가 없음
- 작업자, 설비 상태, 자재, Cycle Time 데이터가 없음
- Product Type과 Downtime 간 직접적인 인과관계를 판단할 수 없음
- Screening Score의 가중치는 실제 기업 관리기준이 아닌 동일 가중치 기반 상대 비교임

따라서 본 분석은 Root Cause를 확정하는 것이 아니라  
**우선 점검 대상과 추가 확인이 필요한 데이터 범위를 좁히는 것**을 목적으로 합니다.

---

## 10. Next Step

V3에서는 V2에서 생성한 정량 Evidence를 기반으로  
전문 역할별 AI Agent를 구성할 예정입니다.

- Production Agent
- Downtime Agent
- Efficiency Agent
- Pattern Agent
- Production Manager Agent

각 Agent는 원시 데이터를 임의로 계산하지 않고  
Python 분석 결과와 검증된 Evidence를 기반으로 판단하도록 설계합니다.