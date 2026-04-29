import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURACIÓN DE SEGURIDAD Y GOOGLE ---
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
        st.info("Conectá tu cuenta de Google para empezar a planificar.")
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        st.link_button("🔑 Conectar con Google Calendar", auth_url)
        st.stop()
    else:
        try:
            flow.fetch_token(code=st.query_params["code"])
            st.session_state.credentials = flow.credentials
            st.rerun()
        except:
            st.error("Hubo un error al conectar.")
            if st.button("Reintentar"):
                st.cache_resource.clear()
                st.rerun()
            st.stop()

# --- INTERFAZ PRINCIPAL ---
service = build('calendar', 'v3', credentials=st.session_state.credentials)

st.title("🛠️ Gestión de Turnos y Rotaciones")

# SIDEBAR: CONFIGURACIÓN DE TURNOS
st.sidebar.header("1. Tus Variantes de Turno")
if 'df_turnos' not in st.session_state:
    st.session_state.df_turnos = pd.DataFrame([
        {"Turno": "Mañana", "Inicio": "07:00", "Fin": "15:00", "Horas": 8},
        {"Turno": "Tarde", "Inicio": "19:00", "Fin": "23:00", "Horas": 4},
        {"Turno": "Guardia", "Inicio": "08:00", "Fin": "20:00", "Horas": 12}
    ])

turnos_config = st.sidebar.data_editor(st.session_state.df_turnos, num_rows="dynamic")

col_izq, col_der = st.columns([1, 1.2])

with col_izq:
    st.subheader("2. Selección de Días")
    st.info("Hacé clic en todos los días que quieras asignar (ej: 2, 4, 7, 8).")
    
    # NUEVO: Selección múltiple de fechas
    fechas_seleccionadas = st.date_input(
        "Seleccioná los días en el calendario:",
        value=[], # Lista vacía permite seleccionar varios
        help="Podés marcar días salteados haciendo clic en cada uno."
    )
    
    tipo_turno = st.selectbox("Asignar el turno:", turnos_config["Turno"])
    
    if st.button("➕ Aplicar Turno a Selección"):
        if fechas_seleccionadas and isinstance(fechas_seleccionadas, list):
            for fecha in fechas_seleccionadas:
                st.session_state.agenda[fecha.strftime("%Y-%m-%d")] = tipo_turno
            st.success(f"Asignado '{tipo_turno}' a {len(fechas_seleccionadas)} días.")
            st.rerun()
        else:
            st.warning("Seleccioná al menos un día (hacé clic en el calendario).")

with col_der:
    st.subheader("3. Vista Previa y Carga Horaria")
    
    if st.session_state.agenda:
        lista_final = []
        for fecha_str, nombre_t in st.session_state.agenda.items():
            try:
                datos_t = turnos_config[turnos_config["Turno"] == nombre_t].iloc[0]
                lista_final.append({
                    "Fecha": fecha_str,
                    "Turno": nombre_t,
                    "Horas": datos_t["Horas"]
                })
            except:
                continue
        
        df_resumen = pd.DataFrame(lista_final).sort_values("Fecha")
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
        
        total_h = df_resumen["Horas"].sum()
        st.metric("Total Horas Acumuladas", f"{total_h} hs", delta=f"{130 - total_h} restantes")
        
        if total_h > 130:
            st.error(f"⚠️ ¡Atención! Superaste el límite por {total_h - 130} hs.")
            
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.agenda = {}
            st.rerun()
    else:
        st.info("No hay turnos asignados.")

# --- SINCRONIZACIÓN ---
st.divider()
if st.button("🚀 SUBIR A GOOGLE CALENDAR", type="primary", use_container_width=True):
    if not st.session_state.agenda:
        st.error("No hay nada para sincronizar.")
    else:
        with st.spinner("Subiendo eventos..."):
            try:
                for f_str, t_nombre in st.session_state.agenda.items():
                    info_t = turnos_config[turnos_config["Turno"] == t_nombre].iloc[0]
                    event = {
                        'summary': f'Turno: {t_nombre}',
                        'start': {
                            'dateTime': f'{f_str}T{info_t["Inicio"]}:00',
                            'timeZone': 'America/Argentina/Catamarca',
                        },
                        'end': {
                            'dateTime': f'{f_str}T{info_t["Fin"]}:00',
                            'timeZone': 'America/Argentina/Catamarca',
                        },
                    }
                    service.events().insert(calendarId='primary', body=event).execute()
                st.balloons()
                st.success("¡Calendario actualizado!")
                st.session_state.agenda = {} 
            except Exception as e:
                st.error(f"Error: {e}")

if st.sidebar.button("Cerrar Sesión"):
    st.cache_resource.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
