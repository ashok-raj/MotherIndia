#!/usr/bin/env python3
"""
Invoice and Receipt Processing Script for Mother India Foods LLC
Extracts item information and tracks price changes over time from both invoices and receipts

Usage:
    python process_invoices.py                    # Process only invoices
    python process_invoices.py /path/to/receipts  # Process invoices and receipts
"""

import os
import re
import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
import pdfplumber
from typing import List, Dict, Tuple
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

class InvoiceProcessor:
    def __init__(self, invoice_dir: str = "Invoices", receipts_dir: str = None):
        self.invoice_dir = Path(invoice_dir)
        self.receipts_dir = Path(receipts_dir) if receipts_dir else None
        self.items_file = "invoice_items.csv"
        self.receipt_items_file = "receipt_items.csv"
        self.combined_items_file = "combined_items.csv"
        self.price_tracking_file = "price_tracking.csv"
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
    
    def parse_invoice_date(self, text: str) -> str:
        """Extract invoice date from PDF text"""
        date_match = re.search(r'DATE\s+(\d{2}/\d{2}/\d{4})', text)
        if date_match:
            return date_match.group(1)
        return ""
    
    def parse_invoice_number(self, text: str) -> str:
        """Extract invoice number from PDF text"""
        invoice_match = re.search(r'INVOICE\s+(\d+)', text)
        if invoice_match:
            return invoice_match.group(1)
        return ""
    
    def parse_line_items(self, text: str) -> List[Dict]:
        """Extract line items from invoice text"""
        items = []
        
        # Find the section with items (between DESCRIPTION and VERIFIED/EMAILED)
        lines = text.split('\n')
        in_items_section = False
        
        for line in lines:
            line = line.strip()
            
            # Start capturing items after the header
            if 'DESCRIPTION' in line and 'QTY' in line and 'RATE' in line:
                in_items_section = True
                continue
                
            # Stop at payment/total section
            if 'VERIFIED' in line or 'TOTAL DUE' in line or 'PAYMENT' in line:
                in_items_section = False
                continue
            
            if not in_items_section or not line:
                continue
            
            # Parse item line - format: DESCRIPTION QTY RATE AMOUNT
            # Use regex to capture the components
            item_match = re.match(r'^(.+?)\s+(\d+)\s+([\d.]+)\s+([\d.]+)$', line)
            
            if item_match:
                description = item_match.group(1).strip()
                
                # Filter out unwanted items containing these terms
                skip_terms = ['BILL TO', 'SHIP TO', 'INVOICE']
                if any(term in description.upper() for term in skip_terms):
                    continue
                
                quantity = int(item_match.group(2))
                rate = float(item_match.group(3))
                amount = float(item_match.group(4))
                
                items.append({
                    'description': description,
                    'quantity': quantity,
                    'rate': rate,
                    'amount': amount
                })
        
        return items
    
    def process_single_invoice(self, pdf_path: str) -> Dict:
        """Process a single PDF invoice"""
        print(f"Processing: {pdf_path}")
        
        text = self.extract_text_from_pdf(pdf_path)
        
        invoice_data = {
            'file_name': os.path.basename(pdf_path),
            'invoice_number': self.parse_invoice_number(text),
            'date': self.parse_invoice_date(text),
            'items': self.parse_line_items(text)
        }
        
        return invoice_data
    
    def process_all_invoices(self) -> List[Dict]:
        """Process all PDF invoices in the directory"""
        invoices = []
        
        pdf_files = list(self.invoice_dir.glob("*.pdf"))
        pdf_files.sort()  # Process in order
        
        for pdf_file in pdf_files:
            try:
                invoice_data = self.process_single_invoice(str(pdf_file))
                invoices.append(invoice_data)
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
        
        return invoices
    
    def parse_receipt_date(self, text: str) -> str:
        """Extract receipt date from PDF text - more flexible date patterns"""
        # Try various date formats common in receipts
        date_patterns = [
            r'DATE\s+(\d{2}/\d{2}/\d{4})',  # DATE MM/DD/YYYY
            r'Date:\s*(\d{2}/\d{2}/\d{4})',  # Date: MM/DD/YYYY
            r'(\d{2}/\d{2}/\d{4})',  # Just MM/DD/YYYY
            r'(\d{1,2}/\d{1,2}/\d{4})',  # M/D/YYYY or MM/D/YYYY
            r'(\d{2}-\d{2}-\d{4})',  # MM-DD-YYYY
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, text)
            if date_match:
                return date_match.group(1)
        return ""
    
    def parse_receipt_number(self, text: str) -> str:
        """Extract receipt/reference number from PDF text"""
        # Try various receipt number patterns
        receipt_patterns = [
            r'RECEIPT\s+(\d+)',  # RECEIPT 12345
            r'Receipt\s*#?\s*(\d+)',  # Receipt #12345 or Receipt 12345
            r'REF\s*#?\s*(\d+)',  # REF #12345
            r'Reference\s*#?\s*(\d+)',  # Reference #12345
        ]
        
        for pattern in receipt_patterns:
            receipt_match = re.search(pattern, text)
            if receipt_match:
                return receipt_match.group(1)
        return ""
    
    def parse_receipt_items(self, text: str) -> List[Dict]:
        """Extract line items from receipt text - more flexible parsing"""
        items = []
        lines = text.split('\n')
        
        # Look for item patterns - receipts often have different formats
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Pattern 1: Item name followed by quantity and price
            # e.g., "BASMATI RICE 5LB 2 12.99"
            item_match1 = re.match(r'^(.+?)\s+(\d+)\s+([\d.]+)$', line)
            if item_match1:
                description = item_match1.group(1).strip()
                
                # Filter out unwanted items containing these terms
                skip_terms = ['BILL TO', 'SHIP TO', 'INVOICE']
                if any(term in description.upper() for term in skip_terms):
                    continue
                
                quantity = int(item_match1.group(2))
                amount = float(item_match1.group(3))
                rate = amount / quantity if quantity > 0 else amount
                
                items.append({
                    'description': description,
                    'quantity': quantity,
                    'rate': rate,
                    'amount': amount
                })
                continue
            
            # Pattern 2: Item name with just total amount
            # e.g., "TURMERIC POWDER 8.99"
            item_match2 = re.match(r'^(.+?)\s+([\d.]+)$', line)
            if item_match2 and len(item_match2.group(1)) > 3:  # Avoid matching short codes
                description = item_match2.group(1).strip()
                amount = float(item_match2.group(2))
                
                # Skip lines that look like totals, tax, etc.
                skip_terms = ['TOTAL', 'TAX', 'SUBTOTAL', 'PAYMENT', 'CHANGE', 'CASH', 'CREDIT', 'BILL TO', 'SHIP TO', 'INVOICE']
                if not any(term in description.upper() for term in skip_terms):
                    items.append({
                        'description': description,
                        'quantity': 1,
                        'rate': amount,
                        'amount': amount
                    })
        
        return items
    
    def process_single_receipt(self, pdf_path: str) -> Dict:
        """Process a single PDF receipt"""
        print(f"Processing receipt: {pdf_path}")
        
        text = self.extract_text_from_pdf(pdf_path)
        
        receipt_data = {
            'file_name': os.path.basename(pdf_path),
            'receipt_number': self.parse_receipt_number(text),
            'date': self.parse_receipt_date(text),
            'items': self.parse_receipt_items(text),
            'type': 'receipt'
        }
        
        return receipt_data
    
    def process_all_receipts(self) -> List[Dict]:
        """Process all PDF receipts in the receipts directory"""
        if not self.receipts_dir or not self.receipts_dir.exists():
            print("No receipts directory specified or found.")
            return []
        
        receipts = []
        pdf_files = list(self.receipts_dir.glob("*.pdf"))
        pdf_files.sort()  # Process in order
        
        print(f"Found {len(pdf_files)} receipt files to process")
        
        for pdf_file in pdf_files:
            try:
                receipt_data = self.process_single_receipt(str(pdf_file))
                receipts.append(receipt_data)
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
        
        return receipts
    
    def save_items_data(self, invoices: List[Dict]):
        """Save all items data to CSV"""
        items_data = []
        
        for invoice in invoices:
            for item in invoice['items']:
                items_data.append({
                    'invoice_number': invoice['invoice_number'],
                    'date': invoice['date'],
                    'file_name': invoice['file_name'],
                    'item_name': item['description'],
                    'quantity': item['quantity'],
                    'rate_per_item': item['rate'],
                    'total_amount': item['amount']
                })
        
        df = pd.DataFrame(items_data)
        df.to_csv(self.items_file, index=False)
        print(f"Saved {len(items_data)} invoice items to {self.items_file}")
    
    def save_receipt_data(self, receipts: List[Dict]):
        """Save all receipt data to CSV"""
        if not receipts:
            print("No receipts to save")
            return
        
        receipt_data = []
        for receipt in receipts:
            for item in receipt['items']:
                receipt_data.append({
                    'receipt_number': receipt['receipt_number'],
                    'date': receipt['date'],
                    'file_name': receipt['file_name'],
                    'item_name': item['description'],
                    'quantity': item['quantity'],
                    'rate_per_item': item['rate'],
                    'total_amount': item['amount'],
                    'type': 'receipt'
                })
        
        df = pd.DataFrame(receipt_data)
        df.to_csv(self.receipt_items_file, index=False)
        print(f"Saved {len(receipt_data)} receipt items to {self.receipt_items_file}")
    
    def save_combined_data(self, invoices: List[Dict], receipts: List[Dict]):
        """Save combined invoice and receipt data to CSV"""
        combined_data = []
        
        # Add invoice data
        for invoice in invoices:
            for item in invoice['items']:
                combined_data.append({
                    'document_number': invoice['invoice_number'],
                    'date': invoice['date'],
                    'file_name': invoice['file_name'],
                    'item_name': item['description'],
                    'quantity': item['quantity'],
                    'rate_per_item': item['rate'],
                    'total_amount': item['amount'],
                    'type': 'invoice'
                })
        
        # Add receipt data
        for receipt in receipts:
            for item in receipt['items']:
                combined_data.append({
                    'document_number': receipt['receipt_number'],
                    'date': receipt['date'],
                    'file_name': receipt['file_name'],
                    'item_name': item['description'],
                    'quantity': item['quantity'],
                    'rate_per_item': item['rate'],
                    'total_amount': item['amount'],
                    'type': 'receipt'
                })
        
        df = pd.DataFrame(combined_data)
        df.to_csv(self.combined_items_file, index=False)
        print(f"Saved {len(combined_data)} combined items (invoices + receipts) to {self.combined_items_file}")
    
    def save_individual_invoice_csvs(self, invoices: List[Dict]):
        """Save individual CSV files for each invoice"""
        for invoice in invoices:
            if not invoice['items']:
                continue
                
            # Create CSV filename from PDF filename
            pdf_name = invoice['file_name']
            csv_name = pdf_name.replace('.pdf', '.csv')
            csv_path = os.path.join(self.invoice_dir, csv_name)
            
            # Prepare data for this invoice
            invoice_items = []
            for item in invoice['items']:
                invoice_items.append({
                    'item_name': item['description'],
                    'quantity': item['quantity'],
                    'rate_per_item': item['rate'],
                    'total_amount': item['amount']
                })
            
            # Save to CSV
            df = pd.DataFrame(invoice_items)
            df.to_csv(csv_path, index=False)
            print(f"Saved individual invoice CSV: {csv_path}")
        
        print(f"Created {len(invoices)} individual invoice CSV files")
    
    def create_price_tracking(self, invoices: List[Dict], receipts: List[Dict] = None):
        """Create price tracking file for comparison including both invoices and receipts"""
        price_data = []
        
        # Add invoice data
        for invoice in invoices:
            for item in invoice['items']:
                price_data.append({
                    'date': invoice['date'],
                    'item_name': item['description'],
                    'price_per_item': item['rate'],
                    'document_number': invoice['invoice_number'],
                    'document_type': 'invoice'
                })
        
        # Add receipt data if available
        if receipts:
            for receipt in receipts:
                for item in receipt['items']:
                    price_data.append({
                        'date': receipt['date'],
                        'item_name': item['description'],
                        'price_per_item': item['rate'],
                        'document_number': receipt['receipt_number'],
                        'document_type': 'receipt'
                    })
        
        df = pd.DataFrame(price_data)
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y', errors='coerce')
            df = df.dropna(subset=['date'])  # Remove rows with invalid dates
            df = df.sort_values(['item_name', 'date'])
        
        df.to_csv(self.price_tracking_file, index=False)
        print(f"Saved price tracking data to {self.price_tracking_file}")
        
        return df
    
    def analyze_price_changes(self, price_df: pd.DataFrame):
        """Analyze price changes and calculate percentage increases"""
        price_changes = []
        
        for item_name in price_df['item_name'].unique():
            item_prices = price_df[price_df['item_name'] == item_name].copy()
            item_prices = item_prices.sort_values('date')
            
            if len(item_prices) > 1:
                for i in range(1, len(item_prices)):
                    prev_price = item_prices.iloc[i-1]['price_per_item']
                    curr_price = item_prices.iloc[i]['price_per_item']
                    
                    if prev_price != curr_price:
                        percentage_change = ((curr_price - prev_price) / prev_price) * 100
                        
                        price_changes.append({
                            'item_name': item_name,
                            'previous_date': item_prices.iloc[i-1]['date'].strftime('%m/%d/%Y'),
                            'current_date': item_prices.iloc[i]['date'].strftime('%m/%d/%Y'),
                            'previous_price': prev_price,
                            'current_price': curr_price,
                            'price_change': curr_price - prev_price,
                            'percentage_change': round(percentage_change, 2)
                        })
        
        if price_changes:
            changes_df = pd.DataFrame(price_changes)
            changes_df.to_csv('price_changes.csv', index=False)
            print(f"Saved {len(price_changes)} price changes to price_changes.csv")
            
            # Show summary
            print("\nPrice Change Summary:")
            print(f"Items with price increases: {len(changes_df[changes_df['percentage_change'] > 0])}")
            print(f"Items with price decreases: {len(changes_df[changes_df['percentage_change'] < 0])}")
            
            if len(changes_df) > 0:
                print(f"Average price change: {changes_df['percentage_change'].mean():.2f}%")
                print(f"Largest price increase: {changes_df['percentage_change'].max():.2f}%")
                print(f"Largest price decrease: {changes_df['percentage_change'].min():.2f}%")
        else:
            print("No price changes detected across invoices")
    
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
    
    def generate_price_report(self):
        """Generate the complete PDF report"""
        # Load data
        data = self.load_price_data()
        if data is None or len(data) == 0:
            print("No price increases found to report.")
            return
        
        print(f"Generating PDF report for {len(data)} price increases...")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            "price_increase_report.pdf",
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
        print(f"Report generated successfully: price_increase_report.pdf")
        
        # Show summary
        print(f"\\nReport Summary:")
        print(f"- Total price increases: {len(data)}")
        print(f"- Average increase: {data['percentage_change'].mean():.2f}%")
        print(f"- Largest increase: {data['percentage_change'].max():.2f}% ({data.loc[data['percentage_change'].idxmax(), 'item_name']})")
    
    def run(self):
        """Main processing function"""
        print("Starting invoice and receipt processing...")
        
        # Process all invoices
        invoices = self.process_all_invoices()
        print(f"Processed {len(invoices)} invoices")
        
        # Process all receipts
        receipts = self.process_all_receipts()
        print(f"Processed {len(receipts)} receipts")
        
        if not invoices and not receipts:
            print("No invoices or receipts found to process")
            return
        
        # Save items data
        if invoices:
            self.save_items_data(invoices)
            # Save individual invoice CSVs
            self.save_individual_invoice_csvs(invoices)
        
        if receipts:
            self.save_receipt_data(receipts)
        
        # Save combined data if we have both
        if invoices or receipts:
            self.save_combined_data(invoices, receipts)
        
        # Create price tracking (including both invoices and receipts)
        price_df = self.create_price_tracking(invoices, receipts)
        
        # Analyze price changes
        self.analyze_price_changes(price_df)
        
        # Generate PDF report
        self.generate_price_report()
        
        print("\nProcessing complete!")
        print(f"Files generated:")
        if invoices:
            print(f"- {self.items_file}: All invoice items with details")
        if receipts:
            print(f"- {self.receipt_items_file}: All receipt items with details")
        if invoices or receipts:
            print(f"- {self.combined_items_file}: Combined invoice and receipt items")
        print(f"- {self.price_tracking_file}: Price tracking data")
        print(f"- price_changes.csv: Price change analysis")
        print(f"- price_increase_report.pdf: Price increase report")


if __name__ == "__main__":
    import sys
    
    # Check for command-line arguments
    receipts_dir = None
    if len(sys.argv) > 1:
        receipts_dir = sys.argv[1]
        print(f"Using receipts directory: {receipts_dir}")
    
    processor = InvoiceProcessor(receipts_dir=receipts_dir)
    processor.run()