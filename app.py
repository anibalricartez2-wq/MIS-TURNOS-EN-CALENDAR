import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

# Inicializar la agenda en la sesión si no existe
if 'agenda' not in st.session_state:
    st.session_state.agenda = {}

# --- SEGURIDAD (Secrets) ---
try:
    CLIENT_CONFIG = {
        "web": {
            "client_id": st.secrets["google_auth"]["client_id"],
            "client_secret": st.secrets["google_auth"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
except:
    st.error("Error: No se encontraron los Secrets. Revisá la configuración en Streamlit Cloud.")
    st.stop()

# --- INTERFAZ ---
st.title("📅 Sistema de Turnos - Selección Múltiple")

# 1. Configuración de Turnos
st.sidebar.header("Configurar Horarios")
df_turnos = pd.DataFrame([
    {"Turno": "Mañana", "Horas": 8},
    {"Turno": "Tarde", "Horas": 4},
    {"Turno": "Guardia", "Horas": 12}
])
turnos_config = st.sidebar.data_editor(df_turnos, num_rows="dynamic")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Paso 1: Seleccionar Turno y Días")
    
    # Elegir el tipo de turno primero
    tipo = st.selectbox("¿Qué turno vas a asignar?", turnos_config["Turno"])
    
    # Seleccionar días (aquí podés arrastrar o elegir varios)
    dias_seleccionados = st.date_input("Hacé clic o arrastrá en el calendario:", value=None)
    
    if st.button("✅ Confirmar estos días"):
        if dias_seleccionados:
            # Si eligió un rango (lista/tupla)
            if isinstance(dias_seleccionados, (list, tuple)):
                import datetime as dt
                start = dias_seleccionados[0]
                end = dias_seleccionados[-1]
                curr = start
                while curr <= end:
                    st.session_state.agenda[curr.strftime("%Y-%m-%d")] = tipo
                    curr += dt.timedelta(days=1)
            # Si eligió un solo día
            else:
                st.session_state.agenda[dias_seleccionados.strftime("%Y-%m-%d")] = tipo
            st.success("Días agregados a la lista de abajo.")
        else:
            st.warning("Primero seleccioná días en el calendario.")

with col2:
    st.subheader("Paso 2: Revisión y Carga Horaria")
    
    if st.session_state.agenda:
        # Armar el resumen
        datos_resumen = []
        for fecha, t_name in st.session_state.agenda.items():
            hs = turnos_config[turnos_config["Turno"] == t_name]["Horas"].values[0]
            datos_resumen.append({"Fecha": fecha, "Turno": t_name, "Horas": hs})
        
        df_res = pd.DataFrame(datos_resumen).sort_values("Fecha")
        st.table(df_res) # 'table' es más estable que 'dataframe'
        
        total_hs = df_res["Horas"].sum()
        st.metric("Total Horas", f"{total_hs} hs", f"{130 - total_hs} para el límite")
        
        if st.button("🗑️ Borrar todo y empezar de nuevo"):
            st.session_state.agenda = {}
            st.rerun()
    else:
        st.write("Aún no hay días asignados.")

# --- BOTÓN DE SINCRONIZACIÓN ---
st.divider()
st.info("Cuando termines de armar todo el mes, dale al botón de abajo:")
if st.button("🚀 SUBIR A GOOGLE CALENDAR", type="primary"):
    st.write("Conectando con Google...")
    # Aquí iría el código de sincronización que ya tenías funcional
