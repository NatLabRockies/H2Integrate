# Real vs Nominal Analysis

There can be significant confusion when distinguishing between **real** and **nominal** analyses in financial or techno-economic studies. This distinction matters because it determines whether and how inflation is accounted for when evaluating costs, revenues, or cash flows.

---

```{eval-rst}
.. toctree::
   :hidden:

  ../user_guide/specifying_finance_parameters
  ../user_guide/cost_years
```

## Key Definitions

* **Real Analysis:**
  Presents all monetary values in terms of a **single reference year** (constant dollars).

  * Inflation effects are **removed** so that results reflect true purchasing power.
  * Useful for comparing values across time without inflation distortions.

* **Nominal Analysis:**
  Presents values in the **year dollars they occur** (current or actual year dollars).

  * Inflation effects are **included** since each year’s value reflects that year’s prices.

---

## How Inflation Is Applied

The application of inflation depends on whether the analysis is **historical** or **predictive (forward-looking)**:

| Type of Analysis                 | Real Analysis                                                                                                               | Nominal Analysis                                                                                    |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Historical**                   | Must **add inflation** to bring past values to the base year (e.g., convert 2010 dollars to 2025 dollars).                  | Uses **recorded values as-is**, since historical data are already in their respective year dollars. |
| **Predictive / Forward-looking** | Uses **current-year values directly** — inflation is not added because costs are expressed in today’s dollars (real terms). | Must **add inflation** to project future year costs or revenues in their actual year dollars.       |

---

## Example: Five-Year Project with 2% Annual Inflation

Suppose you are evaluating a project that incurs $1 million in operating costs each year for five years, expressed in **today’s dollars** (Year 0).

| Year | Real Analysis (constant $) | Nominal Analysis (2% inflation) |
| ---- | -------------------------- | ------------------------------- |
| 1    | $1,000,000                 | $1,020,000                      |
| 2    | $1,000,000                 | $1,040,400                      |
| 3    | $1,000,000                 | $1,061,208                      |
| 4    | $1,000,000                 | $1,082,432                      |
| 5    | $1,000,000                 | $1,104,081                      |

**Interpretation:**

* The **real analysis** shows the same cost every year because it ignores inflation—values are all in Year 0 (today’s) dollars.
* The **nominal analysis** escalates costs each year to reflect inflation, showing what you’d actually pay in each year’s currency.

---

## Summary

In short:

* **Real analysis** removes inflation effects — values are in constant dollars.
* **Nominal analysis** includes inflation effects — values are in actual year dollars.
* The direction of inflation adjustment (adding or not adding) flips depending on whether you’re looking **backward (historical)** or **forward (predictive)**.

All approaches are useful — what matters most is being **abundantly clear** which one is being applied and consistent across your calculations.
