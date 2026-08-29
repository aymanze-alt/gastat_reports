# gastat_reports

Custom application for the **General Authority for Statistics (GASTAT)** – Saudi Arabia that generates two monthly statistical reports:

1. **Industrial Production Survey** (تقرير المسح الصناعي الشهري) – product / item production data with value analysis.
2. **Employee Statistics** (إحصاءات الموظفين) – national / gender breakdown with salary distribution.

## Features

- Beautiful Frappe **Custom Pages** (HTML / CSS / JS) with:
  - Summary statistic cards with icons and colors
  - Frappe Charts (pie, bar) visualizations
  - Zebra-striped, sortable data tables with grand totals
  - Print-ready layouts
- **Server-side REST APIs** (`/api`) for both reports.
- **PDF export** with a professional RTL-Arabic print template (letterhead, signature block, page numbers).
- **Excel export** with formatting and summary rows.
- Custom **DocTypes**:
  - `GASTAT Settings` (Single) – configuration (company, price source, salary component, letterhead).
  - `GASTAT Production Item` (Child) – configurable list of items for the production report.
  - `GASTAT Monthly Report Log` – audit trail of every generated report.
- Dedicated **Workspace** for quick access.

## Installation

```bash
bench get-app gastat_reports
bench --site your-site install-app gastat_reports
bench --site your-site migrate
```

After install, open the app Workspace and configure **GASTAT Settings** (company, price source, salary component, logo, signatory).

## License

MIT
# gastat_reports
