"""
Test Document Scenarios for Claims Processing Framework

This file contains test data structures and GCS URIs for testing document processing agents.
Use these scenarios to test Document AI, Vision AI, and RAG processing capabilities.
"""

import json
from datetime import datetime, timedelta

# Test GCS bucket for documents
TEST_BUCKET = "gs://test-claims-bucket/documents"

# Test document scenarios
TEST_SCENARIOS = {
    "CLM-2025-001": {
        "claim_id": "CLM-2025-001",
        "description": "Minor fender bender with injuries",
        "incident_date": "2025-01-15",
        "policy_id": "POL-HTF-789012",
        "claimant": "Michael Thompson",
        "documents": {
            "police_report": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-001/police_report/accident_report_PR-2025-0856.pdf",
                "document_type": "police_report",
                "upload_date": "2025-01-15",
                "description": "Official police report from Hartford PD",
                "test_file": "sample_police_report.txt"
            },
            "body_shop_estimate": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-001/estimates/mikes_auto_body_estimate.pdf", 
                "document_type": "estimate",
                "upload_date": "2025-01-16",
                "description": "Repair estimate from Mike's Auto Body",
                "test_file": "sample_body_shop_estimate.txt"
            },
            "medical_bill": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-001/medical/hartford_hospital_bill.pdf",
                "document_type": "medical_record",
                "upload_date": "2025-01-16", 
                "description": "Emergency room bill from Hartford Hospital",
                "test_file": "sample_medical_bill.txt"
            },
            "damage_photos": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-001/photos/front_damage_01.jpg",
                    "description": "Front-end collision damage",
                    "analysis_type": "damage_assessment"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-001/photos/airbag_deployment.jpg",
                    "description": "Deployed airbags in driver compartment",
                    "analysis_type": "damage_assessment"
                }
            ],
            "audio_statement": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-001/audio/claimant_statement.wav",
                "description": "Recorded statement from claimant",
                "language_code": "en-US"
            }
        }
    },
    
    "CLM-2025-002": {
        "claim_id": "CLM-2025-002", 
        "description": "Major collision with multiple vehicles",
        "incident_date": "2025-01-18",
        "policy_id": "POL-HTF-445566",
        "claimant": "Sarah Wilson",
        "documents": {
            "police_report": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-002/police_report/multi_vehicle_accident.pdf",
                "document_type": "police_report",
                "upload_date": "2025-01-18",
                "description": "Multi-vehicle accident report"
            },
            "witness_statements": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-002/statements/witness_1_statement.pdf",
                    "description": "Witness statement from John Doe"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-002/statements/witness_2_statement.pdf", 
                    "description": "Witness statement from Jane Smith"
                }
            ],
            "damage_photos": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-002/photos/total_loss_vehicle.jpg",
                    "description": "Vehicle declared total loss",
                    "analysis_type": "damage_assessment"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-002/photos/scene_overview.jpg",
                    "description": "Accident scene overview",
                    "analysis_type": "scene_analysis"
                }
            ]
        }
    },
    
    "CLM-2025-003": {
        "claim_id": "CLM-2025-003",
        "description": "Suspicious fraud case - staged accident",
        "incident_date": "2025-01-20",
        "policy_id": "POL-HTF-998877", 
        "claimant": "Robert Johnson",
        "fraud_indicators": [
            "Policy purchased 2 days before incident",
            "Claimant has 4 previous claims in 6 months",
            "Damage inconsistent with reported incident",
            "Repair shop has history of inflated estimates"
        ],
        "documents": {
            "police_report": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-003/police_report/suspicious_incident.pdf",
                "document_type": "police_report",
                "upload_date": "2025-01-25",  # 5 days late
                "description": "Police report with inconsistent details"
            },
            "inflated_estimate": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-003/estimates/shady_auto_estimate.pdf",
                "document_type": "estimate", 
                "upload_date": "2025-01-21",
                "description": "Suspiciously high repair estimate",
                "estimated_cost": 25000  # Very high for minor damage
            },
            "staged_photos": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-003/photos/minimal_damage.jpg",
                    "description": "Minimal visible damage",
                    "analysis_type": "damage_assessment"
                }
            ]
        }
    },
    
    "CLM-2025-004": {
        "claim_id": "CLM-2025-004",
        "description": "Comprehensive claim for RAG testing",
        "incident_date": "2025-01-22",
        "policy_id": "POL-HTF-112233",
        "claimant": "Maria Rodriguez",
        "documents": {
            "police_report": {
                "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/police_report/detailed_accident_report.pdf",
                "document_type": "police_report"
            },
            "medical_records": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/medical/emergency_room_visit.pdf",
                    "document_type": "medical_record"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/medical/physical_therapy_bill.pdf", 
                    "document_type": "medical_record"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/medical/orthopedic_consultation.pdf",
                    "document_type": "medical_record"
                }
            ],
            "estimates": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/estimates/body_shop_estimate_1.pdf",
                    "document_type": "estimate"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/estimates/body_shop_estimate_2.pdf",
                    "document_type": "estimate"
                }
            ],
            "photos": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/photos/vehicle_damage_front.jpg",
                    "analysis_type": "damage_assessment"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/photos/vehicle_damage_side.jpg", 
                    "analysis_type": "damage_assessment"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/photos/accident_scene.jpg",
                    "analysis_type": "scene_analysis"
                }
            ],
            "audio_files": [
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/audio/claimant_interview.wav",
                    "description": "Initial claimant interview"
                },
                {
                    "gcs_uri": f"{TEST_BUCKET}/CLM-2025-004/audio/witness_statement.wav",
                    "description": "Witness phone interview"
                }
            ]
        }
    }
}

# Test functions for agent interaction
def get_test_document_uri(claim_id: str, document_type: str) -> str:
    """Get a test document URI for a specific claim and document type"""
    if claim_id in TEST_SCENARIOS:
        documents = TEST_SCENARIOS[claim_id]["documents"]
        if document_type in documents:
            return documents[document_type]["gcs_uri"]
    return None

def get_test_claim_documents(claim_id: str) -> dict:
    """Get all documents for a test claim"""
    return TEST_SCENARIOS.get(claim_id, {}).get("documents", {})

def get_fraud_test_case() -> dict:
    """Get the suspicious fraud test case"""
    return TEST_SCENARIOS["CLM-2025-003"]

def get_comprehensive_test_case() -> dict:
    """Get the comprehensive test case for RAG testing"""
    return TEST_SCENARIOS["CLM-2025-004"]

# Agent testing commands
AGENT_TEST_COMMANDS = {
    "document_extraction": [
        "extract_from_document('gs://test-claims-bucket/documents/CLM-2025-001/police_report/accident_report_PR-2025-0856.pdf', 'police_report')",
        "extract_from_document('gs://test-claims-bucket/documents/CLM-2025-001/estimates/mikes_auto_body_estimate.pdf', 'estimate')",
        "extract_from_document('gs://test-claims-bucket/documents/CLM-2025-001/medical/hartford_hospital_bill.pdf', 'medical_record')"
    ],
    
    "image_analysis": [
        "extract_from_image('gs://test-claims-bucket/documents/CLM-2025-001/photos/front_damage_01.jpg', 'damage_assessment')",
        "extract_from_image('gs://test-claims-bucket/documents/CLM-2025-002/photos/total_loss_vehicle.jpg', 'damage_assessment')"
    ],
    
    "audio_transcription": [
        "transcribe_audio('gs://test-claims-bucket/documents/CLM-2025-001/audio/claimant_statement.wav', 'en-US')",
        "transcribe_audio('gs://test-claims-bucket/documents/CLM-2025-004/audio/claimant_interview.wav', 'en-US')"
    ],
    
    "hybrid_processing": [
        "process_document_with_hybrid_approach('gs://test-claims-bucket/documents/CLM-2025-001/police_report/accident_report_PR-2025-0856.pdf', 'CLM-2025-001', 'police_report')",
        "process_document_with_hybrid_approach('gs://test-claims-bucket/documents/CLM-2025-004/estimates/body_shop_estimate_1.pdf', 'CLM-2025-004', 'estimate')"
    ],
    
    "rag_analysis": [
        "analyze_claim_documents_intelligently('CLM-2025-004', 'comprehensive')",
        "analyze_claim_documents_intelligently('CLM-2025-003', 'fraud_detection')",
        "analyze_claim_documents_intelligently('CLM-2025-001', 'settlement_preparation')"
    ],
    
    "fraud_detection": [
        "check_claimant_history('POL-HTF-998877', 'Robert Johnson', '(860) 555-9999')",
        "analyze_incident_timing('2025-01-20', '2025-01-25', '2025-01-18')",  # Suspicious timing
        "calculate_ml_fraud_score({'claim_id': 'CLM-2025-003', 'policy_id': 'POL-HTF-998877', 'estimated_damage': 25000, 'incident_date': '2025-01-20', 'reported_date': '2025-01-25', 'claimant_age': 28, 'claim_type': 'collision', 'description': 'Minor rear-end collision'})"
    ]
}

if __name__ == "__main__":
    # Print test scenarios for reference
    print("=== CLAIMS PROCESSING TEST SCENARIOS ===\n")
    
    for claim_id, scenario in TEST_SCENARIOS.items():
        print(f"CLAIM: {claim_id}")
        print(f"Description: {scenario['description']}")
        print(f"Documents: {len(scenario['documents'])} types")
        if 'fraud_indicators' in scenario:
            print(f"Fraud Indicators: {len(scenario['fraud_indicators'])}")
        print()
    
    print("=== SAMPLE AGENT COMMANDS ===\n")
    
    for category, commands in AGENT_TEST_COMMANDS.items():
        print(f"{category.upper().replace('_', ' ')}:")
        for cmd in commands:
            print(f"  {cmd}")
        print()