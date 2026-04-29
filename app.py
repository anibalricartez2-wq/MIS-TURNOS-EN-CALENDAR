import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Rotaciones Aníbal", layout="wide")

if 'access_token' not in st.session_state:
    st.session_state.access_token = None

CLIENT_ID = st.secrets["google_auth"]["client_id"]
CLIENT_SECRET = st.secrets["google_auth"]["client_secret"]
REDIRECT_URI = st.secrets["google_auth"]["redirect_uri"]

# --- FUNCIONES DE CONEXIÓN ---
def get_auth_url():
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
        "response_type": "code", "scope": "https://www.googleapis.com/auth/calendar.events",
        "access_type": "offline", "prompt": "consent"
    }
    return requests.Request('GET', base_url, params=params).prepare().url

def exchange_code_for_token(code):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"
    }
    return requests.post(token_url, data=data).json()

# --- LÓGICA DE LOGIN ---
if st.session_state.access_token is None:
    if "code" in st.query_params:
        res = exchange_code_for_token(st.query_params["code"])
        if "access_token" in res:
            st.session_state.access_token = res["access_token"]
            st.query_params.clear()
            st.rerun()
    st.title("📅 Sistema de Turnos")
    st.link_button("🔑 Conectar con Google Calendar", get_auth_url())
    st.stop()

# --- INTERFAZ DE ROTACIÓN ---
st.title("🔄 Generador de Rotaciones Personalizadas")
st.success("✅ Conectado a Google Calendar")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("1. Configurar Patrón")
    fecha_inicio = st.date_input("¿Qué día inicia el ciclo?", datetime.now())
    dias_a_proyectar = st.number_input("¿Cuántos días generar?", value=30, min_value=1)
    
    patron_input = st.text_input("Definí tu rotación (Ejemplo: MMTTFF o MMMMTTTTFFFF)", "MMTTFF")
    # Limpiamos el patrón: quitamos espacios y comas
    patron = patron_input.upper().replace(" ", "").replace(",", "")
    
    st.info(f"Ciclo actual: {'-'.join(patron)}")

    st.subheader("2. Definir Horarios")
    h_m = st.text_input("Mañana (M)", "07:00-15:00")
    h_t = st.text_input("Tarde (T)", "15:00-23:00")
    h_n = st.text_input("Noche (N)", "23:00-07:00")
    # Vacaciones y Francos no necesitan horario, son todo el día o no se suben

if st.button("⚡ Generar Rotación"):
    lista_final = []
    total_horas = 0
    
    for i in range(dias_a_proyectar):
        fecha_actual = fecha_inicio + timedelta(days=i)
        # Seleccionamos la letra del patrón que toca hoy
        letra = patron[i % len(patron)]
        
        info_dia = {
            "Fecha": fecha_actual.strftime("%Y-%m-%d"),
            "Día": fecha_actual.strftime("%A"), # Nombre del día
            "Turno": "Franco" if letra == 'F' else "Vacaciones" if letra == 'V' else f"Turno {letra}",
            "Horario": "---",
            "Subir": False,
            "Hs": 0
        }

        if letra in ['M', 'T', 'N']:
            horario = h_m if letra == 'M' else h_t if letra == 'T' else h_n
            info_dia["Horario"] = horario
            info_dia["Subir"] = True
            info_dia["Hs"] = 8 # Podés ajustar esto si querés
            total_horas += 8
        elif letra == 'V':
            info_dia["Horario"] = "Todo el día"
            info_dia["Subir"] = True # Las vacaciones sí solemos querer verlas en el calendar
            info_dia["Hs"] = 0

        lista_final.append(info_dia)
    
    st.session_state.agenda_generada = lista_final
    st.session_state.total_h = total_horas

# --- VISTA PREVIA Y SUBIDA ---
if 'agenda_generada' in st.session_state:
    with col2:
        st.subheader("3. Vista Previa")
        df = pd.DataFrame(st.session_state.agenda_generada)
        
        # Colorear la tabla para que sea fácil de leer
        def color_turnos(val):
            if 'M' in val: color = '#e1f5fe'
            elif 'T' in val: color = '#fff9c4'
            elif 'Franco' in val: color = '#f1f1f1'
            elif 'Vacaciones' in val: color = '#c8e6c9'
            else: color = 'white'
            return f'background-color: {color}'

        st.dataframe(df.style.applymap(color_turnos, subset=['Turno']), use_container_width=True)
        
        st.metric("Total Horas de Trabajo", f"{st.session_state.total_h} hs", 
                  delta=f"{130 - st.session_state.total_h} para el límite")

        if st.button("🚀 SUBIR TURNOS Y VACACIONES A GOOGLE", type="primary", use_container_width=True):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            exitos = 0
            with st.spinner("Subiendo al calendario..."):
                for dia in st.session_state.agenda_generada:
                    if dia["Subir"]:
                        # Preparar evento
                        if dia["Turno"] == "Vacaciones":
                            body = {
                                "summary": "🌴 VACACIONES",
                                "start": {"date": dia["Fecha"]}, # Evento de día completo
                                "end": {"date": (datetime.strptime(dia["Fecha"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")}
                            }
                        else:
                            ini, fin = dia["Horario"].split("-")
                            body = {
                                "summary": dia["Turno"],
                                "start": {"dateTime": f"{dia['Fecha']}T{ini}:00", "timeZone": "America/Argentina/Catamarca"},
                                "end": {"dateTime": f"{dia['Fecha']}T{fin}:00", "timeZone": "America/Argentina/Catamarca"}
                            }
                        
                        r = requests.post("https://www.googleapis.com/calendar/v3/calendars/primary/events", 
                                          json=body, headers=headers)
                        if r.status_code == 200: exitos += 1
                
                st.balloons()
                st.success(f"¡Se subieron {exitos} eventos correctamente!")
