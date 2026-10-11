# Revision 3: every flagged artifact traced to a correction

Source: the frozen v2 author review, 108 flagged documents out of 300. One primary
flag per document; the five groups below are mutually exclusive. The complete
ID, original category and original reason mapping is in `clusters-v3.json`.
This is a diagnosis of earlier outcomes, not an evaluation of revision 3.

| Cluster | n / 108 | Original categories | Correction |
|---|---:|---|---|
| Repeated scaffolds | 63 | amounts 23; oversized fixtures 22; versions 14; statute padding 3; fare repetition 1 | Variable-length receipts with varied cents; executable retry tests covering distinct failures; remove irrelevant versions/article lists; four distinct fares. |
| Missing task material | 20 | export 4; tickets 4; merchant strings 3; accounts 3; receipts 3; expenses 2; receipt 1 | Supply amounts even in short billing requests, both merchant strings, account and passenger references. |
| Inconsistent context | 9 | shared context 6; conflicting question counts 2; delivery contradiction 1 | Delivery asks no longer assert a particular outcome; individual notes drive the reply; workshop count is stated once. |
| Forced quotations | 5 | artificial greeting/status fragments | A substantive request with first-name signature; no self-addressed greeting or Polish vocative mistake. |
| Inappropriate or unused PII | 11 | clinical tax/NINO 4; excessive applicant intake 3; unused token 4 | Remove national IDs from clinical records; payroll intake after accepted offers; token authenticates the queue client. |

Preventive change, not an extra diagnosed count: code-switching is restricted to
single-person IT handovers with an explicit translation purpose. Receipt fields
remain attributed to their owners. New localized support/payroll/quoted-message
prose is authored in all eight languages. No external source or model call is used.

The v2 allocation function is reused: identical conversation/family/scenario/
translation/subject IDs, split reservations, subject counts and length strata.
Manifest `data_revision` advances to 3; schema version stays 1 and status stays dev.
Historical inputs and scored receipts remain immutable. Only current local strict
records are regenerated. Long billing/code concentration and template reuse remain
limitations, not independent scenario coverage or evidence of a passed panel gate.

A separate reviewer receives only the fresh 300-document Stage A packet and rubric
under `docs/validation/gateway-r1-sample/`. No author ratings are supplied. The
coordinator mapping and sampling receipt are outside that directory. Outcomes,
confidence intervals and agreement await the independent europriv-bench panel run.
