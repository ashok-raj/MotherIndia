#!/usr/bin/env python3
"""
Price Increase Report Generator
Creates a formatted PDF report showing price increases with item details
"""

import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os

class PriceReportGenerator:
    def __init__(self):
        self.report_file = "price_increase_report.pdf"
        
    def load_price_data(self):
        """Load price changes data"""
        if not os.path.exists('price_changes.csv'):
            print("Error: price_changes.csv not found. Please run process_invoices.py first.")
            return None
            
        df = pd.read_csv('price_changes.csv')
        # Filter for price increases only
        increases = df[df['percentage_change'] > 0].copy()
        # Sort by percentage change descending
        increases = increases.sort_values('percentage_change', ascending=False)
        return increases
    
    def create_header(self, story, styles, custom_title):
        """Add report header"""
        title = Paragraph("Mother India Foods LLC - Price Increase Report", custom_title)
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        subtitle = Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal'])
        story.append(subtitle)
        story.append(Spacer(1, 0.3*inch))
    
    def create_summary_section(self, story, styles, data):
        """Add summary statistics"""
        summary_title = Paragraph("Summary", styles['Heading2'])
        story.append(summary_title)
        story.append(Spacer(1, 0.1*inch))
        
        total_increases = len(data)
        avg_increase = data['percentage_change'].mean()
        max_increase = data['percentage_change'].max()
        
        summary_text = f"""
        • Total items with price increases: {total_increases}
        • Average price increase: {avg_increase:.2f}%
        • Largest price increase: {max_increase:.2f}%
        """
        
        summary_para = Paragraph(summary_text, styles['Normal'])
        story.append(summary_para)
        story.append(Spacer(1, 0.3*inch))
    
    def create_price_table(self, story, styles, data):
        """Create formatted table of price increases"""
        table_title = Paragraph("Detailed Price Increases", styles['Heading2'])
        story.append(table_title)
        story.append(Spacer(1, 0.1*inch))
        
        # Prepare table data with shorter column headers
        table_data = [['Item Name', 'Prev Price', 'Prev Date', 'New Price', 'New Date', 'Increase', '% Change']]
        
        for _, row in data.iterrows():
            # Wrap long item names using Paragraph for better formatting
            item_name = row['item_name']
            if len(item_name) > 35:
                item_para = Paragraph(item_name, ParagraphStyle(
                    'ItemName',
                    fontSize=7,
                    leading=8,
                    alignment=TA_LEFT
                ))
            else:
                item_para = item_name
            
            table_data.append([
                item_para,
                f"${row['previous_price']:.2f}",
                row['previous_date'],
                f"${row['current_price']:.2f}",
                row['current_date'],
                f"${row['price_change']:.2f}",
                f"{row['percentage_change']:.2f}%"
            ])
        
        # Create table with better column widths - more space for item names
        table = Table(table_data, colWidths=[2.4*inch, 0.65*inch, 0.85*inch, 0.65*inch, 0.85*inch, 0.65*inch, 0.65*inch])
        
        # Style the table
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('FONTSIZE', (0, 1), (0, -1), 7),  # Smaller font for item names
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Item names left aligned
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Numbers center aligned
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Vertical alignment for wrapped text
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            
            # Grid lines
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Highlighting high increases (>5%)
            ('TEXTCOLOR', (6, 1), (6, -1), colors.red),  # % increase column in red
            ('FONTNAME', (6, 1), (6, -1), 'Helvetica-Bold'),
        ]))
        
        # Highlight rows with high percentage increases
        for i, (_, row) in enumerate(data.iterrows(), 1):
            if row['percentage_change'] > 5:
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.mistyrose),
                ]))
        
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
    
    def create_notes_section(self, story, styles):
        """Add notes and explanation"""
        notes_title = Paragraph("Notes", styles['Heading2'])
        story.append(notes_title)
        story.append(Spacer(1, 0.1*inch))
        
        notes_text = """
        • Prices highlighted in red indicate increases greater than 5%
        • Data extracted from Mother India Foods LLC invoices
        • Only items with price increases are shown in this report
        • Price comparison is based on consecutive invoice dates
        """
        
        notes_para = Paragraph(notes_text, styles['Normal'])
        story.append(notes_para)
    
    def generate_report(self):
        """Generate the complete PDF report"""
        # Load data
        data = self.load_price_data()
        if data is None or len(data) == 0:
            print("No price increases found to report.")
            return
        
        print(f"Generating PDF report for {len(data)} price increases...")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            self.report_file,
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        
        # Build content
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        custom_title = ParagraphStyle(
            name='CustomTitle',
            parent=styles['Title'],
            fontSize=20,
            textColor=colors.darkblue,
            alignment=TA_CENTER,
            spaceAfter=0.3*inch
        )
        
        # Add content sections
        self.create_header(story, styles, custom_title)
        self.create_summary_section(story, styles, data)
        self.create_price_table(story, styles, data)
        self.create_notes_section(story, styles)
        
        # Build PDF
        doc.build(story)
        print(f"Report generated successfully: {self.report_file}")
        
        # Show summary
        print(f"\nReport Summary:")
        print(f"- Total price increases: {len(data)}")
        print(f"- Average increase: {data['percentage_change'].mean():.2f}%")
        print(f"- Largest increase: {data['percentage_change'].max():.2f}% ({data.loc[data['percentage_change'].idxmax(), 'item_name']})")

def main():
    generator = PriceReportGenerator()
    generator.generate_report()

if __name__ == "__main__":
    main()