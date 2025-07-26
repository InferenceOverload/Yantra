# Test Documents for Claims Processing

This directory contains sample documents for testing the claims processing agents:

## Document Types

### 1. Police Reports (`police_reports/`)
- Traffic accident reports
- Incident documentation
- Officer statements

### 2. Medical Bills (`medical_bills/`)
- Hospital invoices
- Treatment records
- Therapy bills

### 3. Body Shop Reports (`body_shop_reports/`)
- Damage estimates
- Repair invoices
- Parts lists

### 4. Photos (`photos/`)
- Vehicle damage photos
- Accident scene images
- Property damage

### 5. Audio Files (`audio/`)
- Recorded statements
- Customer calls
- Witness interviews

## GCS URIs Format
All test documents should use the format:
`gs://test-claims-bucket/documents/{claim_id}/{document_type}/{filename}`

## Test Claims
- CLM-2025-001: Minor fender bender
- CLM-2025-002: Major collision with injuries
- CLM-2025-003: Suspicious fraud case
- CLM-2025-004: Comprehensive claim with multiple documents