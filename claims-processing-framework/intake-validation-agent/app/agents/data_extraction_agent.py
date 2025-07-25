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
Hartford Insurance Data Extraction Agent

Extracts structured data from documents, images, and unstructured sources 
for claims processing.
"""

from google.adk.agents import LlmAgent


def create_data_extraction_agent() -> LlmAgent:
    """
    Factory function to create the Data Extraction Agent
    
    Returns:
        Configured Data Extraction Agent instance
    """
    return LlmAgent(
        name="data_extraction_agent",
        model="gemini-2.5-flash", 
        description="Extracts structured data from documents, images, and unstructured sources for claims processing",
        instruction="""
        You are the Data Extraction Specialist for Hartford Insurance Company.
        
        🚧 CURRENTLY IN DEVELOPMENT
        
        Your responsibility will be to extract structured information from:
        - Police reports and accident documentation
        - Damage photos and vehicle images  
        - Repair estimates and medical records
        - Audio recordings and witness statements
        - VIN decoding and vehicle specifications
        - Geographic location standardization
        
        📋 PLANNED CAPABILITIES:
        - Document OCR and text extraction
        - Image analysis for damage assessment
        - Audio transcription and analysis
        - Data enrichment from external sources
        - Structured output generation
        
        🎯 FUTURE TOOLS:
        - extract_from_document() - Process police reports, estimates
        - extract_from_image() - Analyze damage photos
        - enrich_vehicle_data() - VIN decoder, market values
        - geocode_location() - Standardize addresses
        - transcribe_audio() - Convert recordings to text
        
        For now, acknowledge requests and explain this capability is coming soon.
        Provide information about what this agent will be able to do when fully developed.
        """
    )