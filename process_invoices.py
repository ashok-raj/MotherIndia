#!/usr/bin/env python3
"""
Invoice Processing Script for Mother India Foods LLC invoices
Extracts item information and tracks price changes over time
"""

import os
import re
import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
import pdfplumber
from typing import List, Dict, Tuple

class InvoiceProcessor:
    def __init__(self, invoice_dir: str = "Invoices"):
        self.invoice_dir = Path(invoice_dir)
        self.items_file = "invoice_items.csv"
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
        print(f"Saved {len(items_data)} items to {self.items_file}")
    
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
    
    def create_price_tracking(self, invoices: List[Dict]):
        """Create price tracking file for comparison"""
        price_data = []
        
        for invoice in invoices:
            for item in invoice['items']:
                price_data.append({
                    'date': invoice['date'],
                    'item_name': item['description'],
                    'price_per_item': item['rate'],
                    'invoice_number': invoice['invoice_number']
                })
        
        df = pd.DataFrame(price_data)
        df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
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
    
    def run(self):
        """Main processing function"""
        print("Starting invoice processing...")
        
        # Process all invoices
        invoices = self.process_all_invoices()
        print(f"Processed {len(invoices)} invoices")
        
        if not invoices:
            print("No invoices found to process")
            return
        
        # Save items data
        self.save_items_data(invoices)
        
        # Save individual invoice CSVs
        self.save_individual_invoice_csvs(invoices)
        
        # Create price tracking
        price_df = self.create_price_tracking(invoices)
        
        # Analyze price changes
        self.analyze_price_changes(price_df)
        
        print("\nProcessing complete!")
        print(f"Files generated:")
        print(f"- {self.items_file}: All invoice items with details")
        print(f"- {self.price_tracking_file}: Price tracking data")
        print(f"- price_changes.csv: Price change analysis")


if __name__ == "__main__":
    processor = InvoiceProcessor()
    processor.run()