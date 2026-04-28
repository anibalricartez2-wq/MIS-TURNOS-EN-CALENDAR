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

# --- FUNCIONES DE CACHÉ PARA EVITAR ERRORES DE TOKEN ---
@st.cache_resource
def get_flow():
    return Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)

# --- INICIALIZACIÓN DEL ESTADO ---
if 'agenda' not in st.session_state:
    st.session_state.agenda = {} # Almacena { "YYYY-MM-DD": "Nombre del Turno" }

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
            st.error("Hubo un error al conectar. Por favor, reintentá.")
            if st.button("Reintentar"):
                st.cache_resource.clear()
                st.rerun()
            st.stop()

# --- INTERFAZ PRINCIPAL (USUARIO CONECTADO) ---
service = build('calendar', 'v3', credentials=st.session_state.credentials)

st.title("🛠️ Gestión de Turnos y Rotaciones")

# SIDEBAR: CONFIGURACIÓN PERSONALIZADA DE TURNOS
st.sidebar.header("1. Tus Variantes de Turno")
st.sidebar.write("Definí tus horarios aquí:")

if 'df_turnos' not in st.session_state:
    st.session_state.df_turnos = pd.DataFrame([
        {"Turno": "Mañana", "Inicio": "07:00", "Fin": "15:00", "Horas": 8},
        {"Turno": "Tarde", "Inicio": "19:00", "Fin": "23:00", "Horas": 4}
    ])

turnos_config = st.sidebar.data_editor(st.session_state.df_turnos, num_rows="dynamic")

# CUERPO CENTRAL: ASIGNACIÓN POR BLOQUES
col_izq, col_der = st.columns([1, 1.2])

with col_izq:
    st.subheader("2. Asignar Días")
    
    # Selección de rango de fechas
    rango_fechas = st.date_input(
        "Seleccioná un día o un bloque (hacé clic en el inicio y fin)",
        value=[],
        help="Si seleccionás dos fechas, se completarán todos los días intermedios."
    )
    
    tipo_turno = st.selectbox("Asignar el turno:", turnos_config["Turno"])
    
    if st.button("➕ Aplicar al Calendario"):
        if isinstance(rango_fechas, list) or isinstance(rango_fechas, tuple):
            if len(rango_fechas) == 2:
                # Es un rango (bloque)
                inicio, fin = rango_fechas
                actual = inicio
                while actual <= fin:
                    st.session_state.agenda[actual.strftime("%Y-%m-%d")] = tipo_turno
                    actual += timedelta(days=1)
                st.success(f"Bloque asignado con éxito.")
            elif len(rango_fechas) == 1:
                # Es un solo día
                st.session_state.agenda[rango_fechas[0].strftime("%Y-%m-%d")] = tipo_turno
                st.success(f"Día individual asignado.")
            st.rerun()
        else:
            st.warning("Seleccioná al menos una fecha.")

with col_der:
    st.subheader("3. Vista Previa y Carga Horaria")
    
    if st.session_state.agenda:
        # Armar tabla de resumen
        lista_final = []
        for fecha_str, nombre_t in st.session_state.agenda.items():
            # Buscar datos del turno
            datos_t = turnos_config[turnos_config["Turno"] == nombre_t].iloc[0]
            lista_final.append({
                "Fecha": fecha_str,
                "Turno": nombre_t,
                "Horas": datos_t["Horas"]
            })
        
        df_resumen = pd.DataFrame(lista_final).sort_values("Fecha")
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
        
        # Lógica de las 130 horas
        total_h = df_resumen["Horas"].sum()
        st.metric("Total Horas Acumuladas", f"{total_h} hs", delta=f"{130 - total_h} restantes")
        
        if total_h > 130:
            st.error(f"⚠️ ¡Atención! Estás superando el límite de 130 horas por {total_h - 130} hs.")
            
        if st.button("🗑️ Limpiar Planificación"):
            st.session_state.agenda = {}
            st.rerun()
    else:
        st.info("No hay turnos asignados todavía.")

# --- SECCIÓN DE SINCRONIZACIÓN ---
st.divider()
if st.button("🚀 SUBIR A GOOGLE CALENDAR", type="primary", use_container_width=True):
    if not st.session_state.agenda:
        st.error("No hay nada para sincronizar.")
    else:
        with st.spinner("Sincronizando con Google..."):
            try:
                for f_str, t_nombre in st.session_state.agenda.items():
                    # Obtener horas específicas del turno
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
                st.success("¡Sincronización completada! Revisá tu Google Calendar.")
                st.session_state.agenda = {} # Opcional: limpiar después de subir
            except Exception as e:
                st.error(f"Error al subir: {e}")

if st.sidebar.button("Cerrar Sesión"):
    st.cache_resource.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
