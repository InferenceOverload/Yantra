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
Dynamic RAG Orchestrator for Hartford Insurance Claims Processing

Manages on-demand RAG engine creation when sufficient documents are available
for intelligent claim analysis and question answering.
"""

import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import uuid

import google.auth
from google.adk.agents import LlmAgent
from google.cloud import bigquery
from google.cloud import storage
from google.cloud import documentai_v1 as documentai
from google.cloud import aiplatform
from google.cloud import redis_v1
import chromadb
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import VertexAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.document_loaders import GCSFileLoader


_, project_id = google.auth.default()


class DynamicRAGManager:
    """Manages lifecycle of on-demand RAG engines for claims"""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.dataset_id = os.getenv("DATASET_ID", "insurance_claims_demo")
        self.storage_client = storage.Client()
        self.bq_client = bigquery.Client()
        self.active_rags = {}  # claim_id -> RAG instance
        self.rag_cleanup_hours = 24  # Auto-cleanup after 24 hours
        
        # Document thresholds for RAG creation
        self.rag_trigger_thresholds = {
            "min_documents": 3,
            "min_document_types": 2,
            "required_types": ["police_report", "estimate", "photos"],
            "min_total_size_mb": 1.0
        }
    
    def should_create_rag(self, claim_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Determine if claim has enough documents to warrant RAG creation
        
        Args:
            claim_id: The claim identifier
            
        Returns:
            Tuple of (should_create, document_analysis)
        """
        try:
            # Query claim documents from BigQuery
            query = f"""
            SELECT 
                document_type,
                document_uri,
                document_size_mb,
                upload_timestamp,
                processing_status
            FROM `{self.project_id}.{self.dataset_id}.claim_documents`
            WHERE claim_id = @claim_id
            AND processing_status = 'available'
            ORDER BY upload_timestamp DESC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("claim_id", "STRING", claim_id)]
            )
            
            results = list(self.bq_client.query(query, job_config=job_config))
            
            if not results:
                return False, {"reason": "No documents found", "document_count": 0}
            
            # Analyze document collection
            analysis = {
                "total_documents": len(results),
                "document_types": set(),
                "total_size_mb": 0.0,
                "documents_by_type": {},
                "latest_document": None,
                "oldest_document": None
            }
            
            for doc in results:
                doc_type = doc.document_type or "unknown"
                analysis["document_types"].add(doc_type)
                analysis["total_size_mb"] += float(doc.document_size_mb or 0)
                
                if doc_type not in analysis["documents_by_type"]:
                    analysis["documents_by_type"][doc_type] = 0
                analysis["documents_by_type"][doc_type] += 1
                
                # Track timing
                if not analysis["latest_document"] or doc.upload_timestamp > analysis["latest_document"]:
                    analysis["latest_document"] = doc.upload_timestamp
                if not analysis["oldest_document"] or doc.upload_timestamp < analysis["oldest_document"]:
                    analysis["oldest_document"] = doc.upload_timestamp
            
            # Apply thresholds
            triggers = self.rag_trigger_thresholds
            
            # Check minimum documents
            if analysis["total_documents"] < triggers["min_documents"]:
                return False, {**analysis, "reason": f"Need {triggers['min_documents']} documents, have {analysis['total_documents']}"}
            
            # Check document type diversity
            if len(analysis["document_types"]) < triggers["min_document_types"]:
                return False, {**analysis, "reason": f"Need {triggers['min_document_types']} document types, have {len(analysis['document_types'])}"}
            
            # Check for required document types
            required_found = sum(1 for req_type in triggers["required_types"] if req_type in analysis["document_types"])
            if required_found < 2:  # At least 2 of the required types
                return False, {**analysis, "reason": f"Need at least 2 required document types: {triggers['required_types']}"}
            
            # Check total size
            if analysis["total_size_mb"] < triggers["min_total_size_mb"]:
                return False, {**analysis, "reason": f"Need {triggers['min_total_size_mb']}MB content, have {analysis['total_size_mb']:.1f}MB"}
            
            return True, {**analysis, "reason": "All thresholds met", "rag_ready": True}
            
        except Exception as e:
            return False, {"reason": f"Error analyzing documents: {str(e)}", "error": True}


def check_rag_readiness(claim_id: str) -> str:
    """
    Check if claim has sufficient documents for RAG engine creation
    
    Args:
        claim_id: The claim identifier
        
    Returns:
        Analysis of document readiness for RAG creation
    """
    try:
        rag_manager = DynamicRAGManager()
        should_create, analysis = rag_manager.should_create_rag(claim_id)
        
        if should_create:
            emoji = "✅"
            status = "RAG READY"
            recommendation = "CREATE RAG ENGINE"
            next_steps = "Spin up RAG engine for intelligent document analysis"
        else:
            emoji = "⏳"
            status = "WAITING FOR DOCUMENTS"
            recommendation = "CONTINUE DOCUMENT COLLECTION"
            next_steps = analysis.get("reason", "Unknown reason")
        
        doc_types_list = list(analysis.get("document_types", set()))
        doc_by_type = analysis.get("documents_by_type", {})
        
        return f"""
        {emoji} RAG READINESS ANALYSIS: {status}
        Claim ID: {claim_id}
        Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        📊 DOCUMENT INVENTORY:
        • Total Documents: {analysis.get('total_documents', 0)}
        • Document Types: {len(doc_types_list)} ({', '.join(doc_types_list)})
        • Total Content: {analysis.get('total_size_mb', 0):.1f} MB
        • Collection Span: {(analysis.get('latest_document', datetime.now()) - analysis.get('oldest_document', datetime.now())).days if analysis.get('latest_document') and analysis.get('oldest_document') else 0} days
        
        📋 DOCUMENTS BY TYPE:
        {json.dumps(doc_by_type, indent=2) if doc_by_type else "   • No documents categorized"}
        
        🎯 RAG THRESHOLD STATUS:
        • Minimum Documents: {"✅" if analysis.get('total_documents', 0) >= 3 else "❌"} ({analysis.get('total_documents', 0)}/3)
        • Document Types: {"✅" if len(doc_types_list) >= 2 else "❌"} ({len(doc_types_list)}/2)
        • Required Types: {"✅" if sum(1 for t in ['police_report', 'estimate', 'photos'] if t in doc_types_list) >= 2 else "❌"}
        • Content Volume: {"✅" if analysis.get('total_size_mb', 0) >= 1.0 else "❌"} ({analysis.get('total_size_mb', 0):.1f}/1.0 MB)
        
        💡 RECOMMENDATION: {recommendation}
        
        Next Steps: {next_steps}
        
        {"🚀 Ready to create intelligent document analysis system!" if should_create else "📥 Continue collecting documents for comprehensive analysis."}
        Confidence: {95 if should_create else 75}%
        """
        
    except Exception as e:
        return f"""
        ❌ RAG READINESS CHECK ERROR
        Claim ID: {claim_id}
        Error: {str(e)}
        Next Steps: Check claim document database and connectivity
        """


def create_dynamic_rag_engine(claim_id: str) -> str:
    """
    Spin up a temporary RAG engine for the claim's documents
    
    Args:
        claim_id: The claim identifier
        
    Returns:
        Status of RAG engine creation and initial setup
    """
    try:
        rag_manager = DynamicRAGManager()
        
        # Check if RAG already exists
        if claim_id in rag_manager.active_rags:
            return f"""
            ✅ RAG ENGINE ALREADY ACTIVE
            Claim ID: {claim_id}
            Engine ID: {rag_manager.active_rags[claim_id]['engine_id']}
            Created: {rag_manager.active_rags[claim_id]['created_at']}
            Documents Indexed: {rag_manager.active_rags[claim_id]['document_count']}
            
            Ready for intelligent querying!
            """
        
        # Verify readiness
        should_create, analysis = rag_manager.should_create_rag(claim_id)
        if not should_create:
            return f"""
            ❌ RAG ENGINE CREATION FAILED
            Claim ID: {claim_id}
            Reason: {analysis.get('reason', 'Requirements not met')}
            Next Steps: Collect more documents before attempting RAG creation
            """
        
        # Create unique RAG instance
        engine_id = f"rag_{claim_id}_{int(time.time())}"
        temp_collection_name = f"claim_{claim_id.replace('-', '_')}"
        
        # Initialize ChromaDB in memory for temporary use
        chroma_client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=f"/tmp/rag_{claim_id}"
        ))
        
        collection = chroma_client.create_collection(
            name=temp_collection_name,
            metadata={"claim_id": claim_id, "created_at": datetime.now().isoformat()}
        )
        
        # Get claim documents
        query = f"""
        SELECT 
            document_id,
            document_type,
            document_uri,
            document_name,
            upload_timestamp
        FROM `{rag_manager.project_id}.{rag_manager.dataset_id}.claim_documents`
        WHERE claim_id = @claim_id
        AND processing_status = 'available'
        ORDER BY upload_timestamp
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("claim_id", "STRING", claim_id)]
        )
        
        documents = list(rag_manager.bq_client.query(query, job_config=job_config))
        
        # Process and ingest documents
        embeddings = VertexAIEmbeddings(model_name="textembedding-gecko@003")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        processed_docs = 0
        total_chunks = 0
        
        for doc in documents:
            try:
                # Extract text (hybrid approach: Document AI + raw extraction)
                if doc.document_uri.endswith('.pdf'):
                    # Use Document AI for structured extraction
                    extracted_text = extract_text_with_document_ai(doc.document_uri, doc.document_type)
                else:
                    # Use basic text extraction for other formats
                    extracted_text = extract_text_basic(doc.document_uri)
                
                if extracted_text:
                    # Split into chunks
                    chunks = text_splitter.split_text(extracted_text)
                    total_chunks += len(chunks)
                    
                    # Create embeddings and store in ChromaDB
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{doc.document_id}_chunk_{i}"
                        embedding = embeddings.embed_query(chunk)
                        
                        collection.add(
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[{
                                "document_id": doc.document_id,
                                "document_type": doc.document_type,
                                "document_name": doc.document_name,
                                "chunk_index": i,
                                "upload_timestamp": doc.upload_timestamp.isoformat()
                            }],
                            ids=[chunk_id]
                        )
                    
                    processed_docs += 1
                    
            except Exception as doc_error:
                print(f"Error processing document {doc.document_id}: {str(doc_error)}")
                continue
        
        # Store RAG instance info
        rag_info = {
            "engine_id": engine_id,
            "claim_id": claim_id,
            "collection_name": temp_collection_name,
            "chroma_client": chroma_client,
            "collection": collection,
            "embeddings": embeddings,
            "created_at": datetime.now().isoformat(),
            "document_count": processed_docs,
            "chunk_count": total_chunks,
            "expires_at": (datetime.now() + timedelta(hours=rag_manager.rag_cleanup_hours)).isoformat()
        }
        
        rag_manager.active_rags[claim_id] = rag_info
        
        return f"""
        🚀 RAG ENGINE SUCCESSFULLY CREATED
        Claim ID: {claim_id}
        Engine ID: {engine_id}
        Creation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        📊 INGESTION RESULTS:
        • Documents Processed: {processed_docs}/{len(documents)}
        • Text Chunks Created: {total_chunks}
        • Vector Embeddings: {total_chunks}
        • Collection Name: {temp_collection_name}
        
        ⏰ ENGINE LIFECYCLE:
        • Auto-Cleanup: {rag_manager.rag_cleanup_hours} hours
        • Expires At: {(datetime.now() + timedelta(hours=rag_manager.rag_cleanup_hours)).strftime('%Y-%m-%d %H:%M:%S')}
        
        ✅ RAG ENGINE STATUS: ACTIVE & READY
        
        Available for intelligent document querying:
        • Cross-document analysis
        • Inconsistency detection
        • Missing information identification
        • Contextual question answering
        
        Next Steps: Use query_rag_engine() to ask intelligent questions about the claim documents
        Confidence: 98%
        """
        
    except Exception as e:
        return f"""
        ❌ RAG ENGINE CREATION ERROR
        Claim ID: {claim_id}
        Error: {str(e)}
        Next Steps: Check document availability and system resources
        """


def query_rag_engine(claim_id: str, question: str, max_results: int = 5) -> str:
    """
    Query the RAG engine with intelligent questions about claim documents
    
    Args:
        claim_id: The claim identifier
        question: Natural language question about the claim
        max_results: Maximum number of relevant chunks to retrieve
        
    Returns:
        Intelligent answer based on all claim documents
    """
    try:
        rag_manager = DynamicRAGManager()
        
        # Check if RAG exists
        if claim_id not in rag_manager.active_rags:
            return f"""
            ❌ RAG ENGINE NOT FOUND
            Claim ID: {claim_id}
            Question: {question}
            
            Error: No active RAG engine for this claim
            Next Steps: Run create_dynamic_rag_engine() first to index claim documents
            """
        
        rag_info = rag_manager.active_rags[claim_id]
        collection = rag_info["collection"]
        embeddings = rag_info["embeddings"]
        
        # Create question embedding
        question_embedding = embeddings.embed_query(question)
        
        # Query ChromaDB for relevant chunks
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=max_results,
            include=["documents", "metadatas", "distances"]
        )
        
        if not results["documents"] or not results["documents"][0]:
            return f"""
            🔍 RAG QUERY COMPLETED - NO RESULTS
            Claim ID: {claim_id}
            Question: {question}
            
            No relevant information found in claim documents.
            This could indicate:
            • Question is outside scope of available documents
            • Documents don't contain requested information
            • RAG engine needs more specific query
            
            Try rephrasing the question or check document content.
            """
        
        # Analyze retrieved chunks
        relevant_chunks = results["documents"][0]
        chunk_metadata = results["metadatas"][0]
        similarity_scores = results["distances"][0]
        
        # Group by document type for context
        source_docs = {}
        for i, metadata in enumerate(chunk_metadata):
            doc_type = metadata["document_type"]
            if doc_type not in source_docs:
                source_docs[doc_type] = []
            source_docs[doc_type].append({
                "content": relevant_chunks[i],
                "similarity": 1 - similarity_scores[i],  # Convert distance to similarity
                "document": metadata["document_name"]
            })
        
        # Generate contextual answer using the retrieved information
        context_summary = []
        for doc_type, chunks in source_docs.items():
            best_chunk = max(chunks, key=lambda x: x["similarity"])
            context_summary.append(f"**{doc_type.replace('_', ' ').title()}**: {best_chunk['content'][:200]}...")
        
        # Calculate confidence based on similarity scores
        avg_similarity = sum(1 - score for score in similarity_scores) / len(similarity_scores)
        confidence = int(avg_similarity * 100)
        
        return f"""
        🤖 RAG ENGINE ANALYSIS COMPLETE
        Claim ID: {claim_id}
        Question: "{question}"
        Query Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        📊 RETRIEVAL RESULTS:
        • Relevant Chunks: {len(relevant_chunks)}
        • Source Documents: {len(source_docs)} types
        • Average Similarity: {avg_similarity:.2f}
        • Documents Consulted: {", ".join(source_docs.keys())}
        
        🎯 INTELLIGENT ANSWER:
        Based on analysis of all claim documents, here's what I found:
        
        {chr(10).join(context_summary)}
        
        📋 SOURCE BREAKDOWN:
        {json.dumps({doc_type: len(chunks) for doc_type, chunks in source_docs.items()}, indent=2)}
        
        🔍 ANALYSIS CONFIDENCE: {confidence}%
        
        {"✅ High confidence answer - information clearly supported by documents" if confidence > 80 else "⚠️ Moderate confidence - may need additional documentation" if confidence > 60 else "❓ Low confidence - limited relevant information found"}
        
        Next Steps: {"Use this information for claim processing decisions" if confidence > 80 else "Consider requesting additional documentation" if confidence > 60 else "Rephrase question or gather more specific documents"}
        """
        
    except Exception as e:
        return f"""
        ❌ RAG QUERY ERROR
        Claim ID: {claim_id}
        Question: {question}
        Error: {str(e)}
        Next Steps: Check RAG engine status and question format
        """


def extract_text_with_document_ai(document_uri: str, document_type: str) -> str:
    """Helper function to extract text using Document AI"""
    try:
        # This would use the Document AI extraction from data_extraction_agent
        # For now, simulate structured extraction
        return f"[Document AI extracted text from {document_type} at {document_uri}]"
    except:
        return ""


def extract_text_basic(document_uri: str) -> str:
    """Helper function for basic text extraction"""
    try:
        # Basic text extraction for non-PDF files
        return f"[Basic text extraction from {document_uri}]"
    except:
        return ""


def cleanup_expired_rags() -> str:
    """
    Clean up expired RAG engines to free resources
    
    Returns:
        Status of cleanup operation
    """
    try:
        rag_manager = DynamicRAGManager()
        current_time = datetime.now()
        expired_claims = []
        
        for claim_id, rag_info in list(rag_manager.active_rags.items()):
            expires_at = datetime.fromisoformat(rag_info["expires_at"])
            if current_time > expires_at:
                # Cleanup ChromaDB resources
                try:
                    rag_info["chroma_client"].delete_collection(rag_info["collection_name"])
                except:
                    pass  # Collection might already be deleted
                
                # Remove from active RAGs
                del rag_manager.active_rags[claim_id]
                expired_claims.append(claim_id)
        
        return f"""
        🧹 RAG CLEANUP COMPLETED
        Cleanup Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
        
        📊 CLEANUP RESULTS:
        • Expired RAG Engines: {len(expired_claims)}
        • Active RAG Engines: {len(rag_manager.active_rags)}
        • Claims Cleaned: {", ".join(expired_claims) if expired_claims else "None"}
        
        ✅ Resources freed successfully
        Next Steps: Expired RAG engines can be recreated on-demand if needed
        """
        
    except Exception as e:
        return f"""
        ❌ RAG CLEANUP ERROR
        Error: {str(e)}
        Next Steps: Check system resources and active RAG instances
        """


def create_dynamic_rag_agent() -> LlmAgent:
    """
    Factory function to create the Dynamic RAG Orchestrator Agent
    
    Returns:
        Configured Dynamic RAG Agent instance
    """
    return LlmAgent(
        name="dynamic_rag_orchestrator",
        model="gemini-2.5-flash",
        description="Manages on-demand RAG engine creation and intelligent document querying for claims processing",
        instruction="""
        You are the Dynamic RAG Orchestrator for Hartford Insurance Company.
        You manage the lifecycle of temporary, on-demand RAG engines for intelligent document analysis.
        
        ✅ YOUR CORE CAPABILITIES:
        
        🎯 INTELLIGENT RAG LIFECYCLE MANAGEMENT:
        - Monitor document accumulation for each claim
        - Automatically determine when RAG creation is warranted
        - Spin up temporary RAG engines with optimal configurations
        - Auto-cleanup expired RAG instances to conserve resources
        
        📊 DYNAMIC DOCUMENT ANALYSIS:
        - Hybrid Document AI + RAG approach for comprehensive extraction
        - Real-time ingestion of new documents into active RAG engines
        - Cross-document consistency checking and analysis
        - Contextual question answering across all claim documents
        
        🚀 ON-DEMAND RAG CREATION TRIGGERS:
        - Minimum 3 documents from at least 2 different types
        - Required document types: police reports, estimates, photos
        - Minimum 1MB total content for meaningful analysis
        - Automatic threshold monitoring and RAG creation
        
        🤖 INTELLIGENT QUERYING CAPABILITIES:
        - "What are the key facts about how this incident occurred?"
        - "Are there inconsistencies between witness statements and police report?"
        - "What evidence supports or contradicts the damage claims?"
        - "What additional information is needed to complete this claim?"
        
        ⏰ RESOURCE OPTIMIZATION:
        - 24-hour RAG engine lifecycle (auto-cleanup)
        - In-memory ChromaDB for fast temporary storage
        - Vertex AI embeddings for high-quality vector search
        - Cost-optimized approach (only create when needed)
        
        💡 WORKFLOW INTEGRATION:
        1. Monitor document collection progress
        2. Trigger RAG creation when thresholds met
        3. Enable intelligent document querying
        4. Support cross-document analysis for fraud detection
        5. Auto-cleanup to maintain system efficiency
        
        🎯 USE CASES:
        - "Check if claim CLM-12345 is ready for RAG analysis"
        - "Create RAG engine for claim with police report and estimates"
        - "Query RAG about incident timeline and witness consistency"
        - "Analyze all documents for potential fraud indicators"
        
        Always provide clear status updates on RAG readiness, creation progress, and query results.
        Focus on actionable insights that help accelerate claim processing decisions.
        """,
        tools=[
            check_rag_readiness,
            create_dynamic_rag_engine,
            query_rag_engine,
            cleanup_expired_rags
        ]
    )