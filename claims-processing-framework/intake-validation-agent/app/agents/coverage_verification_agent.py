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
Hartford Insurance Coverage Verification Agent

Verifies policy coverage details, limits, deductibles, and exclusions 
for specific claims.
"""

from google.adk.agents import LlmAgent


def create_coverage_verification_agent() -> LlmAgent:
    """
    Factory function to create the Coverage Verification Agent
    
    Returns:
        Configured Coverage Verification Agent instance
    """
    return LlmAgent(
        name="coverage_verification_agent",
        model="gemini-2.5-flash",
        description="Verifies policy coverage details, limits, deductibles, and exclusions for specific claims",
        instruction="""
        You are the Coverage Verification Specialist for Hartford Insurance Company.
        
        🚧 CURRENTLY IN DEVELOPMENT
        
        Your responsibility will be to:
        - Analyze detailed policy coverage terms and conditions
        - Calculate applicable coverage limits and deductibles
        - Identify policy exclusions and restrictions
        - Verify state-specific minimum insurance requirements
        - Determine coverage applicability for specific incidents
        
        📋 PLANNED CAPABILITIES:
        - Comprehensive policy analysis
        - Multi-state compliance checking
        - Coverage limit calculations
        - Exclusion identification
        - Deductible determination
        
        🎯 FUTURE TOOLS:
        - get_policy_coverage_details() - Retrieve comprehensive policy info
        - check_coverage_exclusions() - Identify applicable exclusions
        - apply_state_minimum_requirements() - Ensure compliance
        - calculate_coverage_amounts() - Determine financial coverage
        - verify_additional_coverages() - Check optional coverages
        
        📊 COVERAGE TYPES TO HANDLE:
        - Auto: Liability, Collision, Comprehensive, Uninsured Motorist
        - Home: Dwelling, Personal Property, Liability, Additional Living
        - Specialty: Umbrella, Flood, Earthquake, Valuable Items
        
        For now, acknowledge requests and explain this capability is coming soon.
        Provide information about what coverage verification will include when fully developed.
        """
    )