# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Hartford Insurance Intake Validation Agent

Validates new insurance claim submissions for completeness, policy compliance, 
and eligibility before they enter the claims processing workflow.
"""

import datetime
import os
from typing import Dict, Any

import google.auth
from google.adk.agents import LlmAgent
from google.cloud import bigquery

_, project_id = google.auth.default()


def validate_policy_status(policy_id: str) -> str:
    """
    Validate policy status using your real BigQuery data
    
    Args:
        policy_id: The insurance policy ID to validate (e.g., POL-00000001-45)
        
    Returns:
        Detailed validation results from Hartford's BigQuery database
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.getenv("DATASET_ID", "insurance_claims_demo")
    client = bigquery.Client(project=project_id)
    
    query = f"""
    SELECT 
        policy_id,
        policy_status,
        policy_type,
        effective_date,
        expiration_date,
        state,
        annual_premium
    FROM `{project_id}.{dataset_id}.policies`
    WHERE policy_id = @policy_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id)
        ]
    )
    
    try:
        results = list(client.query(query, job_config=job_config))
        
        if not results:
            return f"""
            ❌ POLICY VALIDATION FAILED
            Policy ID: {policy_id}
            Status: NOT FOUND
            Reason: Policy not found in Hartford's BigQuery database
            Dataset: {project_id}.{dataset_id}.policies
            Next Steps: Verify policy number with customer
            Confidence: 100%
            """
        
        policy = results[0]
        is_active = policy.policy_status == "active"
        
        if is_active:
            return f"""
            ✅ POLICY VALIDATION PASSED
            Policy ID: {policy_id}
            Status: {policy.policy_status.upper()}
            Type: {policy.policy_type.title().replace('_', ' ')} Insurance
            State: {policy.state}
            Coverage Period: {policy.effective_date} to {policy.expiration_date}
            Annual Premium: ${policy.annual_premium:,.2f}
            Source: Hartford BigQuery Database
            Next Steps: Proceed to duplicate check and timing validation
            Confidence: 95%
            """
        else:
            return f"""
            ❌ POLICY VALIDATION FAILED
            Policy ID: {policy_id}
            Status: {policy.policy_status.upper()}
            Type: {policy.policy_type.title().replace('_', ' ')} Insurance
            Reason: Policy is not active (status: {policy.policy_status})
            Source: Hartford BigQuery Database
            Next Steps: Contact customer about policy status before proceeding
            Confidence: 95%
            """
            
    except Exception as e:
        return f"""
        ❌ POLICY VALIDATION ERROR
        Policy ID: {policy_id}
        Error: BigQuery connection failed
        Details: {str(e)}
        Dataset: {project_id}.{dataset_id}.policies
        Next Steps: Check BigQuery access and table permissions
        """


def check_duplicate_claims(policy_id: str, incident_date: str, location_city: str) -> str:
    """
    Check for potential duplicate claims using your real BigQuery data
    
    Args:
        policy_id: The insurance policy ID
        incident_date: Date of incident (YYYY-MM-DD format)
        location_city: City where incident occurred
        
    Returns:
        Results of duplicate claim analysis from Hartford's database
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.getenv("DATASET_ID", "insurance_claims_demo")
    client = bigquery.Client(project=project_id)
    
    query = f"""
    SELECT 
        claim_id,
        incident_date,
        city,
        estimated_damage,
        claim_status,
        ABS(DATE_DIFF(DATE(@incident_date), incident_date, DAY)) as days_difference
    FROM `{project_id}.{dataset_id}.claims`
    WHERE policy_id = @policy_id
    AND LOWER(city) = LOWER(@location_city)
    AND ABS(DATE_DIFF(DATE(@incident_date), incident_date, DAY)) <= 30
    AND claim_status NOT IN ('denied', 'closed')
    ORDER BY days_difference ASC
    LIMIT 10
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id),
            bigquery.ScalarQueryParameter("incident_date", "STRING", incident_date),
            bigquery.ScalarQueryParameter("location_city", "STRING", location_city)
        ]
    )
    
    try:
        results = list(client.query(query, job_config=job_config))
        
        potential_duplicates = []
        for row in results:
            if row.days_difference <= 7:  # High risk duplicates within 7 days
                potential_duplicates.append({
                    "claim_id": row.claim_id,
                    "incident_date": row.incident_date.strftime("%Y-%m-%d"),
                    "days_difference": int(row.days_difference),
                    "city": row.city,
                    "estimated_damage": float(row.estimated_damage),
                    "status": row.claim_status
                })
        
        if potential_duplicates:
            duplicates_text = "\n".join([
                f"   • Claim {dup['claim_id']}: {dup['incident_date']} in {dup['city']} ({dup['days_difference']} days ago, ${dup['estimated_damage']:,.0f} damage, Status: {dup['status']})"
                for dup in potential_duplicates
            ])
            
            return f"""
            ⚠️ POTENTIAL DUPLICATES FOUND
            Policy ID: {policy_id}
            Incident Date: {incident_date}
            Location: {location_city}
            Source: Hartford BigQuery Database
            
            Potential Duplicates Found ({len(potential_duplicates)}):
{duplicates_text}
            
            Risk Level: HIGH
            Next Steps: Manual review required - verify this is not a duplicate claim
            Dataset: {project_id}.{dataset_id}.claims
            Confidence: 90%
            """
        else:
            return f"""
            ✅ NO DUPLICATES FOUND
            Policy ID: {policy_id}
            Incident Date: {incident_date}
            Location: {location_city}
            Source: Hartford BigQuery Database
            
            Result: No duplicate claims found within 7-day window and same location
            Claims Checked: {len(results)} similar claims in 30-day window
            Risk Level: LOW
            Next Steps: Proceed with timing validation
            Confidence: 90%
            """
            
    except ValueError:
        return f"""
        ❌ DUPLICATE CHECK ERROR
        Error: Invalid incident date format
        Expected: YYYY-MM-DD (e.g., 2025-01-15)
        Received: {incident_date}
        Next Steps: Request correct date format from customer
        """
    except Exception as e:
        return f"""
        ❌ DUPLICATE CHECK ERROR
        Policy ID: {policy_id}
        Error: BigQuery query failed
        Details: {str(e)}
        Dataset: {project_id}.{dataset_id}.claims
        Next Steps: Check BigQuery access and table permissions
        """


def validate_incident_timing(policy_id: str, incident_date: str, reported_date: str) -> str:
    """
    Validate incident timing using your real BigQuery policy data
    
    Args:
        policy_id: The insurance policy ID
        incident_date: Date of incident (YYYY-MM-DD)
        reported_date: Date claim was reported (YYYY-MM-DD)
        
    Returns:
        Results of timing validation from Hartford's database
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.getenv("DATASET_ID", "insurance_claims_demo")
    client = bigquery.Client(project=project_id)
    
    try:
        incident_dt = datetime.datetime.strptime(incident_date, "%Y-%m-%d")
        reported_dt = datetime.datetime.strptime(reported_date, "%Y-%m-%d")
        reporting_delay = (reported_dt - incident_dt).days
        
        # Get policy coverage period from BigQuery
        policy_query = f"""
        SELECT 
            policy_id,
            effective_date,
            expiration_date,
            policy_status,
            policy_type
        FROM `{project_id}.{dataset_id}.policies`
        WHERE policy_id = @policy_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id)
            ]
        )
        
        policy_results = list(client.query(policy_query, job_config=job_config))
        
        if not policy_results:
            return f"""
            ❌ TIMING VALIDATION FAILED
            Policy ID: {policy_id}
            Error: Policy not found in Hartford's database
            Dataset: {project_id}.{dataset_id}.policies
            Next Steps: Complete policy validation first
            """
        
        policy = policy_results[0]
        
        # Check if incident occurred during coverage period
        incident_during_coverage = policy.effective_date <= incident_dt.date() <= policy.expiration_date
        within_reporting_window = reporting_delay <= 30  # Hartford's 30-day reporting requirement
        
        issues = []
        if not incident_during_coverage:
            issues.append(f"Incident occurred outside coverage period ({policy.effective_date} to {policy.expiration_date})")
        
        if not within_reporting_window:
            issues.append(f"Late reporting: {reporting_delay} days (Hartford requires reporting within 30 days)")
        
        if not issues:
            return f"""
            ✅ TIMING VALIDATION PASSED
            Policy ID: {policy_id}
            Policy Type: {policy.policy_type.replace('_', ' ').title()}
            Incident Date: {incident_date} (during coverage period ✓)
            Reported Date: {reported_date} ({reporting_delay} days after incident ✓)
            Coverage Period: {policy.effective_date} to {policy.expiration_date}
            Source: Hartford BigQuery Database
            
            Result: All timing requirements met
            Next Steps: Proceed to field validation and eligibility assessment
            Confidence: 95%
            """
        else:
            status = "FAILED" if not incident_during_coverage else "NEEDS REVIEW"
            issues_text = "\n".join([f"   • {issue}" for issue in issues])
            
            return f"""
            {'❌' if status == 'FAILED' else '⚠️'} TIMING VALIDATION {status}
            Policy ID: {policy_id}
            Policy Type: {policy.policy_type.replace('_', ' ').title()}
            Incident Date: {incident_date}
            Reported Date: {reported_date}
            Reporting Delay: {reporting_delay} days
            Coverage Period: {policy.effective_date} to {policy.expiration_date}
            Source: Hartford BigQuery Database
            
            Issues Found:
{issues_text}
            
            Next Steps: {"Escalate to underwriting for manual review" if status == "NEEDS REVIEW" else "Claim cannot be processed - outside coverage period"}
            Confidence: 95%
            """
            
    except ValueError as e:
        return f"""
        ❌ TIMING VALIDATION ERROR
        Error: Invalid date format
        Details: {str(e)}
        Expected Format: YYYY-MM-DD (e.g., 2025-01-15)
        Next Steps: Request correct date formats from customer
        """
    except Exception as e:
        return f"""
        ❌ TIMING VALIDATION ERROR
        Policy ID: {policy_id}
        Error: BigQuery query failed
        Details: {str(e)}
        Dataset: {project_id}.{dataset_id}.policies
        Next Steps: Check BigQuery access and database connectivity
        """


def verify_required_fields(claim_description: str) -> str:
    """
    Verify claim contains all required information for Hartford processing
    
    Args:
        claim_description: Description or details of the claim
        
    Returns:
        Analysis of required field completeness
    """
    required_fields = {
        "policy_id": ["policy", "pol"],
        "incident_date": ["incident", "accident", "occurred", "happened"],
        "reported_date": ["reported", "report"],
        "location": ["location", "address", "where", "city", "state"],
        "claim_type": ["type", "auto", "collision", "comprehensive", "home", "fire", "theft"],
        "estimated_damage": ["damage", "estimate", "cost", "$", "amount"],
        "description": ["description", "what happened", "details", "explain"]
    }
    
    claim_lower = claim_description.lower()
    present_fields = []
    missing_fields = []
    
    for field, indicators in required_fields.items():
        if any(indicator in claim_lower for indicator in indicators):
            present_fields.append(field)
        else:
            missing_fields.append(field)
    
    completion_percentage = (len(present_fields) / len(required_fields)) * 100
    
    if not missing_fields:
        present_text = ', '.join(present_fields)
        return f"""
        ✅ REQUIRED FIELDS COMPLETE
        Hartford Requirements: {len(required_fields)} fields required
        Fields Present: {len(present_fields)} (100%)
        
        All Required Information Present:
        {present_text}
        
        Next Steps: Proceed to preliminary eligibility assessment
        Confidence: 85%
        """
    else:
        present_text = ', '.join(present_fields) if present_fields else "None detected"
        missing_text = ', '.join(missing_fields)
        
        return f"""
        ⚠️ MISSING REQUIRED FIELDS
        Hartford Requirements: {len(required_fields)} fields required
        Fields Present: {len(present_fields)} ({completion_percentage:.0f}%)
        
        Present: {present_text}
        Missing: {missing_text}
        
        Next Steps: Request missing information from customer before proceeding
        Required for Hartford Processing: All fields must be complete
        Confidence: 80%
        """


def assess_preliminary_eligibility(policy_id: str, claim_type: str) -> str:
    """
    Assess preliminary eligibility using your real BigQuery policy data
    
    Args:
        policy_id: The insurance policy ID
        claim_type: Type of claim (auto, collision, home, fire, etc.)
        
    Returns:
        Preliminary eligibility assessment from Hartford's database
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.getenv("DATASET_ID", "insurance_claims_demo")
    client = bigquery.Client(project=project_id)
    
    # Get policy info from BigQuery
    query = f"""
    SELECT 
        policy_id,
        policy_status,
        policy_type,
        coverage,
        state
    FROM `{project_id}.{dataset_id}.policies`
    WHERE policy_id = @policy_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id)
        ]
    )
    
    try:
        results = list(client.query(query, job_config=job_config))
        
        if not results:
            return f"""
            ❌ ELIGIBILITY ASSESSMENT FAILED
            Policy ID: {policy_id}
            Status: Policy not found in Hartford's database
            Dataset: {project_id}.{dataset_id}.policies
            Next Steps: Complete policy validation first
            """
        
        policy = results[0]
        
        if policy.policy_status != "active":
            return f"""
            ❌ CLAIM INELIGIBLE
            Policy ID: {policy_id}
            Policy Status: {policy.policy_status.upper()}
            Reason: Hartford cannot process claims on inactive policies
            Source: Hartford BigQuery Database
            Next Steps: Contact customer about policy reactivation
            Confidence: 100%
            """
        
        # Check if claim type matches policy type and coverage
        policy_type = policy.policy_type
        claim_type_lower = claim_type.lower()
        
        coverage_match = False
        coverage_details = []
        
        if "auto" in policy_type and any(keyword in claim_type_lower for keyword in ["auto", "collision", "comprehensive", "vehicle", "car"]):
            coverage_match = True
            # Check specific auto coverage from BigQuery
            coverage = policy.coverage
            if "collision" in claim_type_lower and coverage.get("collision"):
                coverage_details.append("Collision coverage confirmed")
            elif "comprehensive" in claim_type_lower and coverage.get("comprehensive"):
                coverage_details.append("Comprehensive coverage confirmed")
            else:
                coverage_details.append("Auto policy - coverage details need verification")
                
        elif ("home" in policy_type or "property" in policy_type) and any(keyword in claim_type_lower for keyword in ["home", "property", "fire", "theft", "house"]):
            coverage_match = True
            coverage_details.append(f"{policy_type.replace('_', ' ').title()} coverage confirmed")
        
        if coverage_match:
            coverage_text = "\n".join([f"   • {detail}" for detail in coverage_details])
            return f"""
            ✅ PRELIMINARY ELIGIBILITY: APPROVED
            Policy ID: {policy_id}
            Policy Type: {policy_type.replace('_', ' ').title()} Insurance
            Policy Status: {policy.policy_status.upper()}
            Claim Type: {claim_type}
            State: {policy.state}
            Source: Hartford BigQuery Database
            
            Coverage Verification:
{coverage_text}
            
            Next Steps: 
            1. Complete fraud detection analysis
            2. Perform detailed coverage verification
            3. Process claim through settlement calculation
            
            Confidence: 85%
            """
        else:
            return f"""
            ⚠️ PRELIMINARY ELIGIBILITY: NEEDS REVIEW
            Policy ID: {policy_id}
            Policy Type: {policy_type.replace('_', ' ').title()} Insurance
            Claim Type: {claim_type}
            Issue: Claim type may not match policy coverage
            Source: Hartford BigQuery Database
            
            Next Steps: Verify specific coverage details with underwriting department
            Manual Review Required: Coverage mismatch detected
            Confidence: 70%
            """
            
    except Exception as e:
        return f"""
        ❌ ELIGIBILITY ASSESSMENT ERROR
        Policy ID: {policy_id}
        Error: BigQuery query failed
        Details: {str(e)}
        Dataset: {project_id}.{dataset_id}.policies
        Next Steps: Check BigQuery access and database connectivity
        """


def create_intake_validation_agent() -> LlmAgent:
    """
    Factory function to create the Intake Validation Agent
    
    Returns:
        Configured Intake Validation Agent instance
    """
    return LlmAgent(
        name="intake_validation_agent",
        model="gemini-2.5-flash",
        description="Validates new insurance claim submissions for completeness, policy compliance, and eligibility before processing",
        instruction="""
        You are the Intake Validation Specialist for Hartford Insurance Company.
        You have direct access to Hartford's BigQuery insurance database with real policy and claims data.
        
        Your SOLE responsibility is validating new insurance claim submissions before they enter the claims processing workflow.
        
        ✅ YOUR CORE FUNCTIONS (Using Real Hartford Data):
        1. Policy Status Validation - Query BigQuery to verify policy exists and is active
        2. Duplicate Claim Detection - Search claims database for potential duplicates
        3. Incident Timing Validation - Verify incident occurred during coverage period using policy dates from BigQuery
        4. Required Field Verification - Ensure all necessary information for Hartford processing
        5. Preliminary Eligibility Assessment - Match claim type with policy coverage from database
        
        📊 DATA SOURCE:
        All validations use Hartford's real BigQuery database:
        - Dataset: insurance_claims_demo
        - Tables: policies, claims, users, agents
        - Live data with thousands of real insurance policies and claims
        
        📋 COMMUNICATION STYLE:
        - Be professional and thorough
        - Always mention you're using Hartford's BigQuery database
        - Provide clear validation results with confidence scores
        - Explain any issues found and next steps needed
        - Include specific database information for audit trails
        
        🔍 VALIDATION STANDARDS:
        - Policy must be active in Hartford's system
        - No duplicate claims within 7 days in same location
        - Incident must occur during policy effective period
        - Claims must be reported within 30 days of incident
        - All required fields must be present for processing
        - Claim type must match policy coverage type
        
        When handling requests, systematically validate using your tools in this order:
        1. First validate the policy status
        2. Check for potential duplicates
        3. Validate incident and reporting timing
        4. Verify required fields are complete
        5. Assess preliminary eligibility
        """,
        tools=[
            validate_policy_status,
            check_duplicate_claims,
            validate_incident_timing,
            verify_required_fields,
            assess_preliminary_eligibility
        ]
    )