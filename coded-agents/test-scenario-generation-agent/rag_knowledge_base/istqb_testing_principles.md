# ISTQB Testing Principles

Apply these principles when designing QualityOps scenarios.

## Testing Shows Presence of Defects

Tests provide evidence that defects exist when observed behavior differs from expected behavior. Passing tests reduce risk but do not prove the workflow is defect-free.

## Exhaustive Testing Is Impossible

Do not attempt every possible demographic, eligibility, provider, location, and appointment combination. Select representative tests based on risk, acceptance criteria, business impact, boundaries, and known defect-prone areas.

## Early Testing

Use signed-off requirements, QA Lead review feedback, identified gaps, and acceptance criteria to design tests before implementation completes. Early test design exposes ambiguous expected results, missing preconditions, missing data rules, and unclear failure behavior.

## Defect Clustering

Healthcare workflows often cluster defects around validation, duplicate detection, eligibility integration, appointment scheduling rules, audit logging, and role-based access. Prioritize these areas when risk is high.

## Pesticide Paradox

Do not repeat only the happy path. Add negative, boundary, timeout, unavailable service, duplicate patient, role/access, audit, and regression scenarios so the suite continues finding new defects.

## Testing Is Context Dependent

Healthcare workflow testing must consider patient safety, privacy, auditability, user-facing warnings, provider/location constraints, eligibility status, downstream API reliability, and operational recovery. Test design for healthcare must be more explicit than generic CRUD testing.

## Absence of Errors Fallacy

A workflow that saves without technical errors can still fail the business need. Verify that the correct patient data, eligibility status, appointment details, warning messages, confirmation messages, and audit records are produced according to the signed-off requirement.
