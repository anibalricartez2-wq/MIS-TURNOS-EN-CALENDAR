import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Rotaciones Aníbal", layout="wide")

# Inicializamos las credenciales en la memoria de la app
if 'access_token' not in st.session_state:
    st.session_state.access_token = None

# Datos de tus Secrets
CLIENT_ID = st.secrets["google_auth"]["client_id"]
CLIENT_SECRET = st.secrets["google_auth"]["client_secret"]
REDIRECT_URI = st.secrets["google_auth"]["redirect_uri"]

# --- FUNCIONES DE AUTENTICACIÓN MANUAL ---
def get_auth_url():
    # Creamos la URL de Google a mano para evitar errores de librerías
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.events",
        "access_type": "offline",
        "prompt": "consent"
    }
    # Construimos la URL
    p = requests.Request('GET', base_url, params=params).prepare()
    return p.url

def exchange_code_for_token(code):
    # Intercambiamos el código por el token usando requests (sin intermediarios)
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    response = requests.post(token_url, data=data)
    return response.json()

# --- LÓGICA DE CONEXIÓN ---
if st.session_state.access_token is None:
    # Si Google nos mandó el código en la URL
    if "code" in st.query_params:
        res = exchange_code_for_token(st.query_params["code"])
        if "access_token" in res:
            st.session_state.access_token = res["access_token"]
            st.query_params.clear()
            st.rerun()
        else:
            st.error("No se pudo obtener el permiso de Google.")
            st.write(res) # Para ver qué error tira Google
    
    st.title("📅 Sistema de Turnos (Modo Directo)")
    st.link_button("🔑 Conectar con Google Calendar", get_auth_url())
    st.stop()

# --- SI ESTÁ CONECTADO, MOSTRAR LA APP ---
st.success("✅ ¡Conectado correctamente!")

col_config, col_vista = st.columns([1, 1.2])

with col_config:
    st.subheader("1. Configurar Rotación")
    fecha_inicio = st.date_input("¿Cuándo empezó el ciclo?", datetime.now())
    dias_a_generar = st.number_input("Días a proyectar", value=30, min_value=1)
    patron = st.text_input("Patrón (ej: MMTTFF)", "MMTTFF").upper().replace(" ", "")
    
    st.divider()
    st.subheader("2. Horarios")
    h_m = st.text_input("Mañana (M)", "07:00-15:00")
    h_t = st.text_input("Tarde (T)", "15:00-23:00")
    h_n = st.text_input("Noche (N)", "23:00-07:00")

if st.button("⚡ Generar Vista Previa"):
    resumen = []
    total_h = 0
    for i in range(dias_a_generar):
        f_actual = fecha_inicio + timedelta(days=i)
        letra = patron[i % len(patron)]
        if letra != 'F':
            horario = h_m if letra == 'M' else h_t if letra == 'T' else h_n
            try:
                inicio, fin = horario.split("-")
                resumen.append({
                    "Fecha": f_actual.strftime("%Y-%m-%d"),
                    "Turno": f"Turno {letra}",
                    "Inicio": inicio, "Fin": fin, "Horas": 8
                })
                total_h += 8
            except: continue
    st.session_state.lista_turnos = resumen
    st.session_state.total_h = total_h

if 'lista_turnos' in st.session_state:
    with col_vista:
        st.subheader("3. Resumen")
        st.dataframe(pd.DataFrame(st.session_state.lista_turnos), hide_index=True)
        st.metric("Total Horas", f"{st.session_state.total_h} hs")
        
        if st.button("🚀 SUBIR A GOOGLE CALENDAR", type="primary"):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            with st.spinner("Subiendo..."):
                try:
                    for ev in st.session_state.lista_turnos:
                        body = {
                            "summary": ev["Turno"],
                            "start": {"dateTime": f"{ev['Fecha']}T{ev['Inicio']}:00", "timeZone": "America/Argentina/Catamarca"},
                            "end": {"dateTime": f"{ev['Fecha']}T{ev['Fin']}:00", "timeZone": "America/Argentina/Catamarca"},
                        }
                        requests.post("https://www.googleapis.com/calendar/v3/calendars/primary/events", json=body, headers=headers)
                    st.balloons()
                    st.success("¡Calendario actualizado!")
                except Exception as e:
                    st.error(f"Error: {e}")
