#!/usr/bin/env python3
"""
FastAPI endpoint for Resume Agent
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
import logging
import os
import tempfile
import shutil
import requests
import zipfile
import uuid
import hashlib
from dotenv import load_dotenv
from resume_agent.graph import build_graph, TailorState, LLMQuotaExceededError

# Load environment variables from .env file
load_dotenv()

# Configure logging FIRST before anything else
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # Simple format without timestamps for cleaner output
    force=True,  # Override any existing logging configuration
)
logger = logging.getLogger(__name__)

# Create cache directory for resume templates
CACHE_DIR = os.path.join(os.getcwd(), ".resume_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Cache version - increment this when you want to invalidate all caches
CACHE_VERSION = "v3"  # Increment to force fresh template download

# Initialize FastAPI app
app = FastAPI(title="Resume Agent API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Allow all origins in development. In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Initialize Firebase Admin SDK
# Note: Set FIREBASE_CREDENTIALS_PATH environment variable to your Firebase service account JSON
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
if firebase_credentials_path and os.path.exists(firebase_credentials_path):
    # Check if Firebase app is already initialized (important for reload mode)
    try:
        firebase_admin.get_app()
        logger.info("Firebase Admin SDK already initialized")
    except ValueError:
        # App doesn't exist, initialize it
        cred = credentials.Certificate(firebase_credentials_path)
        firebase_admin.initialize_app(
            cred, {"storageBucket": "resume-generator-492c5.firebasestorage.app"}
        )
        logger.info("Firebase Admin SDK initialized")
    
    db = firestore.client()
    bucket = storage.bucket()
else:
    logger.warning("Firebase credentials not found. Authentication will be disabled.")
    db = None
    bucket = None


class GenerateRequest(BaseModel):
    """Request model for resume generation"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobId": "12345678-1234-1234-1234-123456789abc",
                "companyName": "Tech Corp",
                "jobTitle": "Senior Software Engineer",
                "jobUrl": "https://example.com/job/12345",
                "jobDescription": "We are looking for...",
                "resumeZipUrl": "https://firebasestorage.googleapis.com/.../resume.zip",
                "generateResume": True,
                "generateCoverLetter": True,
                "generateEmail": False,
            }
        },
        populate_by_name=True,
    )

    job_id: Optional[str] = Field(
        None, alias="jobId", description="Existing job ID for regeneration (optional)"
    )
    company_name: str = Field(
        ..., alias="companyName", description="Name of the company"
    )
    job_title: str = Field(..., alias="jobTitle", description="Job title/position")
    job_url: Optional[str] = Field(
        None, alias="jobUrl", description="URL of the job posting"
    )
    job_description: str = Field(
        ..., alias="jobDescription", description="Job description text"
    )
    resume_zip_url: str = Field(
        ...,
        alias="resumeZipUrl",
        description="Firebase storage URL to resume template zip file",
    )
    generate_resume: bool = Field(
        default=True, alias="generateResume", description="Generate resume"
    )
    generate_cover_letter: bool = Field(
        default=False, alias="generateCoverLetter", description="Generate cover letter"
    )
    generate_email: bool = Field(
        default=False, alias="generateEmail", description="Generate email"
    )


class GenerateResponse(BaseModel):
    """Response model for resume generation"""

    status: str = Field(..., description="Status of the request")
    message: str = Field(..., description="Response message")
    job_id: Optional[str] = Field(
        None, description="Job ID for tracking the generation process"
    )
    resume_pdf_url: Optional[str] = Field(
        None, description="URL of the generated resume PDF"
    )


async def verify_firebase_token(authorization: str = Header(None)) -> str:
    """
    Verify Firebase authentication token

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        user_id: Verified Firebase user ID

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        # Extract token from "Bearer <token>" format
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme. Use Bearer token",
            )

        # Verify the token with Firebase
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token["uid"]

        logger.info(f"Authenticated user: {user_id}")
        return user_id

    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Resume Agent API",
        "version": "1.0.0",
        "endpoints": {"generate": "/api/v1/generate"},
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/api/v1/generate", response_model=GenerateResponse)
async def generate_resume(
    request: GenerateRequest,
    authenticated_user_id: str = Depends(verify_firebase_token),
):
    """
    Generate resume, cover letter, and/or email based on job description

    Args:
        request: GenerateRequest containing job details and items to generate
        authenticated_user_id: User ID from Firebase authentication (auto-injected)

    Returns:
        GenerateResponse with status and generated file information
    """
    logger.info("=" * 80)
    logger.info("NEW GENERATE REQUEST RECEIVED")
    logger.info("=" * 80)

    try:
        # Build list of items to generate
        generate_items = []
        if request.generate_resume:
            generate_items.append("resume")
        if request.generate_cover_letter:
            generate_items.append("cover_letter")
        if request.generate_email:
            generate_items.append("email")

        if not generate_items:
            raise HTTPException(
                status_code=400, detail="At least one generation option must be enabled"
            )

        logger.info(f"✓ Authenticated User: {authenticated_user_id}")
        logger.info(f"✓ Company: {request.company_name}")
        logger.info(f"✓ Job Title: {request.job_title}")
        logger.info(f"✓ Job URL: {request.job_url or 'Not provided'}")
        logger.info(f"✓ Job Description: {request.job_description[:100]}...")
        logger.info(f"✓ Resume Zip URL: {request.resume_zip_url}")
        logger.info(f"✓ Generate Items: {', '.join(generate_items)}")

        # Use provided job ID for regeneration, or generate a new one
        is_regeneration = bool(request.job_id)
        job_id = request.job_id if is_regeneration else str(uuid.uuid4())
        old_resume_pdf_url = None
        
        if is_regeneration:
            logger.info(f"✓ Regenerating existing job: {job_id}")
            
            # Verify the job exists and belongs to this user
            try:
                existing_app = (
                    db.collection("job_applied")
                    .document(authenticated_user_id)
                    .collection("applications")
                    .document(job_id)
                    .get()
                )
                
                if not existing_app.exists:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Job ID {job_id} not found for this user"
                    )
                
                # Store old PDF URL for deletion later
                existing_data = existing_app.to_dict()
                old_resume_pdf_url = existing_data.get("resume_pdf_url")
                logger.info(f"Old resume PDF URL: {old_resume_pdf_url}")
                
                logger.info("✓ Existing job found. Proceeding with regeneration...")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error verifying existing job: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to verify existing job: {str(e)}"
                )
        else:
            logger.info(f"✓ Creating new job: {job_id}")

        # Only generate resume for now (cover letter and email will be implemented later)
        if request.generate_resume:
            logger.info("Starting resume generation...")

            # Create temporary directories
            temp_dir = tempfile.mkdtemp(prefix=f"resume_job_{job_id}_")
            resume_dir = os.path.join(temp_dir, "resume_template")
            output_dir = os.path.join(temp_dir, "output")
            jd_path = os.path.join(temp_dir, "job_description.txt")

            try:
                # 1. Download and extract resume zip (with caching)
                # Create a hash of the URL to use as cache key (including cache version)
                cache_key = f"{request.resume_zip_url}_{CACHE_VERSION}"
                url_hash = hashlib.md5(cache_key.encode()).hexdigest()
                cached_zip = os.path.join(CACHE_DIR, f"{url_hash}.zip")
                cached_extracted = os.path.join(CACHE_DIR, f"{url_hash}_extracted")

                # Check if already cached
                if os.path.exists(cached_extracted) and os.path.isdir(cached_extracted):
                    logger.info(
                        f"✓ Using cached resume template (hash: {url_hash[:8]}..., version: {CACHE_VERSION})"
                    )
                    # Copy from cache to temp directory
                    shutil.copytree(cached_extracted, resume_dir)
                else:
                    logger.info("Downloading resume template zip...")
                    response = requests.get(request.resume_zip_url, timeout=30)
                    response.raise_for_status()

                    # Save to cache
                    with open(cached_zip, "wb") as f:
                        f.write(response.content)

                    logger.info("Extracting resume template...")
                    os.makedirs(cached_extracted, exist_ok=True)
                    with zipfile.ZipFile(cached_zip, "r") as zip_ref:
                        zip_ref.extractall(cached_extracted)

                    logger.info(f"✓ Resume template cached (hash: {url_hash[:8]}..., version: {CACHE_VERSION})")

                    # Copy from cache to temp directory
                    shutil.copytree(cached_extracted, resume_dir)

                # Find the actual template directory (may be nested)
                template_contents = os.listdir(resume_dir)
                if len(template_contents) == 1 and os.path.isdir(
                    os.path.join(resume_dir, template_contents[0])
                ):
                    resume_dir = os.path.join(resume_dir, template_contents[0])

                # 2. Create job description file
                logger.info("Creating job description file...")
                with open(jd_path, "w") as f:
                    f.write(request.job_description)

                # 3. Use profile.json from workspace
                profile_path = os.path.join(os.getcwd(), "profile.json")
                if not os.path.exists(profile_path):
                    raise HTTPException(
                        status_code=500, detail="profile.json not found in workspace"
                    )

                # 4. Create output directory
                os.makedirs(output_dir, exist_ok=True)

                # 5. Build and run the resume generation graph
                logger.info("Running resume generation workflow...")
                state = TailorState(
                    job_description_path=jd_path,
                    job_url=request.job_url,
                    company_name=request.company_name,
                    resume_root_dir=resume_dir,
                    profile_json_path=profile_path,
                    output_dir=output_dir,
                    output_pdf_path=os.path.join(output_dir, "resume.pdf"),
                )

                graph = build_graph()
                
                try:
                    final_state = graph.invoke(state)
                    
                    # Check for error status in final state
                    if final_state.get("error_status"):
                        error_msg = final_state.get("error_status")
                        logger.error(f"Resume generation failed: {error_msg}")
                        raise Exception(error_msg)
                    
                except LLMQuotaExceededError as e:
                    logger.error("=" * 60)
                    logger.error("PROCESS STOPPED: LLM API Quota Exhausted")
                    logger.error("=" * 60)
                    logger.error(f"Error: {e}")
                    
                    # Update Firebase job status to failed if regeneration
                    if is_regeneration:
                        app_ref = (
                            db.collection("job_applied")
                            .document(authenticated_user_id)
                            .collection("applications")
                            .document(job_id)
                        )
                        app_ref.update({
                            "status": "failed",
                            "error": f"LLM API Quota Exhausted: {str(e)}",
                            "failed_at": firestore.SERVER_TIMESTAMP,
                        })
                    
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail={
                            "error": "LLM_QUOTA_EXHAUSTED",
                            "message": "Your LLM API quota has been exhausted. Please check your API provider's plan and billing details."
                        }
                    )
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Resume generation error: {error_msg}")
                    
                    # Check if this is an LLM failure
                    if "LLM_FAILURE" in error_msg or "RATE_LIMIT_EXCEEDED" in error_msg or "Gemini API" in error_msg:
                        logger.error("=" * 60)
                        logger.error("PROCESS STOPPED: LLM Service Failed")
                        logger.error("=" * 60)
                        
                        # Update Firebase job status to failed if regeneration
                        if is_regeneration:
                            app_ref = (
                                db.collection("job_applied")
                                .document(authenticated_user_id)
                                .collection("applications")
                                .document(job_id)
                            )
                            app_ref.update({
                                "status": "failed",
                                "error": error_msg,
                                "failed_at": firestore.SERVER_TIMESTAMP,
                            })
                        
                        raise HTTPException(
                            status_code=503,  # Service Unavailable
                            detail={
                                "error": "LLM_SERVICE_FAILED",
                                "message": f"Resume generation failed due to LLM service error. Please try again later. Details: {error_msg}"
                            }
                        )
                    
                    # Other unexpected errors
                    logger.error(f"Unexpected error during resume generation: {e}")
                    
                    if is_regeneration:
                        app_ref = (
                            db.collection("job_applied")
                            .document(authenticated_user_id)
                            .collection("applications")
                            .document(job_id)
                        )
                        app_ref.update({
                            "status": "failed",
                            "error": str(e),
                            "failed_at": firestore.SERVER_TIMESTAMP,
                        })
                    
                    raise HTTPException(
                        status_code=500,
                        detail=f"Resume generation failed: {str(e)}"
                    )

                # Check if PDF was generated
                pdf_path = final_state.get("output_pdf_path", state.output_pdf_path)
                if not os.path.exists(pdf_path):
                    raise HTTPException(
                        status_code=500,
                        detail="Resume PDF generation failed. Check logs.",
                    )

                logger.info(f"✓ Resume PDF generated at: {pdf_path}")

                # 6. Delete old PDF from Firebase Storage if regeneration
                if is_regeneration and old_resume_pdf_url:
                    try:
                        logger.info("Deleting old PDF from Firebase Storage...")
                        logger.info(f"Old PDF URL to delete: {old_resume_pdf_url}")
                        # Extract the storage path from the public URL
                        # URL format: https://storage.googleapis.com/{bucket}/users/{user_id}/generated_resumes/{filename}
                        if "/generated_resumes/" in old_resume_pdf_url:
                            # Extract path after bucket name
                            path_parts = old_resume_pdf_url.split("/generated_resumes/")
                            if len(path_parts) > 1:
                                filename = path_parts[1].split("?")[0]  # Remove query params if any
                                old_storage_path = f"users/{authenticated_user_id}/generated_resumes/{filename}"
                                logger.info(f"Attempting to delete: {old_storage_path}")
                                
                                old_blob = bucket.blob(old_storage_path)
                                if old_blob.exists():
                                    old_blob.delete()
                                    logger.info(f"✓ Old PDF deleted: {old_storage_path}")
                                else:
                                    logger.warning(f"Old PDF not found in storage: {old_storage_path}")
                            else:
                                logger.warning(f"Could not extract filename from URL: {old_resume_pdf_url}")
                        else:
                            logger.warning(f"URL does not contain '/generated_resumes/': {old_resume_pdf_url}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old PDF: {e}")
                        import traceback
                        logger.warning(traceback.format_exc())
                        # Continue with upload even if deletion fails
                elif is_regeneration:
                    logger.warning("Regeneration requested but no old_resume_pdf_url found")

                # 7. Upload PDF to Firebase Storage
                logger.info("Uploading PDF to Firebase Storage...")

                # Get user display name from Firebase Auth
                # try:
                #     # user_record = auth.get_user(authenticated_user_id)
                #     # user_name = (
                #     #     user_record.display_name or user_record.email.split("@")[0]
                #     #     if user_record.email
                #     #     else authenticated_user_id[:8]
                #     # )
                #     user_name = "Karthik_Maganahalli_Prakash"
                # except Exception as e:
                #     logger.warning(f"Could not fetch user name: {e}")
                #     user_name = authenticated_user_id[:8]

                # Sanitize filename components
                safe_user_name = "Karthik_Maganahalli_Prakash"
                safe_company_name = request.company_name.replace(" ", "_").replace(
                    "/", "_"
                )
                safe_job_title = request.job_title.replace(" ", "_").replace("/", "_")

                # Add timestamp to filename to prevent caching issues on regeneration
                import time
                timestamp = int(time.time())
                filename = f"{safe_user_name}-{safe_company_name}-{safe_job_title}-{timestamp}.pdf"
                storage_path = (
                    f"users/{authenticated_user_id}/generated_resumes/{filename}"
                )

                blob = bucket.blob(storage_path)
                blob.upload_from_filename(pdf_path, content_type="application/pdf")
                blob.make_public()

                resume_pdf_url = blob.public_url
                logger.info(f"✓ PDF uploaded to: {resume_pdf_url}")

                # 8. Save job data to Firestore
                if is_regeneration:
                    logger.info("Updating job data in Firestore...")
                    
                    # Update existing job data
                    job_ref = db.collection("jobs").document(job_id)
                    job_ref.update({
                        "company_name": request.company_name,
                        "job_title": request.job_title,
                        "job_url": request.job_url,
                        "job_description": request.job_description,
                        "company_summary": state.company_summary,
                        "company_citations": state.citations,
                        "updated_at": firestore.SERVER_TIMESTAMP,
                    })
                    logger.info("✓ Job data updated in 'jobs' collection")
                    
                    # Update application data
                    app_ref = (
                        db.collection("job_applied")
                        .document(authenticated_user_id)
                        .collection("applications")
                        .document(job_id)
                    )
                    app_ref.update({
                        "resume_pdf_url": resume_pdf_url,
                        "generated_items": generate_items,
                        "regenerated_at": firestore.SERVER_TIMESTAMP,
                        "status": "completed",
                    })
                    logger.info("✓ Application data updated in 'job_applied' collection")
                else:
                    logger.info("Saving job data to Firestore...")

                    # Save to "jobs" collection - contains job details
                    job_data = {
                        "company_name": request.company_name,
                        "job_title": request.job_title,
                        "job_url": request.job_url,
                        "job_description": request.job_description,
                        "company_summary": state.company_summary,
                        "company_citations": state.citations,
                        "created_at": firestore.SERVER_TIMESTAMP,
                    }

                    db.collection("jobs").document(job_id).set(job_data)
                    logger.info("✓ Job data saved to 'jobs' collection")

                    # Save to "job_applied" collection - tracks user applications
                    # Structure: job_applied/{user_id}/{job_id} = application data
                    application_data = {
                        "job_id": job_id,
                        "user_id": authenticated_user_id,
                        "resume_zip_url": request.resume_zip_url,
                        "resume_pdf_url": resume_pdf_url,
                        "generated_items": generate_items,
                        "applied_at": firestore.SERVER_TIMESTAMP,
                        "status": "completed",
                    }

                    db.collection("job_applied").document(authenticated_user_id).collection(
                        "applications"
                    ).document(job_id).set(application_data)
                    logger.info("✓ Application data saved to 'job_applied' collection")

            finally:
                # Copy generated files to Resume/ directory for inspection
                try:
                    resume_output_dir = os.path.join(os.getcwd(), "Resume")
                    os.makedirs(resume_output_dir, exist_ok=True)
                    
                    # Copy the entire output directory with job_id in the name
                    output_copy_dir = os.path.join(resume_output_dir, f"job_{job_id[:8]}")
                    if os.path.exists(output_dir):
                        # Remove old copy if exists
                        if os.path.exists(output_copy_dir):
                            shutil.rmtree(output_copy_dir, ignore_errors=True)
                        shutil.copytree(output_dir, output_copy_dir)
                        logger.info(f"✓ Generated files copied to: {output_copy_dir}")
                except Exception as e:
                    logger.warning(f"Failed to copy generated files: {e}")
                
                # Cleanup temporary directory
                logger.info("Cleaning up temporary files...")
                shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info("✓ Request processed successfully")
            logger.info("=" * 80)

            return GenerateResponse(
                status="success",
                message="Resume regenerated successfully" if is_regeneration else "Resume generated successfully",
                job_id=job_id,
                resume_pdf_url=resume_pdf_url,
            )
        else:
            # TODO: Implement cover letter and email generation
            logger.info("Cover letter and email generation not yet implemented")
            logger.info("✓ Request processed successfully")
            logger.info("=" * 80)

            return GenerateResponse(
                status="success",
                message="Only resume generation is currently supported",
                job_id=job_id,
                resume_pdf_url=None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing generate request: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error traceback:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, log_level="info", access_log=True, reload=True)
