## Production Summary
The most important production issue is repeated **Low Schedule Attainment for product B200**. It accounts for 3 exception records and is the only pattern assigned **HIGH** priority.

## Priority Issue
The highest-priority repeated pattern is:

- **Product:** B200
- **Exception:** Low Schedule Attainment
- **Occurrences:** 3
- **Priority:** HIGH

## Evidence
- The dataset contains **8 total exception records**.
- B200 Low Schedule Attainment occurred **3 times**, the highest occurrence count shown.
- Its assigned priority is **HIGH**.
- C300 High Defect Rate occurred 2 times with **MEDIUM** priority.
- The remaining listed patterns each occurred once and were assigned **LOW** priority.
- These observations identify a repeated KPI exception, but they do not establish a physical root cause.

## Recommended Next Check
Check the underlying production records for the three B200 Low Schedule Attainment exceptions, including:

- The relevant production periods or runs.
- Planned production versus actual production used to calculate schedule attainment.
- Whether the exceptions are concentrated in a particular line, shift, order, or other recorded production segment.
- The calculation inputs and exception-rule application for those records.

## Limitations
The evidence is insufficient to determine why B200 had low schedule attainment. It provides KPI-level exceptions and rule-based priorities, but does not prove physical causes, operating conditions, equipment issues, staffing issues, material issues, or planning issues.