import streamlit as st
import pandas as pd
from datetime import datetime
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

# Inicializar estados de sesión si no existen
if 'credentials' not in st.session_state:
    st.session_state.credentials = None
if 'agenda' not in st.session_state:
    st.session_state.agenda = {}
if 'df_turnos' not in st.session_state:
    st.session_state.df_turnos = pd.DataFrame([
        {"Turno": "Mañana", "Inicio": "07:00", "Fin": "15:00", "Horas": 8},
        {"Turno": "Tarde", "Inicio": "19:00", "Fin": "23:00", "Horas": 4},
        {"Turno": "Guardia", "Inicio": "08:00", "Fin": "20:00", "Horas": 12}
    ])

# --- CONFIGURACIÓN DE GOOGLE ---
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
    st.error("Error: Faltan los Secrets en Streamlit Cloud.")
    st.stop()

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# --- PROCESO DE AUTENTICACIÓN ---
if st.session_state.credentials is None:
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    
    # Si Google nos mandó el código por la URL
    if "code" in st.query_params:
        try:
            flow.fetch_token(code=st.query_params["code"])
            st.session_state.credentials = flow.credentials
            # Limpiar la URL para que el código no se use dos veces
            st.query_params.clear() 
            st.rerun()
        except:
            st.error("El código de acceso expiró o es inválido.")
            auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
            st.link_button("🔑 Reintentar Conexión", auth_url)
            st.stop()
    else:
        # Si no hay credenciales ni código, mostrar botón de inicio
        st.title("📅 Bienvenida/o al Organizador")
        st.info("Para empezar, conectá tu cuenta de Google Calendar.")
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        st.link_button("🔑 Conectar con Google Calendar", auth_url)
        st.stop()

# --- SI LLEGAMOS ACÁ, YA ESTAMOS CONECTADOS ---
service = build('calendar', 'v3', credentials=st.session_state.credentials)

st.title("🛠️ Gestión de Turnos")

# Sidebar: Configuración de Turnos (Editable)
st.sidebar.header("1. Configurar Horarios")
# El data_editor actualiza directamente el DataFrame en session_state
st.session_state.df_turnos = st.sidebar.data_editor(st.session_state.df_turnos, num_rows="dynamic")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("2. Asignar Turno")
    fecha = st.date_input("Elegí el día:", value=datetime.now())
    # Usamos los nombres de los turnos de la tabla editable
    lista_nombres_turnos = st.session_state.df_turnos["Turno"].tolist()
    tipo = st.selectbox("Elegí el turno:", lista_nombres_turnos)
    
    if st.button("✅ Confirmar Día"):
        st.session_state.agenda[fecha.strftime("%Y-%m-%d")] = tipo
        st.success(f"Día {fecha.day} anotado como {tipo}")

with col2:
    st.subheader("3. Resumen y Horas")
    if st.session_state.agenda:
        resumen = []
        for f, t_nombre in st.session_state.agenda.items():
            # Buscar horas en el DataFrame actual
            try:
                h = st.session_state.df_turnos[st.session_state.df_turnos["Turno"] == t_nombre]["Horas"].values[0]
                resumen.append({"Fecha": f, "Turno": t_nombre, "Horas": h})
            except:
                continue
        
        df_res = pd.DataFrame(resumen).sort_values("Fecha")
        st.dataframe(df_res, use_container_width=True, hide_index=True)
        
        total_h = df_res["Horas"].sum()
        st.metric("Total Horas Acumuladas", f"{total_h} hs", f"{130 - total_h} para el límite")
        
        if total_h > 130:
            st.error(f"⚠️ Cuidado: Superaste las 130 hs por {total_h - 130} hs.")
            
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.agenda = {}
            st.rerun()
    else:
        st.info("Todavía no cargaste ningún día.")

# --- BOTÓN FINAL ---
st.divider()
if st.button("🚀 SUBIR TODO A GOOGLE CALENDAR", type="primary", use_container_width=True):
    if not st.session_state.agenda:
        st.warning("No hay datos para subir.")
    else:
        with st.spinner("Subiendo eventos..."):
            try:
                for f_str, t_nombre in st.session_state.agenda.items():
                    info = st.session_state.df_turnos[st.session_state.df_turnos["Turno"] == t_nombre].iloc[0]
                    evento = {
                        'summary': f'Turno: {t_nombre}',
                        'start': {'dateTime': f'{f_str}T{info["Inicio"]}:00', 'timeZone': 'America/Argentina/Catamarca'},
                        'end': {'dateTime': f'{f_str}T{info["Fin"]}:00', 'timeZone': 'America/Argentina/Catamarca'},
                    }
                    service.events().insert(calendarId='primary', body=evento).execute()
                st.balloons()
                st.success("¡Sincronización completada!")
                st.session_state.agenda = {} # Limpiar después de subir
            except Exception as e:
                st.error(f"Error al subir: {e}")
