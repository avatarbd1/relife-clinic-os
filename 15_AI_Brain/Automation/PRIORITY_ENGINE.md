# PRIORITY ENGINE

Purpose:
Decide task priority before assignment.

## Priority Levels

P0 — Critical

Examples:
- Security issue
- Production failure
- Patient data risk
- Bot completely down


P1 — High

Examples:
- Core clinic operation blocked
- Payment/salary/patient workflow issue
- Important production improvement


P2 — Medium

Examples:
- Feature improvement
- User experience improvement
- Automation improvement


P3 — Low

Examples:
- Documentation
- Minor cleanup
- Future ideas


## Decision Factors

Brain evaluates:

1. Business Impact
2. Patient Impact
3. Security Risk
4. Time Urgency
5. Development Cost


## Assignment Rule

Higher priority tasks are considered first.

However:

- Production changes require approval.
- Conflicting tasks wait.
- Owner decision overrides priority.


## Output

Every generated task should contain:

Priority:
Reason:
Risk:
Expected Impact:
