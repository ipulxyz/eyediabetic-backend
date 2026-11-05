import base64
from datetime import datetime
from io import BytesIO
import json
import os
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
import firebase_admin
from firebase_admin import credentials, firestore
from PIL import Image

# 1. Inisialisasi Firebase Admin SDK (Mendukung Lokal & Cloud)
if not firebase_admin._apps:
    if os.path.exists("serviceAccountKey.json"):
        # Jika dijalankan di PC lokal
        cred = credentials.Certificate("serviceAccountKey.json")
    else:
        # Jika dijalankan di Cloud (Render) via Environment Variable
        cred_json = json.loads(os.environ.get("FIREBASE_CREDENTIALS_JSON"))
        cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 2. Inisialisasi FastAPI
app = FastAPI(
    title="EyeDiabetic AI Backend API",
    description="API Server untuk mengelola data pasien dan integrasi AI Retinopati Diabetik",
    version="1.0.0",
)


@app.get("/")
def read_root():
  return {
      "status": "online",
      "message": "Backend API EyeDiabetic AI Berhasil Berjalan!",
  }


# 3. Endpoint Screening dengan Kompresi Gambar
@app.post("/api/v1/screening")
async def create_screening(
    nama_pasien: str = Form(...),
    usia: int = Form(...),
    durasi_diabetes: str = Form(...),
    gula_darah: float = Form(...),
    file: UploadFile = File(...),
):
  try:
    # Read dan buka foto dengan PIL
    image_bytes = await file.read()
    img = Image.open(BytesIO(image_bytes))

    # Konversi ke RGB jika format gambar PNG/RGBA
    if img.mode in ("RGBA", "P"):
      img = img.convert("RGB")

    # Resize gambar (maksimal lebar/tinggi 800px)
    img.thumbnail((800, 800))

    # Kompres kualitas gambar ke 70%
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    compressed_bytes = buffer.getvalue()

    # Ubah gambar terkompres ke format Base64
    base64_image = base64.b64encode(compressed_bytes).decode("utf-8")

    # Data diagnosis dummy (nantinya diintegrasikan dengan model AI Ken)
    ai_diagnosis = "Proliferative DR"
    ai_confidence = 0.94
    ai_recommendation = "Rujuk ke Spesialis Retina dalam 24-48 jam"

    # Susun payload data untuk Cloud Firestore
    data_pasien = {
        "nama_pasien": nama_pasien,
        "usia": usia,
        "durasi_diabetes": durasi_diabetes,
        "gula_darah": gula_darah,
        "foto_fundus_base64": f"data:image/jpeg;base64,{base64_image}",
        "hasil_diagnosis": ai_diagnosis,
        "confidence_score": ai_confidence,
        "rekomendasi": ai_recommendation,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Simpan ke koleksi 'patients' di Firestore
    doc_ref = db.collection("patients").add(data_pasien)
    doc_id = doc_ref[1].id

    return {
        "status": "success",
        "message": "Data screening pasien berhasil disimpan ke Cloud Database!",
        "patient_id": doc_id,
        "diagnosis_result": {
            "disease_level": ai_diagnosis,
            "confidence": ai_confidence,
            "recommendation": ai_recommendation,
        },
    }
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"Terjadi kesalahan server: {str(e)}"
    )
    
    
# 4. Endpoint Ambil Semua Daftar Pasien (GET)
@app.get("/api/v1/patients")
async def get_all_patients():
  try:
    patients_ref = db.collection("patients").stream()
    patients_list = []

    for doc in patients_ref:
      patient_data = doc.to_dict()
      patient_data["id"] = doc.id
      patients_list.append(patient_data)

    return {
        "status": "success",
        "total_patients": len(patients_list),
        "data": patients_list,
    }
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"Gagal mengambil data pasien: {str(e)}"
    )


# 5. Endpoint Ambil Detail 1 Pasien Berdasarkan ID (GET)
@app.get("/api/v1/patients/{patient_id}")
async def get_patient_detail(patient_id: str):
  try:
    doc_ref = db.collection("patients").document(patient_id).get()

    if not doc_ref.exists:
      raise HTTPException(status_code=404, detail="Data pasien tidak ditemukan")

    patient_data = doc_ref.to_dict()
    patient_data["id"] = doc_ref.id

    return {"status": "success", "data": patient_data}
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"Gagal mengambil detail pasien: {str(e)}"
    )