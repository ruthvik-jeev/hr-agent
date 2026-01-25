"""
Compensation Repository - Salary and compensation data access
"""

from .base import BaseRepository


class CompensationRepository(BaseRepository):
    """Repository for compensation data."""

    def get_by_employee(self, employee_id: int) -> dict | None:
        """Get compensation details for an employee."""
        row = self._execute_query_one(
            """SELECT c.employee_id, e.preferred_name, c.currency, c.base_salary,
                      c.bonus_target_pct, c.equity_shares, c.last_review_date, c.next_review_date
               FROM compensation c
               JOIN employee e ON e.employee_id = c.employee_id
               WHERE c.employee_id=:e""",
            {"e": employee_id},
        )
        if not row:
            return None

        bonus_amount = round(row["base_salary"] * row["bonus_target_pct"] / 100, 2)
        return {
            **row,
            "bonus_target_amount": bonus_amount,
            "total_target_compensation": round(row["base_salary"] + bonus_amount, 2),
        }

    def get_salary_history(self, employee_id: int) -> list[dict]:
        """Get salary history for an employee."""
        return self._execute_query(
            """SELECT effective_date, base_salary, currency, change_reason, change_pct
               FROM salary_history
               WHERE employee_id=:e
               ORDER BY effective_date DESC""",
            {"e": employee_id},
        )

    def get_team_summary(self, manager_id: int) -> dict:
        """Get compensation summary for a manager's team."""
        rows = self._execute_query(
            """SELECT e.employee_id, e.preferred_name, e.title,
                      c.currency, c.base_salary, c.bonus_target_pct
               FROM manager_reports mr
               JOIN employee e ON e.employee_id = mr.report_employee_id
               LEFT JOIN compensation c ON c.employee_id = e.employee_id
               WHERE mr.manager_employee_id = :m
               ORDER BY c.base_salary DESC""",
            {"m": manager_id},
        )

        if not rows:
            return {"error": "No direct reports found"}

        salaries = [r["base_salary"] for r in rows if r["base_salary"]]

        return {
            "manager_employee_id": manager_id,
            "team_size": len(rows),
            "total_payroll": sum(salaries) if salaries else 0,
            "average_salary": (
                round(sum(salaries) / len(salaries), 2) if salaries else 0
            ),
            "min_salary": min(salaries) if salaries else 0,
            "max_salary": max(salaries) if salaries else 0,
            "team_members": rows,
        }
