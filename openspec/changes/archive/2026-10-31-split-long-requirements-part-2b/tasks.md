## 1. Split
- [x] 1.1 Split the long requirements of the 5 specs by the upstream procedure (MODIFIED keeps header and all scenarios; removed behaviors ADDED with own scenarios).

## 2. Verification
- [x] 2.1 Mechanical split check per spec; `openspec validate <change> --strict` on 1.13.2 and 1.15.0.
- [x] 2.2 After archive, the 5 specs pass `openspec validate --strict` on 1.15.0; full validation; semantic review of meaning preservation.
