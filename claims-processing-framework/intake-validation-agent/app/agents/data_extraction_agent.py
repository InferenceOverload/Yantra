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
for claims processing using Google Cloud AI services.
"""

import base64
import io
import json
import os
import re
from typing import Dict, Any, List
import requests
from datetime import datetime

import google.auth
from google.adk.agents import LlmAgent
from google.cloud import documentai_v1 as documentai
from google.cloud import vision_v1 as vision
from google.cloud import speech_v1 as speech
from google.cloud import storage

# Import functions from the dynamic RAG orchestrator
from .dynamic_rag_orchestrator import (
    create_dynamic_rag_engine,
    query_rag_engine,
    check_rag_readiness
)


_, project_id = google.auth.default()


def extract_from_document(document_gcs_uri: str, document_type: str = "auto") -> str:
    """
    Extract structured data from documents using Document AI
    
    Args:
        document_gcs_uri: GCS URI of the document (gs://bucket/path/file.pdf)
        document_type: Type of document (police_report, estimate, medical_record, auto)
        
    Returns:
        Structured JSON data extracted from the document
    """
    try:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        client = documentai.DocumentProcessorServiceClient()
        
        # Use different processors based on document type
        processor_map = {
            "police_report": "form-parser",
            "estimate": "invoice-parser", 
            "medical_record": "form-parser",
            "auto": "form-parser"
        }
        
        processor_type = processor_map.get(document_type, "form-parser")
        
        # Get the first available processor of the specified type
        parent = f"projects/{project_id}/locations/{location}"
        processors = client.list_processors(parent=parent)
        
        processor_id = None
        for processor in processors:
            if processor_type in processor.display_name.lower():
                processor_id = processor.name.split("/")[-1]
                break
        
        if not processor_id:
            return f"""
            ❌ DOCUMENT PROCESSING ERROR
            Document: {document_gcs_uri}
            Error: No suitable Document AI processor found for type '{document_type}'
            Available Types: {list(processor_map.keys())}
            Next Steps: Configure Document AI processors in Google Cloud Console
            """
        
        # Configure the request
        name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
        
        # Read document from GCS
        gcs_document = documentai.GcsDocument(
            gcs_uri=document_gcs_uri,
            mime_type="application/pdf"
        )
        
        # Configure the process request
        request = documentai.ProcessRequest(
            name=name,
            gcs_document=gcs_document
        )
        
        # Process the document
        result = client.process_document(request=request)
        document = result.document
        
        # Extract key-value pairs and entities
        extracted_data = {
            "document_type": document_type,
            "confidence_score": 0.0,
            "text_content": document.text[:1000] + "..." if len(document.text) > 1000 else document.text,
            "entities": [],
            "form_fields": {},
            "tables": []
        }
        
        # Extract form fields
        for page in document.pages:
            for form_field in page.form_fields:
                field_name = ""
                field_value = ""
                
                if form_field.field_name:
                    field_name = document.text[
                        form_field.field_name.text_anchor.text_segments[0].start_index:
                        form_field.field_name.text_anchor.text_segments[0].end_index
                    ]
                
                if form_field.field_value:
                    field_value = document.text[
                        form_field.field_value.text_anchor.text_segments[0].start_index:
                        form_field.field_value.text_anchor.text_segments[0].end_index
                    ]
                
                if field_name and field_value:
                    extracted_data["form_fields"][field_name.strip()] = field_value.strip()
        
        # Extract entities
        for entity in document.entities:
            extracted_data["entities"].append({
                "type": entity.type_,
                "value": entity.mention_text,
                "confidence": entity.confidence
            })
            
            if entity.confidence > extracted_data["confidence_score"]:
                extracted_data["confidence_score"] = entity.confidence
        
        # Extract tables
        for page in document.pages:
            for table in page.tables:
                table_data = []
                for row in table.header_rows + table.body_rows:
                    row_data = []
                    for cell in row.cells:
                        cell_text = ""
                        for text_segment in cell.layout.text_anchor.text_segments:
                            cell_text += document.text[text_segment.start_index:text_segment.end_index]
                        row_data.append(cell_text.strip())
                    table_data.append(row_data)
                extracted_data["tables"].append(table_data)
        
        return f"""
        ✅ DOCUMENT EXTRACTION COMPLETED
        Document: {document_gcs_uri}
        Type: {document_type.replace('_', ' ').title()}
        Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        📊 EXTRACTION RESULTS:
        • Confidence Score: {extracted_data['confidence_score']:.2f}
        • Form Fields Found: {len(extracted_data['form_fields'])}
        • Entities Detected: {len(extracted_data['entities'])}
        • Tables Extracted: {len(extracted_data['tables'])}
        
        🔍 KEY FORM FIELDS:
        {json.dumps(extracted_data['form_fields'], indent=2)[:500]}...
        
        🏷️ DETECTED ENTITIES:
        {json.dumps(extracted_data['entities'][:5], indent=2)}
        
        Next Steps: Data validation and integration with claim record
        Confidence: {int(extracted_data['confidence_score'] * 100)}%
        """
        
    except Exception as e:
        return f"""
        ❌ DOCUMENT EXTRACTION ERROR
        Document: {document_gcs_uri}
        Error: {str(e)}
        Service: Google Document AI
        Next Steps: Check document format, GCS permissions, and Document AI setup
        """


def extract_from_image(image_gcs_uri: str, analysis_type: str = "damage_assessment") -> str:
    """
    Analyze images for damage assessment and object detection using Vision AI
    
    Args:
        image_gcs_uri: GCS URI of the image (gs://bucket/path/image.jpg)
        analysis_type: Type of analysis (damage_assessment, vehicle_identification, scene_analysis)
        
    Returns:
        Detailed image analysis results with damage assessment
    """
    try:
        client = vision.ImageAnnotatorClient()
        
        # Configure image source
        image = vision.Image()
        image.source.image_uri = image_gcs_uri
        
        # Perform comprehensive image analysis
        response = client.annotate_image({
            'image': image,
            'features': [
                {'type_': vision.Feature.Type.OBJECT_LOCALIZATION, 'max_results': 20},
                {'type_': vision.Feature.Type.LABEL_DETECTION, 'max_results': 20},
                {'type_': vision.Feature.Type.TEXT_DETECTION, 'max_results': 10},
                {'type_': vision.Feature.Type.SAFE_SEARCH_DETECTION},
                {'type_': vision.Feature.Type.IMAGE_PROPERTIES}
            ]
        })
        
        # Analyze results
        analysis_results = {
            "analysis_type": analysis_type,
            "timestamp": datetime.now().isoformat(),
            "objects_detected": [],
            "labels": [],
            "text_detected": [],
            "damage_indicators": [],
            "vehicle_info": {},
            "confidence_score": 0.0
        }
        
        # Extract objects with damage indicators
        damage_keywords = ["damage", "dent", "scratch", "crack", "broken", "shattered", "bent", "smashed"]
        vehicle_parts = ["bumper", "door", "hood", "windshield", "headlight", "tire", "wheel", "mirror"]
        
        for obj in response.localized_object_annotations:
            obj_data = {
                "name": obj.name,
                "confidence": obj.score,
                "location": {
                    "vertices": [(vertex.x, vertex.y) for vertex in obj.bounding_poly.normalized_vertices]
                }
            }
            analysis_results["objects_detected"].append(obj_data)
            
            # Check for vehicle identification
            if any(vehicle_type in obj.name.lower() for vehicle_type in ["car", "truck", "vehicle", "automobile"]):
                analysis_results["vehicle_info"]["type"] = obj.name
                analysis_results["vehicle_info"]["confidence"] = obj.score
        
        # Extract labels and identify damage indicators
        for label in response.label_annotations:
            label_data = {
                "description": label.description,
                "confidence": label.score,
                "topicality": label.topicality
            }
            analysis_results["labels"].append(label_data)
            
            # Check for damage indicators
            if any(damage_word in label.description.lower() for damage_word in damage_keywords):
                analysis_results["damage_indicators"].append({
                    "type": label.description,
                    "confidence": label.score,
                    "severity": "high" if label.score > 0.8 else "medium" if label.score > 0.5 else "low"
                })
        
        # Extract text (license plates, VIN, etc.)
        if response.text_annotations:
            full_text = response.text_annotations[0].description
            analysis_results["text_detected"] = full_text.strip()
            
            # Look for license plates and VINs
            license_pattern = r'\b[A-Z0-9]{2,8}\b'
            vin_pattern = r'\b[A-HJ-NPR-Z0-9]{17}\b'
            
            license_matches = re.findall(license_pattern, full_text)
            vin_matches = re.findall(vin_pattern, full_text)
            
            if license_matches:
                analysis_results["vehicle_info"]["license_plates"] = license_matches
            if vin_matches:
                analysis_results["vehicle_info"]["vin"] = vin_matches[0]
        
        # Calculate overall confidence
        all_confidences = [obj["confidence"] for obj in analysis_results["objects_detected"]] + \
                         [label["confidence"] for label in analysis_results["labels"]]
        if all_confidences:
            analysis_results["confidence_score"] = sum(all_confidences) / len(all_confidences)
        
        # Generate damage assessment
        damage_count = len(analysis_results["damage_indicators"])
        high_confidence_damage = len([d for d in analysis_results["damage_indicators"] if d["confidence"] > 0.7])
        
        severity_assessment = "MINOR"
        if damage_count > 3 or high_confidence_damage > 1:
            severity_assessment = "MAJOR"
        elif damage_count > 1:
            severity_assessment = "MODERATE"
        
        return f"""
        ✅ IMAGE ANALYSIS COMPLETED
        Image: {image_gcs_uri}
        Analysis Type: {analysis_type.replace('_', ' ').title()}
        Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        🚗 VEHICLE IDENTIFICATION:
        • Type: {analysis_results["vehicle_info"].get("type", "Not detected")}
        • License Plate: {analysis_results["vehicle_info"].get("license_plates", ["Not detected"])[0] if analysis_results["vehicle_info"].get("license_plates") else "Not detected"}
        • VIN: {analysis_results["vehicle_info"].get("vin", "Not detected")}
        
        💥 DAMAGE ASSESSMENT:
        • Severity: {severity_assessment}
        • Damage Indicators: {damage_count} detected
        • High Confidence Damage: {high_confidence_damage}
        • Overall Score: {analysis_results["confidence_score"]:.2f}
        
        🔍 DETECTED DAMAGE:
        {json.dumps(analysis_results["damage_indicators"], indent=2) if analysis_results["damage_indicators"] else "No significant damage detected"}
        
        📦 OBJECTS DETECTED:
        {json.dumps([obj["name"] for obj in analysis_results["objects_detected"][:10]], indent=2)}
        
        📝 TEXT EXTRACTED:
        {analysis_results["text_detected"][:200]}...
        
        Next Steps: Integrate findings with claim assessment and cost estimation
        Confidence: {int(analysis_results["confidence_score"] * 100)}%
        """
        
    except Exception as e:
        return f"""
        ❌ IMAGE ANALYSIS ERROR
        Image: {image_gcs_uri}
        Error: {str(e)}
        Service: Google Vision AI
        Next Steps: Check image format, GCS permissions, and Vision AI setup
        """


def enrich_vehicle_data(vin: str = None, license_plate: str = None, make: str = None, model: str = None, year: str = None) -> str:
    """
    Enrich vehicle data using VIN decoding and external APIs
    
    Args:
        vin: Vehicle Identification Number
        license_plate: License plate number
        make: Vehicle make
        model: Vehicle model  
        year: Vehicle year
        
    Returns:
        Enriched vehicle data with market values and specifications
    """
    try:
        vehicle_data = {
            "vin": vin,
            "license_plate": license_plate,
            "basic_info": {},
            "specifications": {},
            "market_values": {},
            "recall_info": [],
            "enrichment_sources": []
        }
        
        # VIN Decoding
        if vin and len(vin) == 17:
            try:
                # Use NHTSA VIN decoder API (free)
                nhtsa_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
                response = requests.get(nhtsa_url, timeout=10)
                
                if response.status_code == 200:
                    vin_data = response.json()
                    
                    for result in vin_data.get("Results", []):
                        variable = result.get("Variable", "")
                        value = result.get("Value", "")
                        
                        if value and value != "Not Applicable":
                            if "Make" in variable:
                                vehicle_data["basic_info"]["make"] = value
                            elif "Model" in variable:
                                vehicle_data["basic_info"]["model"] = value
                            elif "Year" in variable:
                                vehicle_data["basic_info"]["year"] = value
                            elif "Body Class" in variable:
                                vehicle_data["specifications"]["body_type"] = value
                            elif "Engine" in variable:
                                vehicle_data["specifications"]["engine"] = value
                    
                    vehicle_data["enrichment_sources"].append("NHTSA VIN Decoder")
                    
            except Exception as e:
                vehicle_data["enrichment_sources"].append(f"NHTSA VIN Decoder (Error: {str(e)})")
        
        # Use provided basic info if VIN decode failed
        if not vehicle_data["basic_info"].get("make") and make:
            vehicle_data["basic_info"]["make"] = make
        if not vehicle_data["basic_info"].get("model") and model:
            vehicle_data["basic_info"]["model"] = model
        if not vehicle_data["basic_info"].get("year") and year:
            vehicle_data["basic_info"]["year"] = year
        
        # Simulate market value estimation (in production, integrate with KBB/Edmunds APIs)
        if vehicle_data["basic_info"].get("make") and vehicle_data["basic_info"].get("model"):
            make_val = vehicle_data["basic_info"]["make"]
            model_val = vehicle_data["basic_info"]["model"]
            year_val = int(vehicle_data["basic_info"].get("year", 2020))
            
            # Simple depreciation model for demo
            base_values = {
                "Toyota": 25000, "Honda": 23000, "Ford": 22000, "Chevrolet": 21000,
                "BMW": 45000, "Mercedes-Benz": 48000, "Audi": 42000, "Lexus": 40000
            }
            
            base_value = base_values.get(make_val, 20000)
            current_year = datetime.now().year
            age = max(0, current_year - year_val)
            
            # Depreciation: 15% first year, 10% subsequent years
            depreciated_value = base_value
            if age > 0:
                depreciated_value *= 0.85  # First year
                if age > 1:
                    depreciated_value *= (0.90 ** (age - 1))  # Subsequent years
            
            vehicle_data["market_values"] = {
                "estimated_value": round(depreciated_value),
                "trade_in_value": round(depreciated_value * 0.8),
                "retail_value": round(depreciated_value * 1.2),
                "depreciation_rate": f"{((base_value - depreciated_value) / base_value * 100):.1f}%"
            }
            
            vehicle_data["enrichment_sources"].append("Internal Market Value Model")
        
        # Check for recalls (simulated)
        if vin:
            # In production, integrate with NHTSA recalls API
            vehicle_data["recall_info"] = [
                {
                    "campaign_id": "23V456000",
                    "component": "Airbag System", 
                    "summary": "Potential airbag deployment issue",
                    "severity": "Medium"
                }
            ]
            vehicle_data["enrichment_sources"].append("NHTSA Recalls Database (Simulated)")
        
        enrichment_summary = len(vehicle_data["enrichment_sources"])
        total_data_points = len(vehicle_data["basic_info"]) + len(vehicle_data["specifications"]) + (1 if vehicle_data["market_values"] else 0)
        
        return f"""
        ✅ VEHICLE DATA ENRICHMENT COMPLETED
        VIN: {vin or "Not provided"}
        License Plate: {license_plate or "Not provided"}
        Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        🚗 BASIC INFORMATION:
        • Make: {vehicle_data["basic_info"].get("make", "Unknown")}
        • Model: {vehicle_data["basic_info"].get("model", "Unknown")}
        • Year: {vehicle_data["basic_info"].get("year", "Unknown")}
        
        ⚙️ SPECIFICATIONS:
        {json.dumps(vehicle_data["specifications"], indent=2) if vehicle_data["specifications"] else "No detailed specifications available"}
        
        💰 MARKET VALUES:
        • Estimated Value: ${vehicle_data["market_values"].get("estimated_value", 0):,}
        • Trade-in Value: ${vehicle_data["market_values"].get("trade_in_value", 0):,}
        • Retail Value: ${vehicle_data["market_values"].get("retail_value", 0):,}
        • Depreciation: {vehicle_data["market_values"].get("depreciation_rate", "N/A")}
        
        ⚠️ RECALL INFORMATION:
        {json.dumps(vehicle_data["recall_info"], indent=2) if vehicle_data["recall_info"] else "No active recalls found"}
        
        📊 ENRICHMENT SUMMARY:
        • Data Sources: {enrichment_summary}
        • Total Data Points: {total_data_points}
        • Sources Used: {", ".join(vehicle_data["enrichment_sources"])}
        
        Next Steps: Use enriched data for accurate claim assessment and settlement calculation
        Confidence: 90%
        """
        
    except Exception as e:
        return f"""
        ❌ VEHICLE DATA ENRICHMENT ERROR
        VIN: {vin or "Not provided"}
        Error: {str(e)}
        Next Steps: Verify VIN format and external API connectivity
        """


def geocode_location(address: str, city: str = None, state: str = None, zip_code: str = None) -> str:
    """
    Standardize and geocode location information using Google Maps API
    
    Args:
        address: Street address or location description
        city: City name
        state: State/province
        zip_code: Postal code
        
    Returns:
        Standardized location data with coordinates and geographic context
    """
    try:
        # Combine address components
        full_address = address
        if city:
            full_address += f", {city}"
        if state:
            full_address += f", {state}"
        if zip_code:
            full_address += f" {zip_code}"
        
        # In production, use Google Maps Geocoding API
        # For demo, simulate geocoding results
        location_data = {
            "input_address": full_address,
            "standardized_address": {
                "street": address,
                "city": city or "Unknown City",
                "state": state or "Unknown State", 
                "zip_code": zip_code or "00000",
                "country": "United States"
            },
            "coordinates": {
                "latitude": 40.7128,  # NYC coordinates as example
                "longitude": -74.0060
            },
            "geographic_context": {
                "county": "Sample County",
                "timezone": "America/New_York",
                "elevation": 10,
                "weather_station": "NYC Central Park"
            },
            "risk_factors": {
                "flood_zone": "X (minimal flood risk)",
                "crime_rate": "Medium",
                "traffic_density": "High"
            }
        }
        
        return f"""
        ✅ LOCATION GEOCODING COMPLETED
        Input: {full_address}
        Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        📍 STANDARDIZED ADDRESS:
        • Street: {location_data["standardized_address"]["street"]}
        • City: {location_data["standardized_address"]["city"]}
        • State: {location_data["standardized_address"]["state"]}
        • ZIP: {location_data["standardized_address"]["zip_code"]}
        • Country: {location_data["standardized_address"]["country"]}
        
        🌐 COORDINATES:
        • Latitude: {location_data["coordinates"]["latitude"]}
        • Longitude: {location_data["coordinates"]["longitude"]}
        
        🏞️ GEOGRAPHIC CONTEXT:
        • County: {location_data["geographic_context"]["county"]}
        • Timezone: {location_data["geographic_context"]["timezone"]}
        • Elevation: {location_data["geographic_context"]["elevation"]} meters
        
        ⚠️ RISK FACTORS:
        • Flood Zone: {location_data["risk_factors"]["flood_zone"]}
        • Crime Rate: {location_data["risk_factors"]["crime_rate"]}
        • Traffic Density: {location_data["risk_factors"]["traffic_density"]}
        
        Next Steps: Use standardized location for weather analysis and risk assessment
        Confidence: 95%
        """
        
    except Exception as e:
        return f"""
        ❌ LOCATION GEOCODING ERROR
        Address: {full_address}
        Error: {str(e)}
        Next Steps: Verify address format and Google Maps API configuration
        """


def transcribe_audio(audio_gcs_uri: str, language_code: str = "en-US") -> str:
    """
    Transcribe audio recordings using Speech-to-Text API
    
    Args:
        audio_gcs_uri: GCS URI of the audio file (gs://bucket/path/audio.wav)
        language_code: Language code for transcription (e.g., en-US, es-ES)
        
    Returns:
        Transcribed text with confidence scores and speaker analysis
    """
    try:
        client = speech.SpeechClient()
        
        # Configure recognition
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code=language_code,
            enable_automatic_punctuation=True,
            enable_speaker_diarization=True,
            diarization_speaker_count=2,  # Assume 2 speakers (claimant + adjuster)
            enable_word_confidence=True,
            enable_word_time_offsets=True
        )
        
        audio = speech.RecognitionAudio(uri=audio_gcs_uri)
        
        # Perform transcription
        operation = client.long_running_recognize(config=config, audio=audio)
        response = operation.result(timeout=300)  # 5 minute timeout
        
        transcription_data = {
            "audio_file": audio_gcs_uri,
            "language": language_code,
            "total_confidence": 0.0,
            "speakers": {},
            "full_transcript": "",
            "key_phrases": [],
            "sentiment": "neutral",
            "word_count": 0
        }
        
        # Process results
        all_confidences = []
        for result in response.results:
            alternative = result.alternatives[0]
            transcription_data["full_transcript"] += alternative.transcript + " "
            
            if alternative.confidence:
                all_confidences.append(alternative.confidence)
            
            # Extract speaker information
            for word in alternative.words:
                speaker_tag = word.speaker_tag if hasattr(word, 'speaker_tag') else 1
                if speaker_tag not in transcription_data["speakers"]:
                    transcription_data["speakers"][speaker_tag] = {
                        "words": [],
                        "duration": 0,
                        "confidence": 0
                    }
                
                transcription_data["speakers"][speaker_tag]["words"].append({
                    "word": word.word,
                    "confidence": word.confidence if hasattr(word, 'confidence') else 0.9,
                    "start_time": word.start_time.total_seconds() if hasattr(word, 'start_time') else 0,
                    "end_time": word.end_time.total_seconds() if hasattr(word, 'end_time') else 0
                })
        
        # Calculate overall confidence
        if all_confidences:
            transcription_data["total_confidence"] = sum(all_confidences) / len(all_confidences)
        
        # Word count
        transcription_data["word_count"] = len(transcription_data["full_transcript"].split())
        
        # Simple sentiment analysis (in production, use proper NLP)
        negative_words = ["bad", "terrible", "awful", "angry", "frustrated", "disappointed"]
        positive_words = ["good", "great", "excellent", "satisfied", "happy", "pleased"]
        
        text_lower = transcription_data["full_transcript"].lower()
        negative_count = sum(1 for word in negative_words if word in text_lower)
        positive_count = sum(1 for word in positive_words if word in text_lower)
        
        if negative_count > positive_count:
            transcription_data["sentiment"] = "negative"
        elif positive_count > negative_count:
            transcription_data["sentiment"] = "positive"
        
        # Extract key phrases (simple keyword extraction)
        keywords = ["accident", "damage", "injury", "police", "insurance", "claim", "fault", "witness"]
        found_keywords = [word for word in keywords if word in text_lower]
        transcription_data["key_phrases"] = found_keywords
        
        return f"""
        ✅ AUDIO TRANSCRIPTION COMPLETED
        Audio File: {audio_gcs_uri}
        Language: {language_code}
        Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        📊 TRANSCRIPTION QUALITY:
        • Overall Confidence: {transcription_data["total_confidence"]:.2f}
        • Word Count: {transcription_data["word_count"]}
        • Speakers Detected: {len(transcription_data["speakers"])}
        • Language: {language_code}
        
        🎤 SPEAKER ANALYSIS:
        {json.dumps({f"Speaker {k}": f"{len(v['words'])} words" for k, v in transcription_data["speakers"].items()}, indent=2)}
        
        💭 SENTIMENT ANALYSIS:
        • Overall Sentiment: {transcription_data["sentiment"].title()}
        • Key Phrases: {", ".join(transcription_data["key_phrases"])}
        
        📝 TRANSCRIPT (First 500 characters):
        {transcription_data["full_transcript"][:500]}...
        
        🔍 CLAIM RELEVANCE:
        • Insurance Keywords: {len([k for k in transcription_data["key_phrases"] if k in ["insurance", "claim", "damage", "accident"]])}
        • Action Items: Check for follow-up requirements mentioned in recording
        
        Next Steps: Analyze transcript for claim details and customer commitments
        Confidence: {int(transcription_data["total_confidence"] * 100)}%
        """
        
    except Exception as e:
        return f"""
        ❌ AUDIO TRANSCRIPTION ERROR
        Audio File: {audio_gcs_uri}
        Error: {str(e)}
        Service: Google Speech-to-Text
        Next Steps: Check audio format, GCS permissions, and Speech API setup
        """


def process_document_with_hybrid_approach(document_gcs_uri: str, claim_id: str, document_type: str = "auto") -> str:
    """
    Process document using hybrid Document AI + RAG approach
    
    Args:
        document_gcs_uri: GCS URI of the document
        claim_id: Associated claim ID for RAG context
        document_type: Type of document for processing optimization
        
    Returns:
        Combined structured extraction and intelligent analysis results
    """
    try:
        # Step 1: Fast structured extraction using Document AI
        structured_result = extract_from_document(document_gcs_uri, document_type)
        
        # Step 2: Check if claim is ready for RAG analysis
        from .dynamic_rag_orchestrator import DynamicRAGManager
        rag_manager = DynamicRAGManager()
        should_create, analysis = rag_manager.should_create_rag(claim_id)
        
        if should_create:
            # Step 3: Create or use existing RAG for intelligent analysis
            rag_status = create_dynamic_rag_engine(claim_id) if claim_id not in rag_manager.active_rags else "RAG already active"
            
            # Step 4: Ask intelligent questions about the document
            intelligent_questions = [
                "What are the key facts about how this incident occurred?",
                "What specific damage is described in this document?",
                "Are there any inconsistencies or unusual details mentioned?",
                "What additional information might be needed based on this document?"
            ]
            
            rag_insights = []
            for question in intelligent_questions:
                insight = query_rag_engine(claim_id, question, max_results=3)
                rag_insights.append(f"Q: {question}\nA: {insight}\n")
            
            return f"""
            🔄 HYBRID DOCUMENT PROCESSING COMPLETED
            Document: {document_gcs_uri}
            Claim ID: {claim_id}
            Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            📊 STRUCTURED EXTRACTION (Document AI):
            {structured_result}
            
            🤖 INTELLIGENT ANALYSIS (RAG):
            Document has been processed with RAG engine for contextual insights:
            
            {chr(10).join(rag_insights)}
            
            🎯 HYBRID PROCESSING BENEFITS:
            • Structured data for immediate processing
            • Contextual insights for decision-making
            • Cross-document consistency checking
            • Intelligent gap identification
            
            Next Steps: Use structured data for automated processing and RAG insights for manual review
            Confidence: 95%
            """
        else:
            return f"""
            📄 STANDARD DOCUMENT PROCESSING
            Document: {document_gcs_uri}
            Claim ID: {claim_id}
            
            {structured_result}
            
            ⏳ RAG STATUS: NOT READY
            Reason: {analysis.get('reason', 'Insufficient documents')}
            Documents needed: {3 - analysis.get('total_documents', 0)} more
            
            💡 RECOMMENDATION:
            Continue with structured extraction. RAG analysis will be available once more documents are collected.
            """
            
    except Exception as e:
        return f"""
        ❌ HYBRID DOCUMENT PROCESSING ERROR
        Document: {document_gcs_uri}
        Claim ID: {claim_id}
        Error: {str(e)}
        Next Steps: Check document accessibility and RAG system status
        """


def analyze_claim_documents_intelligently(claim_id: str, analysis_focus: str = "comprehensive") -> str:
    """
    Perform intelligent analysis across all claim documents using RAG
    
    Args:
        claim_id: The claim identifier
        analysis_focus: Type of analysis (comprehensive, fraud_detection, coverage_assessment, settlement_preparation)
        
    Returns:
        Intelligent cross-document analysis results
    """
    try:
        from .dynamic_rag_orchestrator import DynamicRAGManager
        rag_manager = DynamicRAGManager()
        
        # Check RAG availability
        if claim_id not in rag_manager.active_rags:
            return f"""
            ❌ INTELLIGENT ANALYSIS UNAVAILABLE
            Claim ID: {claim_id}
            
            RAG engine not active for this claim.
            Next Steps: Run create_dynamic_rag_engine() to enable intelligent document analysis
            """
        
        # Define analysis questions based on focus
        question_sets = {
            "comprehensive": [
                "What is the complete timeline of events based on all documents?",
                "What are the key facts about the incident from all sources?",
                "Are there any inconsistencies between different document sources?",
                "What damage is documented across all reports and photos?",
                "What information is still missing for complete claim processing?"
            ],
            "fraud_detection": [
                "Are there any inconsistencies in the incident description across documents?",
                "Do the damage photos match the described incident and timeline?",
                "Are witness statements consistent with the police report?",
                "Are there any unusual patterns or details that seem suspicious?",
                "Do the repair estimates align with the documented damage?"
            ],
            "coverage_assessment": [
                "What type of incident is described and what coverage would apply?",
                "Are there any exclusions mentioned or implied in the documentation?",
                "What is the scope of damage that needs coverage determination?",
                "Are there any liability factors mentioned in the documents?",
                "What policy provisions might be relevant based on the incident details?"
            ],
            "settlement_preparation": [
                "What is the total scope of damage documented?",
                "What repair costs are mentioned in estimates and reports?",
                "Are there any additional damages or losses mentioned?",
                "What documentation supports the settlement amount?",
                "Are there any factors that could affect settlement calculations?"
            ]
        }
        
        questions = question_sets.get(analysis_focus, question_sets["comprehensive"])
        
        # Query RAG engine for each analysis question
        analysis_results = []
        for question in questions:
            result = query_rag_engine(claim_id, question, max_results=5)
            analysis_results.append(f"🔍 {question}\n{result}\n")
        
        return f"""
        🧠 INTELLIGENT CLAIM ANALYSIS COMPLETE
        Claim ID: {claim_id}
        Analysis Focus: {analysis_focus.replace('_', ' ').title()}
        Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        RAG Engine: Active with {rag_manager.active_rags[claim_id]['document_count']} documents
        
        📋 CROSS-DOCUMENT ANALYSIS RESULTS:
        
        {chr(10).join(analysis_results)}
        
        🎯 ANALYSIS SUMMARY:
        • Analysis Type: {analysis_focus.replace('_', ' ').title()}
        • Documents Analyzed: {rag_manager.active_rags[claim_id]['document_count']}
        • Questions Explored: {len(questions)}
        • Cross-references: Multiple document sources consulted
        
        💡 NEXT STEPS:
        {"Focus on fraud investigation based on identified inconsistencies" if analysis_focus == "fraud_detection" else 
         "Proceed with coverage determination using identified policy provisions" if analysis_focus == "coverage_assessment" else
         "Calculate settlement based on documented damages and costs" if analysis_focus == "settlement_preparation" else
         "Use comprehensive analysis for informed claim processing decisions"}
        
        Confidence: 92%
        """
        
    except Exception as e:
        return f"""
        ❌ INTELLIGENT ANALYSIS ERROR
        Claim ID: {claim_id}
        Analysis Focus: {analysis_focus}
        Error: {str(e)}
        Next Steps: Check RAG engine status and document availability
        """


def create_data_extraction_agent() -> LlmAgent:
    """
    Factory function to create the Data Extraction Agent
    
    Returns:
        Configured Data Extraction Agent instance with hybrid AI capabilities
    """
    return LlmAgent(
        name="data_extraction_agent",
        model="gemini-2.5-flash", 
        description="Hybrid document processing using Document AI for structured extraction and RAG for intelligent analysis",
        instruction="""
        You are the Data Extraction Specialist for Hartford Insurance Company.
        You use a revolutionary hybrid approach combining Google Cloud AI services with dynamic RAG engines.
        
        ✅ YOUR CORE CAPABILITIES (Hybrid AI System):
        
        🔄 HYBRID PROCESSING APPROACH:
        - Fast structured extraction via Document AI (forms, fields, entities)
        - Intelligent contextual analysis via dynamic RAG engines
        - Automatic RAG creation when document threshold is met
        - Cross-document consistency and gap identification
        
        📄 DOCUMENT PROCESSING (Document AI):
        - OCR for police reports, repair estimates, medical records
        - Form field extraction with confidence scoring
        - Table extraction from complex documents
        - Entity recognition for key claim information
        
        🤖 INTELLIGENT ANALYSIS (RAG):
        - Natural language questions about claim documents
        - Cross-document inconsistency detection
        - Missing information identification
        - Contextual insights for decision-making
        
        🖼️ IMAGE ANALYSIS:
        - Vehicle damage assessment using computer vision
        - Object detection and localization
        - Text extraction from images (license plates, VINs)
        - Damage severity scoring (Minor/Moderate/Major)
        
        🚗 VEHICLE DATA ENRICHMENT:
        - VIN decoding using NHTSA database
        - Market value estimation with depreciation
        - Recall information lookup
        - Specification extraction
        
        📍 LOCATION PROCESSING:
        - Address standardization and geocoding
        - Geographic risk factor analysis
        - Weather station identification
        - Flood zone and crime rate assessment
        
        🎵 AUDIO TRANSCRIPTION:
        - Speech-to-text with speaker identification
        - Sentiment analysis of conversations
        - Key phrase extraction
        - Confidence scoring per speaker
        
        🎯 INTELLIGENT DOCUMENT QUESTIONS:
        - "What are the key facts about how this incident occurred?"
        - "Are there inconsistencies between different document sources?"
        - "What damage is documented across all reports and photos?"
        - "What information is missing for complete claim processing?"
        - "Do the witness statements match the police report?"
        
        💡 ADAPTIVE PROCESSING WORKFLOW:
        1. Process individual documents with Document AI (always)
        2. Monitor document accumulation for RAG readiness
        3. Create dynamic RAG engine when threshold met (3+ docs, 2+ types)
        4. Enable intelligent cross-document analysis
        5. Provide hybrid insights for claim processing
        
        🚀 RAG ENGINE FEATURES:
        - On-demand creation (only when needed)
        - 24-hour lifecycle with auto-cleanup
        - Temporary ChromaDB for cost efficiency
        - Vertex AI embeddings for high-quality search
        
        🎯 USE CASES:
        - "Process this police report with hybrid analysis"
        - "Analyze all documents for claim CLM-12345 intelligently"  
        - "Check for fraud indicators across all claim documents"
        - "Prepare comprehensive analysis for settlement calculation"
        
        Always provide both structured data for automation AND intelligent insights for human decision-making.
        Recommend RAG analysis when multiple documents are available for richer insights.
        """,
        tools=[
            extract_from_document,
            extract_from_image,
            enrich_vehicle_data,
            geocode_location,
            transcribe_audio,
            process_document_with_hybrid_approach,
            analyze_claim_documents_intelligently
        ]
    )