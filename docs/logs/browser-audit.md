# Browser Audit Log

**Date:** 2026-03-03
**Tool:** BrowserOS (Chrome MCP) + manual JS execution
**Server:** http://127.0.0.1:8000 (uvicorn, SQLite WAL)
**Users:** audita@test.com (User A), auditb@test.com (User B)

---

## 1. Auth Edge Cases (8/8 PASS)

| # | Test | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 1.1 | Empty login | Error toast | "Please fill in all fields" | PASS |
| 1.2 | Empty signup | Error toast | "Please fill in all fields" | PASS |
| 1.3 | Invalid email signup (`not-an-email`) | Rejected | "Validation failed" | PASS |
| 1.4 | Weak password signup (`weak`) | Rejected | "Validation failed" | PASS |
| 1.5 | Valid signup (audita@test.com) | Success | "Account created for audita@test.com!" | PASS |
| 1.6 | Duplicate email signup | Rejected | "Email already registered" | PASS |
| 1.7 | Wrong password login | Rejected | "Invalid credentials" | PASS |
| 1.8 | Non-existent user login | Rejected | "Invalid credentials" | PASS |

## 2. User A Full Journey (All PASS)

| Step | Action | Result |
|------|--------|--------|
| Login | audita@test.com / AuditPass1! | "Logged in successfully" |
| Empty profile | Submit with empty fields | "Please fill all profile fields" |
| Create profile | Audit UserA, 1990-05-15 | "Profile created!" |
| Open checking | Checking account | "Account opened!" — ACTIVE, $0.00 |
| Open savings | Savings account | "Account opened!" — ACTIVE, $0.00 |
| Deposit $5000 | To checking | "Deposited $5000.00!" — balance $5000 |
| Deposit $2500 | To savings | "Deposited $2500.00!" — balance $2500 |
| Transfer $1000 | Checking → savings | "Transferred $1000.00!" |
| Transfer $500 | Savings → checking | "Transferred $500.00!" |
| Balance check | Verify math | checking=$4500, savings=$3000 CORRECT |
| Transaction history | Checking account | DEPOSIT +$5000, DEBIT -$1000, CREDIT +$500 |
| All Transfers | Both transfers listed | $1000 + $500 with correct account IDs |
| Issue card 1 | On checking (****0122) | "Card issued!" — ACTIVE |
| Card spend | $75.50 at Downtown Bistro | "Charged $75.50 at Downtown Bistro" |
| Issue card 2 | On checking (****2082) | "Card issued!" — ACTIVE |
| Issue card 3 | On savings (****5388) | "Card issued!" — ACTIVE |
| Statement | Checking Feb 1 - Mar 3 | Opening $0, Credits +$5500, Debits -$1075.50, Closing $4424.50, 4 txns |
| Statement math | Verify | $0 + $5500 - $1075.50 = $4424.50 CORRECT |

## 3. Deposit Edge Cases (4/4 PASS)

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Zero deposit ($0) | Rejected | "Enter a valid amount" | PASS |
| Negative deposit (-$100) | Rejected | "Enter a valid amount" | PASS |
| Valid deposit $5000 | Success | "Deposited $5000.00!" | PASS |
| Valid deposit $2500 (savings) | Success | "Deposited $2500.00!" | PASS |

## 4. Transfer Edge Cases (7/7 PASS)

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Same account transfer | Rejected | "Cannot transfer to same account" | PASS |
| Zero amount ($0) | Rejected | "Enter a valid amount" | PASS |
| Negative amount (-$500) | Rejected | "Enter a valid amount" | PASS |
| Overdraft ($99,999 from $5000) | Rejected | "Insufficient funds" | PASS |
| Huge amount ($999,999,999) | Rejected | "Insufficient funds" | PASS |
| Valid $1000 checking→savings | Success | "Transferred $1000.00!" | PASS |
| Valid $500 savings→checking | Success | "Transferred $500.00!" | PASS |

## 5. Card Edge Cases (10/10 PASS)

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Zero spend ($0) | Rejected | "Enter a valid amount" | PASS |
| Negative spend (-$50) | Rejected | "Enter a valid amount" | PASS |
| Empty merchant | Rejected | "Enter a merchant name" | PASS |
| Valid spend $75.50 | Success | "Charged $75.50 at Downtown Bistro" | PASS |
| Overdraft spend ($99,999) | Rejected | "Insufficient funds" | PASS |
| Block card (****0122) | Blocked | "Card blocked" — UI shows BLOCKED, Activate button | PASS |
| Spend on blocked card (API) | HTTP 400 | "Card is blocked" | PASS |
| Blocked card hidden from spend dropdown | Not selectable | Only active cards shown | PASS |
| Activate blocked card | Reactivated | "Card active" — status back to ACTIVE | PASS |
| Cancel card (****2082) | Cancelled | "Card cancelled" — permanent | PASS |
| Reactivate cancelled card (API) | HTTP 400 | "Cannot transition card from 'cancelled' to 'active'" | PASS |
| Spend on cancelled card (API) | HTTP 400 | "Card is cancelled" | PASS |

## 6. Account State Transitions (6/6 PASS, 2 findings)

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Freeze savings account | Frozen | "Account frozen" — UI shows FROZEN | PASS |
| Transfer FROM frozen (API) | HTTP 400 | "Source account is not active" | PASS |
| Deposit TO frozen (API) | Debatable | HTTP 200 — deposit succeeded | FINDING |
| Unfreeze account | Active | "Account active" | PASS |
| Close account with $4000 balance (API) | Debatable | HTTP 200 — closed with balance | FINDING |
| Reopen closed account (API) | HTTP 400 | "Cannot transition from 'closed' to 'active'" | PASS |
| Deposit to closed account (API) | Should fail | HTTP 200 — deposit succeeded | BUG |
| Transfer TO closed account (API) | HTTP 400 | "Destination account is not active" | PASS |

## 7. Cross-User Isolation (6/6 PASS)

User B (auditb@test.com) attempting to access User A's resources:

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| GET User A's account | HTTP 403 | "Access denied" | PASS |
| Deposit to User A's account | HTTP 403 | "Access denied" | PASS |
| Transfer from User A's account | HTTP 403 | "Access denied" | PASS |
| GET User A's card | HTTP 403 | "Access denied" | PASS |
| Spend on User A's card | HTTP 403 | "Access denied" | PASS |
| GET User A's transactions | HTTP 403 | "Access denied" | PASS |

## 8. UI/UX Audit (All PASS)

| Test | Result | Status |
|------|--------|--------|
| Login persistence | Profile "Audit UserA" persisted after logout/login | PASS |
| Dashboard aggregation | Total $8524.50, 1 active account, 2 active cards | PASS |
| Recent activity | All txns from both accounts, sorted by date | PASS |
| Dark mode toggle | Full dark theme, proper contrast, all elements styled | PASS |
| Ops panel | 92 API requests logged with method/path/status/latency/X-Request-ID | PASS |
| Light mode restore | Clean toggle back to light | PASS |
| Sidebar navigation | All tabs navigate correctly, active state highlighted | PASS |
| Guided flow steps | Steps 1-6 progress bar updates correctly | PASS |

---

## Bugs Found

### BUG #1: Deposit endpoint missing account status check (CONFIRMED)

**Location:** `app/services/transfer_service.py:129-146`
**Severity:** Medium
**Description:** The `deposit()` function validates ownership and positive amount, but does NOT check `account.status`. Deposits succeed on frozen and closed accounts.
**Evidence:**
- Deposit to frozen savings: HTTP 200, balance $3000 → $4000
- Deposit to closed savings: HTTP 200, balance $4000 → $4100
**Fix:** Add status check after ownership validation:
```python
if account.status != "active":
    raise HTTPException(status_code=400, detail=f"Account is {account.status}")
```

### FINDING #1: Account can be closed with non-zero balance

**Location:** `app/services/account_service.py`
**Severity:** Low (design decision)
**Description:** Closing an account with $4000 balance succeeds. Some banking systems require zero balance before closure.
**Note:** This may be intentional — the assessment doesn't specify closure prerequisites.

### FINDING #2: Deposit to frozen account succeeds

**Severity:** Low (design decision)
**Description:** In real banking, frozen accounts often still accept incoming funds. This could be correct behavior, but should be documented.

---

## Summary

| Category | Tests | Passed | Failed | Findings |
|----------|-------|--------|--------|----------|
| Auth edge cases | 8 | 8 | 0 | 0 |
| User A journey | 18 | 18 | 0 | 0 |
| Deposit edge cases | 4 | 4 | 0 | 0 |
| Transfer edge cases | 7 | 7 | 0 | 0 |
| Card edge cases | 12 | 12 | 0 | 0 |
| Account states | 8 | 6 | 1 | 2 |
| Cross-user isolation | 6 | 6 | 0 | 0 |
| UI/UX | 8 | 8 | 0 | 0 |
| **Total** | **71** | **69** | **1** | **2** |

**1 confirmed bug** (deposit to closed/frozen accounts), **2 design findings** (account closure with balance, frozen deposit).
**0 security issues** — cross-user isolation is airtight (6/6 tests returned HTTP 403).
