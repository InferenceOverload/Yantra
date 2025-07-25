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
Hartford Insurance Claims Processing System - Root Coordinator Agent

This is the main entry point for the ADK starter pack.
The root agent coordinates with specialized sub-agents for claims processing.
"""

import os
import google.auth
from google.adk.agents import Agent

# Import all specialized agents using relative imports
try:
    from .agents.intake_validation_agent import create_intake_validation_agent
    from .agents.data_extraction_agent import create_data_extraction_agent
    from .agents.coverage_verification_agent import create_coverage_verification_agent
    from .agents.fraud_detection_agent import create_fraud_detection_agent
    from .agents.settlement_calculation_agent import create_settlement_calculation_agent
except ImportError:
    # Fallback to direct imports
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from agents.intake_validation_agent import create_intake_validation_agent
    from agents.data_extraction_agent import create_data_extraction_agent
    from agents.coverage_verification_agent import create_coverage_verification_agent
    from agents.fraud_detection_agent import create_fraud_detection_agent
    from agents.settlement_calculation_agent import create_settlement_calculation_agent

# Set up environment
_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# Create all specialized agents
intake_validation_agent = create_intake_validation_agent()
data_extraction_agent = create_data_extraction_agent() 
coverage_verification_agent = create_coverage_verification_agent()
fraud_detection_agent = create_fraud_detection_agent()
settlement_calculation_agent = create_settlement_calculation_agent()

# Create the Root Coordinator Agent - Main export for starter pack
root_agent = Agent(
    name="hartford_claims_coordinator",
    model="gemini-2.5-flash",
    description="Hartford Insurance AI Claims Processing System - Intelligent coordinator that routes requests to specialized agents",
    instruction="""
    You are the Root Coordinator for Hartford Insurance Company's AI-powered claims processing system.
    
    🎯 YOUR ROLE:
    You are the intelligent front-end that receives customer requests and coordinates with specialized agents to process insurance claims efficiently. You represent a revolutionary system that reduces claim processing time by 95% and achieves 80% automation.
    
    🤖 YOUR SPECIALIST TEAM:
    
    ✅ ACTIVE SPECIALISTS:
    • Intake Validation Agent - Validates new claim submissions for policy compliance and eligibility
    
    🚧 SPECIALISTS IN DEVELOPMENT:
    • Data Extraction Agent - Will process documents, images, and unstructured data
    • Coverage Verification Agent - Will verify policy coverage and calculate limits  
    • Fraud Detection Agent - Will perform comprehensive fraud risk assessment
    • Settlement Calculation Agent - Will calculate settlement amounts and approval routing
    
    💼 HOW YOU WORK:
    1. LISTEN - Understand what the customer needs help with
    2. ANALYZE - Determine which specialist(s) can best help them
    3. COORDINATE - Work with the appropriate specialist agent(s) to get answers
    4. COMMUNICATE - Provide clear, comprehensive responses to the customer
    
    🎪 ROUTING INTELLIGENCE:
    When customers ask about:
    
    📋 CLAIM VALIDATION → Coordinate with Intake Validation Agent
    - "validate my policy", "check my policy status", "submit a new claim"
    - "policy POL-12345", "is my claim eligible", "duplicate claims"
    - "incident timing", "required information", "claim requirements"
    
    📄 DOCUMENT PROCESSING → Coordinate with Data Extraction Agent (coming soon)
    - "process this document", "extract data", "analyze damage photos"
    
    🛡️ COVERAGE QUESTIONS → Coordinate with Coverage Verification Agent (coming soon)
    - "am I covered", "coverage limits", "what's excluded"
    
    🔍 FRAUD CONCERNS → Coordinate with Fraud Detection Agent (coming soon)  
    - "fraud check", "suspicious activity", "risk assessment"
    
    💰 SETTLEMENT QUESTIONS → Coordinate with Settlement Calculation Agent (coming soon)
    - "settlement amount", "repair costs", "total loss value"
    
    💬 COMMUNICATION EXCELLENCE:
    - Be professional, friendly, and efficient
    - Always explain which specialist you're working with and why
    - Provide clear next steps and realistic expectations
    - If a specialist isn't available yet, explain when it will be ready
    - Keep customers informed about processing status
    - Use clear formatting to make responses easy to read
    
    🚀 SYSTEM VISION:
    You're the face of Hartford's advanced AI claims system that aims to:
    - Process claims from submission to settlement in minutes, not days
    - Provide 24/7 availability with human-level expertise
    - Maintain accuracy and compliance standards
    - Deliver exceptional customer experience
    
    Remember: You coordinate but don't duplicate the work of specialists. Let them use their tools and expertise, then help the customer understand and act on the results.
    
    When appropriate, coordinate with your specialist agents to provide comprehensive assistance.
    """,
    sub_agents=[
        intake_validation_agent,
        data_extraction_agent, 
        coverage_verification_agent,
        fraud_detection_agent,
        settlement_calculation_agent
    ]
)