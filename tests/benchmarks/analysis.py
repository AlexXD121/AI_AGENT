"""Benchmark Analysis and Reporting Module.

Provides statistical analysis and visualization generation for benchmark results.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import warnings

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from loguru import logger


# Configure plotting style
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 10

# Suppress matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning)


class BenchmarkAnalyzer:
    """Statistical analysis and visualization for benchmark results."""
    
    def __init__(self, results_df: pd.DataFrame):
        """Initialize analyzer with benchmark results.
        
        Args:
            results_df: DataFrame containing benchmark results
        """
        self.df = results_df
        self.report_data = {}
        
        logger.info(f"BenchmarkAnalyzer initialized with {len(results_df)} results")
    
    def calculate_confidence_interval(
        self,
        data: List[float],
        confidence: float = 0.95
    ) -> Dict[str, float]:
        """Calculate statistical confidence interval.
        
        Args:
            data: List of numeric values
            confidence: Confidence level (default: 0.95 for 95% CI)
            
        Returns:
            Dictionary with mean, std_dev, ci_lower, ci_upper
        """
        if not data or len(data) < 2:
            return {
                'mean': 0.0,
                'std_dev': 0.0,
                'ci_lower': 0.0,
                'ci_upper': 0.0
            }
        
        data_array = np.array(data)
        mean = np.mean(data_array)
        std_dev = np.std(data_array, ddof=1)
        
        # Calculate confidence interval using t-distribution
        n = len(data_array)
        se = std_dev / np.sqrt(n)
        t_critical = stats.t.ppf((1 + confidence) / 2, n - 1)
        
        margin_error = t_critical * se
        
        return {
            'mean': float(mean),
            'std_dev': float(std_dev),
            'ci_lower': float(mean - margin_error),
            'ci_upper': float(mean + margin_error)
        }
    
    def analyze_processing_time(self) -> pd.DataFrame:
        """Analyze processing time by document type.
        
        Returns:
            DataFrame with latency percentiles (p50, p95, p99) by doc_type
        """
        if 'processing_time' not in self.df.columns:
            logger.warning("No processing_time column found")
            return pd.DataFrame()
        
        # Group by doc_type if available, otherwise aggregate all
        if 'doc_type' in self.df.columns:
            grouped = self.df.groupby('doc_type')['processing_time']
        else:
            grouped = {'all': self.df['processing_time']}
        
        latency_stats = []
        
        for doc_type, times in (grouped if isinstance(grouped, dict) else grouped):
            stats_dict = {
                'doc_type': doc_type,
                'count': len(times),
                'mean': times.mean(),
                'p50': times.quantile(0.50),
                'p95': times.quantile(0.95),
                'p99': times.quantile(0.99),
                'min': times.min(),
                'max': times.max()
            }
            latency_stats.append(stats_dict)
        
        result_df = pd.DataFrame(latency_stats)
        self.report_data['latency_analysis'] = result_df
        
        logger.info("Processing time analysis complete")
        return result_df
    
    def analyze_failures(self) -> Dict[str, Any]:
        """Analyze failure rates and error types.
        
        Returns:
            Dictionary with failure statistics
        """
        if 'status' not in self.df.columns:
            logger.warning("No status column found")
            return {'total': 0, 'failures': 0, 'failure_rate': 0.0}
        
        total_count = len(self.df)
        
        # Identify failures (status != 'pass')
        failures = self.df[self.df['status'] != 'pass']
        failure_count = len(failures)
        failure_rate = (failure_count / total_count * 100) if total_count > 0 else 0.0
        
        # Count by error type if available
        error_breakdown = {}
        if 'error_type' in self.df.columns:
            error_breakdown = failures['error_type'].value_counts().to_dict()
        elif 'status' in self.df.columns:
            # Use status as error type
            error_breakdown = failures['status'].value_counts().to_dict()
        
        result = {
            'total': total_count,
            'successes': total_count - failure_count,
            'failures': failure_count,
            'failure_rate': failure_rate,
            'error_breakdown': error_breakdown
        }
        
        self.report_data['failure_analysis'] = result
        
        logger.info(f"Failure analysis: {failure_rate:.1f}% failure rate ({failure_count}/{total_count})")
        return result
    
    def analyze_accuracy_metrics(self) -> Dict[str, Dict[str, float]]:
        """Analyze accuracy metrics with confidence intervals.
        
        Returns:
            Dictionary with stats for CER, WER, IoU, etc.
        """
        metrics = {}
        
        # Analyze available accuracy columns
        accuracy_columns = ['cer', 'wer', 'iou', 'table_precision']
        
        for col in accuracy_columns:
            if col in self.df.columns:
                # Remove NaN values
                data = self.df[col].dropna().tolist()
                
                if data:
                    metrics[col] = self.calculate_confidence_interval(data)
                    logger.info(f"{col.upper()}: {metrics[col]['mean']:.3f} ± {metrics[col]['std_dev']:.3f}")
        
        self.report_data['accuracy_metrics'] = metrics
        return metrics
    
    def plot_latency_distribution(self, output_dir: Path) -> None:
        """Generate box plot of processing time by document type.
        
        Args:
            output_dir: Directory to save the plot
        """
        if 'processing_time' not in self.df.columns:
            logger.warning("Cannot plot latency: no processing_time column")
            return
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        plt.figure(figsize=(12, 6))
        
        if 'doc_type' in self.df.columns and self.df['doc_type'].nunique() > 1:
            # Box plot by document type
            sns.boxplot(data=self.df, x='doc_type', y='processing_time', palette='Set2')
            plt.xlabel('Document Type')
        else:
            # Single box plot for all documents
            sns.boxplot(y=self.df['processing_time'], palette='Set2')
            plt.xlabel('All Documents')
        
        plt.ylabel('Processing Time (seconds)')
        plt.title('Processing Time Distribution by Document Type')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        output_path = output_dir / 'latency_distribution.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.success(f"Latency distribution plot saved: {output_path}")
    
    def plot_accuracy_metrics(self, output_dir: Path) -> None:
        """Generate visualization of accuracy metrics.
        
        Args:
            output_dir: Directory to save the plot
        """
        # Find available accuracy columns
        accuracy_columns = [col for col in ['cer', 'wer', 'iou', 'table_precision'] 
                           if col in self.df.columns]
        
        if not accuracy_columns:
            logger.warning("Cannot plot accuracy: no accuracy columns found")
            return
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subplots for each metric
        n_metrics = len(accuracy_columns)
        fig, axes = plt.subplots(1, n_metrics, figsize=(6 * n_metrics, 5))
        
        if n_metrics == 1:
            axes = [axes]
        
        for idx, col in enumerate(accuracy_columns):
            data = self.df[col].dropna()
            
            if len(data) > 0:
                # Histogram with KDE
                sns.histplot(data, kde=True, ax=axes[idx], color='skyblue', bins=20)
                axes[idx].set_xlabel(col.upper())
                axes[idx].set_ylabel('Frequency')
                axes[idx].set_title(f'{col.upper()} Distribution\nMean: {data.mean():.3f}')
                axes[idx].axvline(data.mean(), color='red', linestyle='--', label='Mean')
                axes[idx].legend()
        
        plt.tight_layout()
        
        output_path = output_dir / 'accuracy_metrics.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.success(f"Accuracy metrics plot saved: {output_path}")
    
    def plot_failure_rates(self, output_dir: Path) -> None:
        """Generate visualization of success vs failure rates.
        
        Args:
            output_dir: Directory to save the plot
        """
        if 'status' not in self.df.columns:
            logger.warning("Cannot plot failures: no status column")
            return
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Analyze failures
        failure_stats = self.analyze_failures()
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Pie chart: Success vs Failure
        sizes = [failure_stats['successes'], failure_stats['failures']]
        labels = ['Success', 'Failure']
        colors = ['#10B981', '#EF4444']
        explode = (0.05, 0.05)
        
        ax1.pie(sizes, explode=explode, labels=labels, colors=colors,
                autopct='%1.1f%%', shadow=True, startangle=90)
        ax1.set_title(f'Overall Success Rate\n({failure_stats["successes"]}/{failure_stats["total"]} tests passed)')
        
        # Bar chart: Failure breakdown by error type
        error_breakdown = failure_stats.get('error_breakdown', {})
        
        if error_breakdown:
            error_types = list(error_breakdown.keys())
            error_counts = list(error_breakdown.values())
            
            ax2.bar(error_types, error_counts, color='#F59E0B')
            ax2.set_xlabel('Error Type')
            ax2.set_ylabel('Count')
            ax2.set_title('Failure Breakdown by Error Type')
            ax2.tick_params(axis='x', rotation=45)
        else:
            ax2.text(0.5, 0.5, 'No failure details available',
                    ha='center', va='center', fontsize=12)
            ax2.set_xlim(0, 1)
            ax2.set_ylim(0, 1)
        
        plt.tight_layout()
        
        output_path = output_dir / 'failure_rates.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.success(f"Failure rates plot saved: {output_path}")
    
    def generate_report(self, output_dir: Path) -> Dict[str, Any]:
        """Generate complete statistical report with visualizations.
        
        Args:
            output_dir: Directory to save report files
            
        Returns:
            Dictionary containing all analysis results
        """
        logger.info("Generating comprehensive benchmark report...")
        
        # Create figures directory
        figures_dir = output_dir / 'figures'
        figures_dir.mkdir(parents=True, exist_ok=True)
        
        # Run all analyses
        self.analyze_processing_time()
        self.analyze_failures()
        self.analyze_accuracy_metrics()
        
        # Generate all plots
        self.plot_latency_distribution(figures_dir)
        self.plot_accuracy_metrics(figures_dir)
        self.plot_failure_rates(figures_dir)
        
        logger.success(f"Report generated in: {output_dir}")
        
        return self.report_data
    
    def print_statistical_summary(self) -> None:
        """Print formatted statistical summary to console using tabulate."""
        from tabulate import tabulate
        
        print("\n" + "="*80)
        print("📊 STATISTICAL SUMMARY")
        print("="*80)
        
        # Accuracy metrics with confidence intervals
        if 'accuracy_metrics' in self.report_data:
            print("\n📈 Accuracy Metrics (95% Confidence Interval):\n")
            
            accuracy_table = []
            for metric, stats in self.report_data['accuracy_metrics'].items():
                accuracy_table.append([
                    metric.upper(),
                    f"{stats['mean']:.4f}",
                    f"±{stats['std_dev']:.4f}",
                    f"[{stats['ci_lower']:.4f}, {stats['ci_upper']:.4f}]"
                ])
            
            print(tabulate(
                accuracy_table,
                headers=['Metric', 'Mean', 'Std Dev', '95% CI'],
                tablefmt='grid'
            ))
        
        # Latency statistics
        if 'latency_analysis' in self.report_data:
            print("\n⏱️  Processing Time Analysis:\n")
            
            latency_df = self.report_data['latency_analysis']
            print(tabulate(
                latency_df,
                headers='keys',
                tablefmt='grid',
                floatfmt='.2f',
                showindex=False
            ))
        
        # Failure analysis
        if 'failure_analysis' in self.report_data:
            failure_stats = self.report_data['failure_analysis']
            
            print("\n🔍 Failure Analysis:\n")
            print(f"  Total Tests: {failure_stats['total']}")
            print(f"  Successes: {failure_stats['successes']} ({100 - failure_stats['failure_rate']:.1f}%)")
            print(f"  Failures: {failure_stats['failures']} ({failure_stats['failure_rate']:.1f}%)")
            
            if failure_stats['error_breakdown']:
                print("\n  Error Breakdown:")
                for error_type, count in failure_stats['error_breakdown'].items():
                    print(f"    - {error_type}: {count}")
        
        print("\n" + "="*80 + "\n")
