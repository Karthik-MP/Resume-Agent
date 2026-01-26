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
from resume_agent.graph import build_graph, TailorState

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

        # Generate unique job ID
        job_id = str(uuid.uuid4())
        logger.info(f"✓ Job ID: {job_id}")

        # Fetch user data from Firestore
        user_data = None
        if db:
            try:
                logger.info(f"Fetching user data from Firestore for user: {authenticated_user_id}")
                user_doc = db.collection("users").document(authenticated_user_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    logger.info("✓ User data fetched successfully")
                else:
                    logger.warning(f"User document not found for user: {authenticated_user_id}")
            except Exception as e:
                logger.error(f"Error fetching user data from Firestore: {str(e)}")
                # Continue without user data - will fall back to profile.json

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
                # Create a hash of the URL to use as cache key
                url_hash = hashlib.md5(request.resume_zip_url.encode()).hexdigest()
                cached_zip = os.path.join(CACHE_DIR, f"{url_hash}.zip")
                cached_extracted = os.path.join(CACHE_DIR, f"{url_hash}_extracted")

                # Check if already cached
                if os.path.exists(cached_extracted) and os.path.isdir(cached_extracted):
                    logger.info(
                        f"✓ Using cached resume template (hash: {url_hash[:8]}...)"
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

                    logger.info(f"✓ Resume template cached (hash: {url_hash[:8]}...)")

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
                    user_data=user_data,  # Pass Firebase user data
                )

                graph = build_graph()
                final_state = graph.invoke(state)

                # Check if PDF was generated
                pdf_path = final_state.get("output_pdf_path", state.output_pdf_path)
                if not os.path.exists(pdf_path):
                    raise HTTPException(
                        status_code=500,
                        detail="Resume PDF generation failed. Check logs.",
                    )

                logger.info(f"✓ Resume PDF generated at: {pdf_path}")

                # 6. Upload PDF to Firebase Storage
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

                filename = f"{safe_user_name}-{safe_company_name}-{safe_job_title}.pdf"
                storage_path = (
                    f"users/{authenticated_user_id}/generated_resumes/{filename}"
                )

                blob = bucket.blob(storage_path)
                blob.upload_from_filename(pdf_path, content_type="application/pdf")
                blob.make_public()

                resume_pdf_url = blob.public_url
                logger.info(f"✓ PDF uploaded to: {resume_pdf_url}")

                # 7. Save job data to Firestore
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
                # Cleanup temporary directory
                logger.info("Cleaning up temporary files...")
                shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info("✓ Request processed successfully")
            logger.info("=" * 80)

            return GenerateResponse(
                status="success",
                message="Resume generated successfully",
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
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info", access_log=True)
