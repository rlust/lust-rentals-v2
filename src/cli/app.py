"""Command-line entrypoints for Lust Rentals processing and reporting."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from src.data_processing.processor import FinancialDataProcessor
from src.reporting.tax_reports import TaxReporter
from src.reporting.property_reports import PropertyReportGenerator
from src.utils.config import configure_logging, load_config

app = typer.Typer(help="Operational commands for Lust Rentals tax reporting workflows.")


@app.callback()
def initialize(level: Optional[str] = typer.Option(None, "--log-level", help="Log level override")) -> None:
    """Initialize logging from configuration or CLI overrides."""

    config = load_config()
    if level is not None:
        configure_logging(level)
    else:
        configure_logging(config.log_level)


@app.command()
def process_bank(
    bank_file: Optional[Path] = typer.Option(
        None,
        "--bank-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional explicit path to Park National transaction export.",
    ),
    year: Optional[int] = typer.Option(
        None,
        "--year",
        help="Restrict transactions to a specific tax year.",
    ),
) -> None:
    """Process the latest bank feed and persist normalized outputs."""

    processor = FinancialDataProcessor()
    results = processor.process_bank_transactions(file_path=bank_file, year=year)

    typer.echo(
        f"Processed bank feed: income rows={len(results['income'])}, expenses rows={len(results['expenses'])}."
    )
    if "unresolved" in results:
        typer.echo(f"Unresolved transactions written: {len(results['unresolved'])}")


@app.command()
def generate_reports(
    year: Optional[int] = typer.Option(
        None,
        "--year",
        help="Tax year to report (defaults to prior calendar year).",
    ),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist PDF and CSV outputs."),
) -> None:
    """Produce annual summary and Schedule E outputs for the requested year."""

    reporter = TaxReporter()
    target_year = year or (datetime.now().year - 1)

    summary = reporter.generate_annual_summary(year=target_year, save_to_file=save)
    typer.echo(
        f"Summary complete for {target_year}: income ${summary['total_income']:.2f}, net ${summary['net_income']:.2f}."
    )

    schedule = reporter.generate_schedule_e(year=target_year)
    typer.echo(
        f"Schedule E generated for {target_year}: income ${schedule['1']:.2f}, expenses ${schedule['11']:.2f}."
    )


@app.command()
def generate_property_pdf(
    year: Optional[int] = typer.Option(
        None,
        "--year",
        help="Tax year to report (defaults to prior calendar year).",
    ),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist PDF output."),
) -> None:
    """Generate a simplified PDF report showing income and expenses by property."""

    generator = PropertyReportGenerator()
    target_year = year or (datetime.now().year - 1)

    file_path, summary = generator.generate_pdf_report(year=target_year, save_to_file=save)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"Property Income & Expense Report - {target_year}")
    typer.echo(f"{'='*60}")
    typer.echo(f"Total Income:    ${summary['total_income']:>15,.2f}")
    typer.echo(f"Total Expenses:  ${summary['total_expenses']:>15,.2f}")
    typer.echo(f"Net Income:      ${summary['total_net']:>15,.2f}")
    typer.echo(f"Properties:      {len(summary['properties']):>15}")

    if save and file_path:
        typer.echo(f"\n✓ PDF report saved to: {file_path}")

    typer.echo(f"{'='*60}\n")


@app.command()
def generate_property_excel(
    year: Optional[int] = typer.Option(
        None,
        "--year",
        help="Tax year to report (defaults to prior calendar year).",
    ),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist Excel output."),
) -> None:
    """Generate a simplified Excel report showing income and expenses by property."""

    generator = PropertyReportGenerator()
    target_year = year or (datetime.now().year - 1)

    file_path, summary = generator.generate_excel_report(year=target_year, save_to_file=save)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"Property Income & Expense Report - {target_year}")
    typer.echo(f"{'='*60}")
    typer.echo(f"Total Income:    ${summary['total_income']:>15,.2f}")
    typer.echo(f"Total Expenses:  ${summary['total_expenses']:>15,.2f}")
    typer.echo(f"Net Income:      ${summary['total_net']:>15,.2f}")
    typer.echo(f"Properties:      {len(summary['properties']):>15}")

    if save and file_path:
        typer.echo(f"\n✓ Excel report saved to: {file_path}")

    typer.echo(f"{'='*60}\n")


def main() -> None:
    """CLI entrypoint for console_scripts."""

    app()


if __name__ == "__main__":
    main()
