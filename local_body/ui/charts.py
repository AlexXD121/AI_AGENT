"""Professional analytics chart generation using Plotly.

Provides factory functions for creating interactive visualizations
with consistent dark-theme styling.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def create_composition_chart(region_counts: Dict[str, int]) -> go.Figure:
    """Create donut chart showing document composition by region type.
    
    Args:
        region_counts: Dictionary mapping region types to counts
        
    Returns:
        Configured Plotly figure with dark theme styling
    """
    fig = px.pie(
        names=list(region_counts.keys()),
        values=list(region_counts.values()),
        title="Document Structure by Region Type",
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Blues_r
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        showlegend=True,
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#E5E5E5'
    )
    
    return fig


def create_confidence_chart(page_data: List[Dict[str, Any]]) -> go.Figure:
    """Create grouped bar chart comparing OCR vs Vision confidence scores.
    
    Args:
        page_data: List of dictionaries with keys: Page, OCR Confidence, Source
        
    Returns:
        Configured Plotly figure with grouped bars
    """
    df = pd.DataFrame(page_data)
    
    fig = px.bar(
        df,
        x='Page',
        y='OCR Confidence',
        color='Source',
        title="Confidence Scores Across Pages",
        barmode='group',
        color_discrete_map={'OCR': '#3B82F6', 'Vision': '#8B5CF6'}
    )
    
    fig.update_layout(
        yaxis_title="Confidence Score",
        xaxis_title="Page Number",
        yaxis_range=[0, 1],
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#E5E5E5'
    )
    
    return fig


def create_conflict_scatter(conflict_data: List[Dict[str, Any]]) -> go.Figure:
    """Create scatter plot showing conflict distribution and severity.
    
    Args:
        conflict_data: List of dictionaries with keys: Page, Impact Score, Type, Details
        
    Returns:
        Configured Plotly scatter plot with hover tooltips
    """
    df = pd.DataFrame(conflict_data)
    
    fig = px.scatter(
        df,
        x='Page',
        y='Impact Score',
        color='Type',
        size='Impact Score',
        hover_data=['Details'],
        title="Conflict Severity Distribution",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    fig.update_layout(
        yaxis_title="Impact Score (Severity)",
        xaxis_title="Page Number",
        yaxis_range=[0, 1],
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#E5E5E5'
    )
    
    return fig
