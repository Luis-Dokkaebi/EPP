# src/analysis/report_main.py

import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.analysis.efficiency_calculator import EfficiencyCalculator
from src.analysis.report_generator import ReportGenerator

def generar_reporte():
    # Calculamos eficiencia
    calculator = EfficiencyCalculator()
    results_df = calculator.calculate_efficiency()

    if results_df is not None:
        # Generamos reportes
        report = ReportGenerator(results_df)
        report.generate_table()
        report.generate_bar_plot()
        report.export_to_excel()

if __name__ == "__main__":
    generar_reporte()
