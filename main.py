from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import engine, get_db
import re
from google_sheets import sync_forms_to_sheet
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Form Management API",
    description="API for managing forms with Google Sheets integration",
    version="1.0.0"
)

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "https://lunar-front.vercel.app",
    "https://lunar-front-git-main-your-username.vercel.app",
    "https://lunar-front-*.vercel.app",
    "*"
]

# Add CORS middleware with full configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.middleware("http")
async def cors_debug_middleware(request: Request, call_next):
    logger.info(f"Request headers: {request.headers}")
    response = await call_next(request)
    logger.info(f"Response headers: {response.headers}")
    
    # Ensure CORS headers are present for all responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

@app.options("/{path:path}")
async def options_handler(path: str):
    return JSONResponse(
        status_code=200,
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        },
    )

# Add Gzip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # In production, you should specify your actual domains
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

def validate_phone_number(phone: str) -> bool:
    # Basic phone number validation
    pattern = re.compile(r'^\+?1?\d{9,15}$')
    return bool(pattern.match(phone))

def validate_email(email: str) -> bool:
    # Basic email validation
    pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(pattern.match(email))

def sync_to_sheets_background(forms):
    sync_forms_to_sheet(forms)

@app.get("/")
def read_root():
    return {"message": "Welcome to Form Management API"}

@app.post("/forms/", response_model=schemas.Form, status_code=status.HTTP_201_CREATED)
def create_form(form: schemas.FormCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not validate_email(form.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if not validate_phone_number(form.phone_number):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    db_form = models.Form(**form.model_dump())
    db.add(db_form)
    db.commit()
    db.refresh(db_form)
    
    # Sync to Google Sheets in background
    forms = db.query(models.Form).all()
    background_tasks.add_task(sync_to_sheets_background, forms)
    
    return db_form

@app.get("/forms/", response_model=List[schemas.Form])
def get_forms(background_tasks: BackgroundTasks, db: Session = Depends(get_db), skip: int = 0, limit: int = 10):
    forms = db.query(models.Form).offset(skip).limit(limit).all()
    
    # Sync to Google Sheets in background
    background_tasks.add_task(sync_to_sheets_background, forms)
    
    return forms

@app.get("/forms/{form_id}", response_model=schemas.Form)
def get_form(form_id: int, db: Session = Depends(get_db)):
    form = db.query(models.Form).filter(models.Form.id == form_id).first()
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return form

@app.put("/forms/{form_id}", response_model=schemas.Form)
def update_form(form_id: int, form: schemas.FormUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_form = db.query(models.Form).filter(models.Form.id == form_id).first()
    if db_form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    
    update_data = form.model_dump(exclude_unset=True)
    
    # Validate email and phone if they are being updated
    if "email" in update_data and not validate_email(update_data["email"]):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if "phone_number" in update_data and not validate_phone_number(update_data["phone_number"]):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    for key, value in update_data.items():
        setattr(db_form, key, value)
    
    db.commit()
    db.refresh(db_form)
    
    # Sync to Google Sheets in background
    forms = db.query(models.Form).all()
    background_tasks.add_task(sync_to_sheets_background, forms)
    
    return db_form

@app.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form(form_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    form = db.query(models.Form).filter(models.Form.id == form_id).first()
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    
    db.delete(form)
    db.commit()
    
    # Sync to Google Sheets in background
    forms = db.query(models.Form).all()
    background_tasks.add_task(sync_to_sheets_background, forms)
    
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile=None,  # Add your SSL key file path for HTTPS
        ssl_certfile=None,  # Add your SSL certificate file path for HTTPS
        reload=True  # Enable auto-reload for development
    )
