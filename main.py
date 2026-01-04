import streamlit as st
import pandas as pd
import joblib
import os

from database import init_db, fetch_history, save_history
from auth_utils import register_user, authenticate
from ocr_utils import ocr_to_row
from pdf_utils import generate_pdf

# ----------------- INIT -----------------
st.set_page_config(page_title="Heart Disease Risk App", layout="wide")
init_db()

MODEL_PATH = "models/best_rf_calibrated.pkl"
PREPROCESSOR_PATH = "models/preprocessor.pkl"
UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

model = joblib.load(MODEL_PATH)
preprocessor = joblib.load(PREPROCESSOR_PATH)

FEATURES = [
    "Age","Sex","ChestPainType","RestingBP","Cholesterol",
    "FastingBS","RestingECG","MaxHR","ExerciseAngina","Oldpeak","ST_Slope"
]

def get_risk(prob):
    if prob < 0.3:
        return "Low"
    elif prob < 0.6:
        return "Moderate"
    return "High"

# ----------------- SESSION STATE -----------------
if "user" not in st.session_state:
    st.session_state.user = None

if "ocr_row" not in st.session_state:
    st.session_state.ocr_row = None

# ----------------- AUTH -----------------
def login_page():
    st.title("Login")

    email = st.text_input("Email", key="login_email")
    pwd = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="login_btn"):
        user = authenticate(email, pwd)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid credentials")

def register_page():
    st.title("Register")

    email = st.text_input("Email", key="register_email")
    pwd = st.text_input("Password", type="password", key="register_password")

    if st.button("Register", key="register_btn"):
        success = register_user(email, pwd)

        if success:
            st.success("Registered successfully! Please login.")
        else:
            st.warning("Email already registered. Please login instead.")


# ----------------- ML PREDICTION -----------------
def predict_from_row(row: dict):
    df = pd.DataFrame([row], columns=FEATURES)
    X = preprocessor.transform(df)
    prob = model.predict_proba(X)[0][1]
    return prob, get_risk(prob)

# ----------------- PATIENT DASHBOARD -----------------
def patient_dashboard():
    st.sidebar.title("Patient Menu")
    choice = st.sidebar.radio(
        "Select Option",
        ["Manual Input", "Upload Report (OCR)", "My History"],
        key="patient_menu"
    )

    # ---------- MANUAL INPUT ----------
    if choice == "Manual Input":
        st.subheader("Manual Clinical Data Entry")

        row = {
            "Age": st.number_input("Age", 1, 120, 45, key="age"),
            "Sex": st.selectbox("Sex", ["M","F"], key="sex"),
            "ChestPainType": st.selectbox("Chest Pain Type", ["ATA","NAP","ASY","TA"], key="cp"),
            "RestingBP": st.number_input("Resting Blood Pressure", 80, 250, 120, key="bp"),
            "Cholesterol": st.number_input("Cholesterol", 100, 600, 200, key="chol"),
            "FastingBS": st.selectbox("Fasting Blood Sugar (0/1)", [0,1], key="fbs"),
            "RestingECG": st.selectbox("Resting ECG", ["Normal","ST","LVH"], key="ecg"),
            "MaxHR": st.number_input("Max Heart Rate", 60, 220, 150, key="maxhr"),
            "ExerciseAngina": st.selectbox("Exercise Induced Angina", ["N","Y"], key="angina"),
            "Oldpeak": st.number_input("Oldpeak (ST Depression)", 0.0, 6.0, 0.0, key="oldpeak"),
            "ST_Slope": st.selectbox("ST Slope", ["Up","Flat","Down"], key="slope")
        }

        if st.button("Predict Risk", key="manual_predict"):
            prob, risk = predict_from_row(row)
            save_history(st.session_state.user[0], prob, risk)

            st.success(f"Risk Level: **{risk}**")
            st.info(f"Probability: {prob:.3f}")

            pdf_path = generate_pdf(row, prob, risk, "manual_report.pdf")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "📄 Download PDF Report",
                    f,
                    file_name="Heart_Risk_Report.pdf",
                    mime="application/pdf"
                )

    # ---------- OCR UPLOAD ----------
    elif choice == "Upload Report (OCR)":
        st.subheader("Upload Medical Report")

        file = st.file_uploader(
            "Upload PDF / Image",
            type=["pdf","png","jpg","jpeg"],
            key="ocr_upload"
        )

        if file:
            path = os.path.join(UPLOAD_DIR, file.name)
            with open(path, "wb") as f:
                f.write(file.getbuffer())

            with st.spinner("Extracting data using OCR..."):
                st.session_state.ocr_row = ocr_to_row(path)

            st.success("OCR extraction completed")

        if st.session_state.ocr_row:
            st.subheader("Verify Extracted Values")

            temp = {}
            for k, v in st.session_state.ocr_row.items():
                temp[k] = st.text_input(
                    k,
                    value="" if v is None else str(v),
                    key=f"ocr_{k}"
                )

            if st.button("Confirm & Predict", key="ocr_predict"):
                clean_row = {
                    "Age": int(temp["Age"]),
                    "Sex": temp["Sex"],
                    "ChestPainType": temp["ChestPainType"],
                    "RestingBP": float(temp["RestingBP"]),
                    "Cholesterol": float(temp["Cholesterol"]),
                    "FastingBS": int(temp["FastingBS"]),
                    "RestingECG": temp["RestingECG"],
                    "MaxHR": int(temp["MaxHR"]),
                    "ExerciseAngina": temp["ExerciseAngina"],
                    "Oldpeak": float(temp["Oldpeak"]),
                    "ST_Slope": temp["ST_Slope"]
                }

                prob, risk = predict_from_row(clean_row)
                save_history(st.session_state.user[0], prob, risk)

                st.success(f"Risk Level: **{risk}**")
                st.info(f"Probability: {prob:.3f}")

                pdf_path = generate_pdf(clean_row, prob, risk, "ocr_report.pdf")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📄 Download PDF Report",
                        f,
                        file_name="Heart_Risk_Report.pdf",
                        mime="application/pdf"
                    )

                st.session_state.ocr_row = None

    # ---------- HISTORY ----------
    else:
        st.subheader("My Prediction History")
        data = fetch_history(st.session_state.user[0])

        if data:
            df = pd.DataFrame(
                data,
                columns=["ID","UserID","Probability","Risk","Timestamp"]
            )
            st.dataframe(df)
        else:
            st.info("No predictions yet.")

# ----------------- ADMIN DASHBOARD -----------------
def admin_dashboard():
    st.sidebar.title("Admin Menu")
    choice = st.sidebar.radio(
        "Select Option",
        ["All History", "Analytics"],
        key="admin_menu"
    )

    data = fetch_history()
    df = pd.DataFrame(
        data,
        columns=["ID","UserID","Probability","Risk","Timestamp"]
    )

    if choice == "All History":
        st.subheader("All Patient Predictions")
        st.dataframe(df)
    else:
        st.subheader("System Analytics")
        st.metric("Total Predictions", len(df))
        st.bar_chart(df["Risk"].value_counts())

# ----------------- MAIN -----------------
if not st.session_state.user:
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        login_page()
    with tab2:
        register_page()
else:
    user = st.session_state.user
    st.sidebar.success(f"Logged in as {user[1]} ({user[3]})")

    if user[3] == "doctor":
        admin_dashboard()
    else:
        patient_dashboard()

