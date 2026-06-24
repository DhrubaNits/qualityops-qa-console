# Healthcare Workflow Test Checklist

Use this checklist for healthcare patient registration, eligibility, and appointment scheduling requirements.

## Patient Registration

- Validate mandatory demographic fields: First Name, Last Name, DOB, Gender, Phone, and Address when required by the workflow.
- Verify invalid formats such as alphabetic phone numbers, impossible DOB values, unsupported gender values, and incomplete address data.
- Confirm valid patient records persist exactly once with the entered demographic details.
- Confirm confirmation messages are shown after successful save.

## Duplicate Patient Validation

- Match duplicates using configured identifiers such as First Name, Last Name, and DOB.
- Display a duplicate patient warning before final save.
- Show enough matching details for the user to make a safe decision.
- If Continue Anyway is allowed, require explicit confirmation and audit the override.
- If Continue Anyway is not allowed, block save and preserve the entered data for correction.

## Eligibility Verification

- Validate Active eligibility behavior before appointment creation.
- Validate Inactive eligibility behavior with warning or configured block.
- Validate Unavailable or Timeout behavior without silently treating the patient as eligible.
- Verify retry, confirmation, or safe-stop behavior.
- Confirm logs capture operational failure details without exposing tokens, secrets, or raw authorization headers.

## Appointment Scheduling

- Validate appointment creation, update, and reschedule.
- Enforce provider, location, appointment date/time, and appointment type.
- Block past dates, unavailable providers, unavailable locations, and missing required scheduling fields.
- Preserve valid entered values when validation fails so the user can correct only the invalid fields.
- Display confirmation after successful save or reschedule.

## Role, Access, Audit, and Integration

- Validate clinic staff can perform permitted registration and scheduling actions.
- Validate unauthorized roles cannot create or modify patient, appointment, or audit records.
- Verify audit trail entries for patient creation, duplicate warning override, eligibility verification, appointment creation, update, and reschedule.
- Validate downstream API failure behavior for patient, eligibility, scheduler, notification, or audit services.
- Verify user-facing warning and confirmation messages are clear, actionable, and specific.
