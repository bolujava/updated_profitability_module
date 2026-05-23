NEW MODIFICATION DONE:

>>>>> Timesheet Integration at the Planner side.

and

Here’s a clean, structured version of your logic comparison table — with clear **columns and row separators** for readability (you can paste this directly into documentation, a wiki, or an Odoo module description):

---



| **Field**                        | **Current Logic (Your Existing Direct Cost)** | **Revamped Logic (Progress-Weighted Forecast)**                                                                                                                  | **Data Source & Rationale**                                                                                                                                                                   |   |                                                                                            |
| -------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | - | ------------------------------------------------------------------------------------------ |
| **budget_utilized**              | ∑(time cost) + ∑(expenses)                    | **No Change.** Remains the sum of actual monetary costs incurred to date.                                                                                        | Direct costs from employee timesheets (cost × hour) and linked project expenses. This represents **Actual Cost (AC)**.                                                                        |   |                                                                                            |
| **budget_remaining**             | budget − budget_utilized                      | **No Change.** Still the unspent portion of the total budget.                                                                                                    | Calculated dynamically from total project budget.                                                                                                                                             |   |                                                                                            |
| **project_progress (New Field)** | Not Applicable                                | **New computed field on `project.project`**: <br> **Average of all linked task progress values** <br> `project_progress = (Σ task.progress) / (Number of tasks)` | Derived from all related `project.task` records. Represents **Performance Index (Progress %)**.                                                                                               |   |                                                                                            |
| **profitability**                | budget − budget_utilized                      | **Forecasted Profitability:** <br> `budget − ((project_progress / 100) × budget_utilized)`                                                                       | **Forecast (EAC):** Projects expected final profit/loss if spending continues at the same cost-per-progress rate. Based on **Budget at Completion (BAC)** and **Expected Actual Cost (EAC)**. |   |                                                                                            |
| **forecasted_budget_overrun**    | max(utilized − budget, 0)                     | **No Change (implicit).** If profitability < 0, then: <br> `overrun =                                                                                            | profitability                                                                                                                                                                                 | ` | Remains dynamically accurate — automatically reflected through profitability computations. |



HOW TO INSTALL THE MODULE.
1. Install task_logs (hr_timesheet)
2. Install timesheet_grid (known as Timesheet)
3. Install project_enterprise
4. Install project_timesheet_forecast
5. All these will help in installing sale_timesheet
6. Finally install the lba_profitability_module (Project Profitability Module)
7. Add in the manifest sale_planning when launching to live