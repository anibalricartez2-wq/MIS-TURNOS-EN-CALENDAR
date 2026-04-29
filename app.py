import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURACIÓN DE GOOGLE (La que te funcionaba) ---
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

st.set_page_config(page_title="Generador de Rotaciones", layout="wide")

# --- CONEXIÓN ---
if 'credentials' not in st.session_state:
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    if "code" not in st.query_params:
        st.title("📅 Sistema de Turnos")
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        st.link_button("🔑 Conectar con Google", auth_url)
        st.stop()
    else:
        flow.fetch_token(code=st.query_params["code"])
        st.session_state.credentials = flow.credentials
        st.rerun()

service = build('calendar', 'v3', credentials=st.session_state.credentials)

# --- LÓGICA DE ROTACIÓN ---
st.title("🔄 Generador Automático de Rotación")

col_config, col_vista = st.columns([1, 1])

with col_config:
    st.subheader("1. Configurar Ciclo")
    fecha_inicio = st.date_input("¿Qué día empieza el ciclo?", datetime.now())
    dias_a_generar = st.number_input("¿Cuántos días querés generar?", value=30)
    
    st.write("Definí tu rotación (ejemplo: MM TT FF):")
    # Creamos una lista de turnos para el ciclo
    patron = st.text_input("Patrón de rotación (M=Mañana, T=Tarde, N=Noche, F=Franco)", "MMTTFF")
    patron = patron.upper().replace(" ", "")

    st.divider()
    st.subheader("2. Definir Horarios")
    h_m = st.text_input("Horario Mañana (M)", "07:00-15:00")
    h_t = st.text_input("Horario Tarde (T)", "15:00-23:00")
    h_n = st.text_input("Horario Noche (N)", "23:00-07:00")

if st.button("⚡ Generar Vista Previa de la Rotación"):
    agenda_temporal = []
    total_horas = 0
    
    for i in range(dias_a_generar):
        fecha_actual = fecha_inicio + timedelta(days=i)
        # El truco: usamos el operador 'módulo' para repetir el patrón infinitamente
        letra_turno = patron[i % len(patron)]
        
        if letra_turno != 'F': # Si no es franco
            if letra_turno == 'M': horario = h_m
            elif letra_turno == 'T': horario = h_t
            elif letra_turno == 'N': horario = h_n
            else: horario = "08:00-16:00" # Por defecto
            
            inicio, fin = horario.split("-")
            # Calculamos horas (ejemplo simple 8hs)
            hs = 8 if letra_turno != 'F' else 0 
            
            agenda_temporal.append({
                "Fecha": fecha_actual.strftime("%Y-%m-%d"),
                "Turno": f"Turno {letra_turno}",
                "Inicio": inicio,
                "Fin": fin,
                "Horas": hs
            })
            total_horas += hs
    
    st.session_state.proxima_subida = agenda_temporal
    st.session_state.total_h = total_horas

# --- MOSTRAR RESULTADOS ---
if 'proxima_subida' in st.session_state:
    with col_vista:
        st.subheader("3. Vista Previa")
        df = pd.DataFrame(st.session_state.proxima_subida)
        st.dataframe(df, hide_index=True)
        st.metric("Total Horas Estimadas", f"{st.session_state.total_h} hs")
        
        if st.button("🚀 SUBIR TODO A GOOGLE CALENDAR"):
            with st.spinner("Sincronizando..."):
                for evento in st.session_state.proxima_subida:
                    body = {
                        'summary': evento['Turno'],
                        'start': {'dateTime': f"{evento['Fecha']}T{evento['Inicio']}:00", 'timeZone': 'America/Argentina/Catamarca'},
                        'end': {'dateTime': f"{evento['Fecha']}T{evento['Fin']}:00', 'timeZone': 'America/Argentina/Catamarca'},
                    }
                    service.events().insert(calendarId='primary', body=body).execute()
                st.success("¡Rotación cargada con éxito!")
