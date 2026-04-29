import streamlit as st
import pandas as pd
from datetime import datetime
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Planificador de Turnos Pro", layout="wide")

# 1. Configuración de Google desde Secrets
try:
    CLIENT_CONFIG = {
        "web": {
            "client_id": st.secrets["google_auth"]["client_id"],
            "client_secret": st.secrets["google_auth"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    REDIRECT_URI = st.secrets["google_auth"]["redirect_uri"]
except:
    st.error("Faltan los Secrets en Streamlit Cloud.")
    st.stop()

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# --- LÓGICA DE SESIÓN ---
if 'agenda' not in st.session_state:
    st.session_state.agenda = {}
if 'df_turnos' not in st.session_state:
    st.session_state.df_turnos = pd.DataFrame([
        {"Turno": "Mañana", "Inicio": "07:00", "Fin": "15:00", "Horas": 8},
        {"Turno": "Tarde", "Inicio": "19:00", "Fin": "23:00", "Horas": 4},
        {"Turno": "Guardia", "Inicio": "08:00", "Fin": "20:00", "Horas": 12}
    ])

# --- AUTENTICACIÓN ---
def autenticar():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    
    if "code" not in st.query_params:
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        st.title("📅 Bienvenida/o al Organizador")
        st.link_button("🔑 Conectar con Google Calendar", auth_url)
        st.stop()
    else:
        if 'credentials' not in st.session_state:
            try:
                flow.fetch_token(code=st.query_params["code"])
                st.session_state.credentials = flow.credentials
            except:
                st.error("Error al obtener el permiso de Google. Probá recargando la página.")
                st.stop()

autenticar()
service = build('calendar', 'v3', credentials=st.session_state.credentials)

# --- INTERFAZ ---
st.title("🛠️ Gestión de Turnos")

# Sidebar para editar turnos
st.sidebar.header("Configurar Turnos")
turnos_editados = st.sidebar.data_editor(st.session_state.df_turnos, num_rows="dynamic")
st.session_state.df_turnos = turnos_editados

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("Seleccionar Día")
    fecha = st.date_input("Día:", value=datetime.now())
    tipo = st.selectbox("Turno:", turnos_editados["Turno"])
    
    if st.button("✅ Confirmar Día"):
        st.session_state.agenda[fecha.strftime("%Y-%m-%d")] = tipo
        st.success(f"Día {fecha.day} anotado.")

with col2:
    st.subheader("Resumen del Mes")
    if st.session_state.agenda:
        resumen = []
        for f, t in st.session_state.agenda.items():
            h = turnos_editados[turnos_editados["Turno"] == t]["Horas"].values[0]
            resumen.append({"Fecha": f, "Turno": t, "Horas": h})
        
        df_res = pd.DataFrame(resumen).sort_values("Fecha")
        st.dataframe(df_res, use_container_width=True, hide_index=True)
        
        total = df_res["Horas"].sum()
        st.metric("Total Horas", f"{total} hs", f"{130 - total} para el límite")
        
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.agenda = {}
            st.rerun()
    else:
        st.info("Todavía no cargaste días.")

# --- SUBIR A GOOGLE ---
st.divider()
if st.button("🚀 SUBIR TODO A GOOGLE CALENDAR", type="primary"):
    if not st.session_state.agenda:
        st.warning("No hay turnos cargados.")
    else:
        with st.spinner("Sincronizando..."):
            try:
                for f_str, t_nombre in st.session_state.agenda.items():
                    info = turnos_editados[turnos_editados["Turno"] == t_nombre].iloc[0]
                    evento = {
                        'summary': f'Turno: {t_nombre}',
                        'start': {'dateTime': f'{f_str}T{info["Inicio"]}:00', 'timeZone': 'America/Argentina/Catamarca'},
                        'end': {'dateTime': f'{f_str}T{info["Fin"]}:00', 'timeZone': 'America/Argentina/Catamarca'},
                    }
                    service.events().insert(calendarId='primary', body=evento).execute()
                st.balloons()
                st.success("¡Sincronizado!")
                st.session_state.agenda = {}
            except Exception as e:
                st.error(f"Error al subir: {e}")
