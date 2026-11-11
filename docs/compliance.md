# Legal compliance checklist (US and California)

Status as of 2026-11-11. This is an engineering checklist, **not legal advice**: have a lawyer review the
Privacy Policy (`/privacy/`) and Terms of Use (`/terms/`) before a public launch, and again when the site,
its business model or the law changes.

## Before launch: things only the operator can do

1. **Name the operator and a contact address.** Set `DJANGO_SITE_OPERATOR` (person or company),
   `DJANGO_SITE_CONTACT_EMAIL` (a monitored inbox) and `DJANGO_DMCA_AGENT`. Until then the legal pages show
   highlighted placeholders and `manage.py check --deploy` warns (`legal.W001`).
2. **Register a DMCA agent** with the US Copyright Office (online, $6, renew every 3 years) and use the same
   name and address in `DJANGO_DMCA_AGENT`. Without registration the DMCA safe harbor for user uploads
   doesn't apply.
3. **Have a lawyer review** `templates/legal/privacy.html` and `templates/legal/terms.html`, especially the
   limitation of liability, Civil Code §1542 waiver, governing law and the prohibited-items list.
4. **Make the hosting match the policy:** HTTPS only; server/access logs kept no more than 30 days;
   backups overwritten within 30 days; a data processing agreement with the host.
5. **Set up a request process:** answer privacy requests (access, deletion, correction) within 45 days,
   verify the requester, and keep a log of requests and responses for 24 months.
6. **Set up moderation:** someone reads the contact inbox, removes prohibited or discriminatory ads, acts on
   DMCA notices and closes repeat infringers' accounts.
7. **Have a breach plan:** who investigates, and how users are told "in the most expedient time possible"
   if unencrypted personal information is exposed (Cal. Civ. Code §1798.82).
8. **Existing accounts** created before 2026-11-11 (the demo and test accounts) have no recorded Terms
   acceptance. Either delete them or ask them to accept on next login (see "Recommended next steps").

## Law by law

| Law | Applies? | What the site does | Status |
|---|---|---|---|
| **CalOPPA** (Cal. Bus. & Prof. Code §22575–22579): privacy policy for any commercial site collecting personal info from Californians | Yes | Policy linked in the footer of every page; lists categories collected, third parties, how to review/correct (edit ads, email), how changes are announced, effective date, and how Do Not Track is handled | Done; needs operator details |
| **CCPA / CPRA** (Cal. Civ. Code §1798.100 ff.) | Only if revenue > ~$26.6M (inflation-adjusted), or buying/selling/sharing data of 100,000+ consumers, or 50%+ of revenue from selling/sharing | Policy already gives every user the CCPA rights (know, delete, correct, opt out, limit sensitive data, non-discrimination), states no selling or sharing, lists categories, sources, purposes and retention. Self-service deletion via account deletion | Done as good practice; request process is operational (item 5) |
| **Sensitive personal information** (CPRA: precise geolocation, account login) | Partly | Location is optional, only collected on a user click, rounded to ~100 m, used only to show the ad or run the search; disclosed in policy | Done |
| **"Shine the Light"** (Cal. Civ. Code §1798.83) | Yes, if sharing for direct marketing | Policy states no sharing for direct marketing | Done |
| **Global Privacy Control / Do Not Track** | Yes (CalOPPA disclosure; CCPA if covered) | No tracking, ads or analytics; two essential cookies plus an optional `theme` preference cookie; policy explains signals change nothing | Done |
| **COPPA** (15 U.S.C. §6501): children under 13 | Not directed at children | Users must be 18+ (signup checkbox, Terms); policy says no knowing collection from under-13s and how to get it deleted | Done |
| **California "eraser" law** (Bus. & Prof. Code §22581): minors can remove their posts | Only for sites used by minors | Site is 18+; users can delete ads and accounts themselves; policy covers removal requests | Done |
| **Data breach notification** (Cal. Civ. Code §1798.82, §1798.81.5 "reasonable security") | Yes | HTTPS, hashed passwords, login throttling, CSP, private messages access-controlled, photo metadata stripped | Code done; breach plan is operational (item 7) |
| **DMCA §512** safe harbor for user uploads | Yes (photos, text) | Terms give the notice/counter-notice procedure and repeat-infringer policy | Needs agent registration (item 2) |
| **Communications Decency Act §230** | Protects the site for users' content | Neutral tools; the site doesn't require or suggest discriminatory choices | No action needed |
| **Fair Housing Act** (42 U.S.C. §3604(c)) and **California FEHA** / Gov. Code §12955: discriminatory housing ads | Yes (Housing category) | Terms prohibit discriminatory housing ads and list protected characteristics; reminder on the post-ad form | Done; enforcement via moderation (item 6) |
| **Title VII / FEHA** equal employment; **California pay transparency** (Lab. Code §432.3) for job ads | Yes (Jobs category) | Terms require equal-employment compliance and pay-transparency where it applies; reminder on the post-ad form | Done |
| **FOSTA-SESTA**; federal and state laws on prohibited goods (drugs, firearms, alcohol, tobacco, counterfeit, recalled products) | Yes | Terms prohibit them and sexual services; removal and account closure reserved | Done; enforcement via moderation |
| **ADA Title III** and **California Unruh Civil Rights Act**: website accessibility (WCAG 2.1 AA is the usual standard) | Yes in practice | Automated axe-core 4.14 audit of every page type, light and dark mode, logged out and in: **no WCAG 2.1 A/AA violations** (fixed: muted-text contrast, dark-mode danger button, unnamed photo links). Keyboard focus styles, focus trap in the photo viewer, labelled forms, alt text | Automated checks pass; manual screen-reader testing recommended |
| **CAN-SPAM** / **California anti-spam** (Bus. & Prof. Code §17529.5) | Not now | The site sends no email | Revisit before adding email notifications |
| **California Automatic Renewal Law**, **TCPA** | No | No subscriptions, payments or text messages | N/A |
| **California consumer-protection / false advertising** (Bus. & Prof. Code §17200, §17500) | Yes | Site makes no claims about listed items; Terms say it's a venue, not a party | Done |
| **Clickwrap enforceability** of the Terms | Yes | Unticked-by-default checkbox with links at signup; acceptance stored with date and terms version (`accounts.TermsAcceptance`) | Done |

## What the code records for compliance

- `accounts.TermsAcceptance`: user, terms version (`legal.policy.TERMS_VERSION`) and time of acceptance.
- `legal/policy.py`: effective dates, terms version, minimum age. **Bump these when the text changes.**
- No analytics, ad or social scripts; all assets self-hosted (a test fails if a template loads a third-party
  script, stylesheet, image or font).
- Retention as stated in the policy: rate-limit counters ≤ 1 day; geocoding cache 7 days (place names only,
  not linked to users); everything else until the user deletes it.

## Recommended next steps (not legally required today)

1. **"Report this ad" button**, so prohibited, discriminatory or scam ads reach moderators quickly.
2. **Re-acceptance prompt**: when `TERMS_VERSION` changes, ask logged-in users to accept before continuing.
3. **Download my data**: a self-service export makes access requests trivial.
4. **Accessibility statement** page with a contact for accessibility problems, and a manual screen-reader pass
   (VoiceOver, NVDA).
5. **Email verification** before posting, if email notifications are added (then CAN-SPAM applies).
