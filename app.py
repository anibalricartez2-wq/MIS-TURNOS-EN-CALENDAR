import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Rotaciones Aníbal", layout="wide")

# 1. Forzar que las credenciales persistan en la memoria del servidor
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["google_auth"]["client_id"],
        "client_secret": st.secrets["google_auth"]["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
REDIRECT_URI = st.secrets["google_auth"]["redirect_uri"]

# --- FUNCIÓN DE CONEXIÓN ROBUSTA ---
def check_auth():
    if st.session_state.credentials:
        return True
    
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    
    # Si detectamos el código de Google en la URL
    if "code" in st.query_params:
        try:
            code = st.query_params["code"]
            flow.fetch_token(code=code)
            st.session_state.credentials = flow.credentials
            # Limpiamos la URL y reiniciamos para que el código desaparezca
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Error de validación: {e}")
            st.query_params.clear()
    
    # Si no hay credenciales, mostrar el botón
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    st.title("📅 Sistema de Turnos")
    st.warning("La conexión con Google no está activa.")
    st.link_button("🔑 Conectar con Google Calendar", auth_url)
    return False

# --- EJECUCIÓN ---
if check_auth():
    service = build('calendar', 'v3', credentials=st.session_state.credentials)
    
    st.title("🔄 Generador de Rotación Automática")
    st.success("✅ Conectado correctamente")

    col_config, col_vista = st.columns([1, 1.2])

    with col_config:
        st.subheader("1. Configurar Ciclo")
        fecha_inicio = st.date_input("¿Qué día empieza el ciclo?", datetime.now())
        dias_a_generar = st.number_input("Días a generar", value=30, min_value=1)
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
                inicio, fin = horario.split("-")
                resumen.append({
                    "Fecha": f_actual.strftime("%Y-%m-%d"),
                    "Turno": f"Turno {letra}",
                    "Inicio": inicio, "Fin": fin, "Horas": 8
                })
                total_h += 8
        st.session_state.lista_turnos = resumen
        st.session_state.total_h = total_h

    if 'lista_turnos' in st.session_state:
        with col_vista:
            st.subheader("3. Vista Previa")
            st.dataframe(pd.DataFrame(st.session_state.lista_turnos), hide_index=True)
            st.metric("Total Horas", f"{st.session_state.total_h} hs")
            
            if st.button("🚀 SUBIR A GOOGLE CALENDAR", type="primary"):
                with st.spinner("Sincronizando..."):
                    try:
                        for ev in st.session_state.lista_turnos:
                            body = {
                                'summary': ev['Turno'],
                                'start': {'dateTime': f"{ev['Fecha']}T{ev['Inicio']}:00", 'timeZone': 'America/Argentina/Catamarca'},
                                'end': {'dateTime': f"{ev['Fecha']}T{ev['Fin']}:00", 'timeZone': 'America/Argentina/Catamarca'},
                            }
                            service.events().insert(calendarId='primary', body=body).execute()
                        st.balloons()
                        st.success("¡Listo! Revisá tu calendario.")
                    except Exception as e:
                        st.error(f"Error al subir: {e}")
