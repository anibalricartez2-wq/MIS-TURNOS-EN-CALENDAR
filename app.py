import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURACIÓN DE GOOGLE ---
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

st.set_page_config(page_title="Planificador de Turnos Pro", layout="wide")

# --- FUNCIONES DE CACHÉ ---
@st.cache_resource
def get_flow():
    return Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)

# --- INICIALIZACIÓN DEL ESTADO ---
if 'agenda' not in st.session_state:
    st.session_state.agenda = {}

# --- FLUJO DE AUTENTICACIÓN ---
if 'credentials' not in st.session_state:
    flow = get_flow()
    if "code" not in st.query_params:
        st.title("📅 Organizador de Turnos")
        st.info("Conectá tu cuenta de Google para empezar.")
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        st.link_button("🔑 Conectar con Google Calendar", auth_url)
        st.stop()
    else:
        try:
            flow.fetch_token(code=st.query_params["code"])
            st.session_state.credentials = flow.credentials
            st.rerun()
        except:
            st.error("Error de conexión. Reintentá.")
            st.stop()

# --- INTERFAZ PRINCIPAL ---
service = build('calendar', 'v3', credentials=st.session_state.credentials)

st.title("🛠️ Gestión de Turnos y Rotaciones")

# 1. CONFIGURACIÓN DE TURNOS (DENTRO DE LA APP PARA QUE SEA EDITABLE)
st.sidebar.header("1. Configurar Turnos")
if 'df_turnos' not in st.session_state:
    st.session_state.df_turnos = pd.DataFrame([
        {"Turno": "Mañana", "Inicio": "07:00", "Fin": "15:00", "Horas": 8},
        {"Turno": "Tarde", "Inicio": "19:00", "Fin": "23:00", "Horas": 4},
        {"Turno": "Guardia", "Inicio": "08:00", "Fin": "20:00", "Horas": 12}
    ])

# La tabla editable
turnos_config = st.sidebar.data_editor(st.session_state.df_turnos, num_rows="dynamic")

col_izq, col_der = st.columns([1, 1.2])

with col_izq:
    st.subheader("2. Selección de Días")
    st.write("Elegí un día y el turno, luego dale a 'Confirmar'.")
    
    # Selección de un solo día para máxima estabilidad
    fecha_clic = st.date_input("Seleccioná un día:", value=datetime.now())
    tipo_turno = st.selectbox("Asignar el turno:", turnos_config["Turno"])
    
    if st.button("✅ Confirmar Día"):
        # Guardamos en el diccionario: clave=fecha, valor=nombre del turno
        st.session_state.agenda[fecha_clic.strftime("%Y-%m-%d")] = tipo_turno
        st.success(f"Día {fecha_clic.day} asignado como {tipo_turno}")

with col_der:
    st.subheader("3. Vista Previa y Carga Horaria")
    
    if st.session_state.agenda:
        resumen_data = []
        for f_str, t_nombre in st.session_state.agenda.items():
            # Buscamos las horas del turno configurado
            try:
                hs = turnos_config[turnos_config["Turno"] == t_nombre]["Horas"].values[0]
                resumen_data.append({"Fecha": f_str, "Turno": t_nombre, "Horas": hs})
            except:
                continue
        
        df_res = pd.DataFrame(resumen_data).sort_values("Fecha")
        st.dataframe(df_res, use_container_width=True, hide_index=True)
        
        total_h = df_res["Horas"].sum()
        st.metric("Total Horas Acumuladas", f"{total_h} hs", delta=f"{130 - total_h} restantes")
        
        if total_h > 130:
            st.error(f"⚠️ Atención: Superaste el límite por {total_h - 130} hs.")
            
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.agenda = {}
            st.rerun()
    else:
        st.info("No hay turnos asignados todavía.")

# --- SINCRONIZACIÓN ---
st.divider()
if st.button("🚀 SUBIR A GOOGLE CALENDAR", type="primary", use_container_width=True):
    if not st.session_state.agenda:
        st.error("No hay turnos para subir.")
    else:
        with st.spinner("Sincronizando..."):
            try:
                for f_str, t_nombre in st.session_state.agenda.items():
                    info_t = turnos_config[turnos_config["Turno"] == t_nombre].iloc[0]
                    event = {
                        'summary': f'Turno: {t_nombre}',
                        'start': {'dateTime': f'{f_str}T{info_t["Inicio"]}:00', 'timeZone': 'America/Argentina/Catamarca'},
                        'end': {'dateTime': f'{f_str}T{info_t["Fin"]}:00', 'timeZone': 'America/Argentina/Catamarca'},
                    }
                    service.events().insert(calendarId='primary', body=event).execute()
                st.balloons()
                st.success("¡Turnos subidos con éxito!")
                st.session_state.agenda = {} 
            except Exception as e:
                st.error(f"Error al subir: {e}")
