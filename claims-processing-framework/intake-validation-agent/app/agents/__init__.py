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
Hartford Insurance Claims Processing Agents

This package contains all specialized agents for the claims processing system.
Each agent is responsible for a specific aspect of claims processing and can
be developed, tested, and deployed independently.

Agents:
- Intake Validation Agent: Validates claim submissions and policy compliance
- Data Extraction Agent: Processes documents, images, and unstructured data
- Coverage Verification Agent: Verifies policy coverage and calculates limits
- Fraud Detection Agent: Performs comprehensive fraud risk assessment
- Settlement Calculation Agent: Calculates settlement amounts and approvals
"""

from .intake_validation_agent import create_intake_validation_agent
from .data_extraction_agent import create_data_extraction_agent
from .coverage_verification_agent import create_coverage_verification_agent
from .fraud_detection_agent import create_fraud_detection_agent
from .settlement_calculation_agent import create_settlement_calculation_agent

__all__ = [
    'create_intake_validation_agent',
    'create_data_extraction_agent', 
    'create_coverage_verification_agent',
    'create_fraud_detection_agent',
    'create_settlement_calculation_agent'
]

__version__ = '1.0.0'
__author__ = 'Hartford Insurance AI Team'