from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import engine, get_db
import re
from google_sheets import sync_forms_to_sheet

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Form Management API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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
    uvicorn.run(app, host="0.0.0.0", port=8000)
