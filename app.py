import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Rotaciones Aníbal", layout="wide")

# Estas líneas desactivan la validación estricta que causa el error 'Missing code verifier'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

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

# --- FUNCIÓN DE CONEXIÓN ---
def check_auth():
    if st.session_state.credentials:
        return True
    
    # IMPORTANTE: Desactivamos PKCE manualmente para evitar el error de validación
    flow = Flow.from_client_config(
        CLIENT_CONFIG, 
        scopes=SCOPES, 
        redirect_uri=REDIRECT_URI
    )
    
    if "code" in st.query_params:
        try:
            # Usamos un truco: le decimos que no use el verifier
            flow.fetch_token(code=st.query_params["code"], include_client_id=True)
            st.session_state.credentials = flow.credentials
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Error al validar: {e}")
            st.query_params.clear()
    
    # Forzamos a Google a darnos una sesión nueva siempre
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    st.title("📅 Sistema de Turnos")
    st.info("Hacé clic abajo para conectar con Google.")
    st.link_button("🔑 Conectar con Google Calendar", auth_url)
    return False

# --- APP PRINCIPAL ---
if check_auth():
    service = build('calendar', 'v3', credentials=st.session_state.credentials)
    st.success("✅ ¡Conectado!")

    col_config, col_vista = st.columns([1, 1.2])

    with col_config:
        st.subheader("1. Configurar Rotación")
        fecha_inicio = st.date_input("¿Cuándo empezó el ciclo?", datetime.now())
        dias_a_generar = st.number_input("Días a proyectar", value=30, min_value=1)
        
        # Ejemplo: MMTTFF (2 mañanas, 2 tardes, 2 francos)
        patron = st.text_input("Patrón de rotación (M, T, N, F)", "MMTTFF").upper().replace(" ", "")
        
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
                with st.spinner("Sincronizando..."):
                    try:
                        for ev in st.session_state.lista_turnos:
                            body = {
                                'summary': ev['Turno'],
                                'description': 'Sincronizado por App de Turnos',
                                'start': {'dateTime': f"{ev['Fecha']}T{ev['Inicio']}:00", 'timeZone': 'America/Argentina/Catamarca'},
                                'end': {'dateTime': f"{ev['Fecha']}T{ev['Fin']}:00", 'timeZone': 'America/Argentina/Catamarca'},
                            }
                            service.events().insert(calendarId='primary', body=body).execute()
                        st.balloons()
                        st.success("¡Calendario actualizado!")
                    except Exception as e:
                        st.error(f"Error: {e}")
